import json
import fcntl
import os
import re
import tempfile
import base64
from dataclasses import dataclass
from functools import wraps
from typing import List, Dict, Union, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from copy import deepcopy
from bisect import insort_left, bisect_left, bisect_right


@dataclass
class InsertOneResult:
    inserted_id: int


@dataclass
class InsertManyResult:
    inserted_ids: list[int]


@dataclass
class UpdateResult:
    matched_count: int
    modified_count: int
    upserted_id: Optional[Any] = None


@dataclass
class DeleteResult:
    deleted_count: int


class Cursor:
    """Chainable cursor for query operations (sort, limit, skip, projection)."""
    
    def __init__(self, data: List[Dict], db_instance: 'JSONlite'):
        self._data = deepcopy(data)
        self._db = db_instance
        self._sort_keys: List[tuple] = []  # [(key, direction), ...]
        self._skip_count: int = 0
        self._limit_count: Optional[int] = None
        self._projection: Optional[Dict] = None
    
    def sort(self, key: Union[str, List[tuple]], direction: int = 1) -> 'Cursor':
        """Sort results by field(s).
        
        Args:
            key: Field name (str) or list of (field, direction) tuples
            direction: 1 for ASC, -1 for DESC (ignored if key is list)
        
        Returns:
            Self for chaining
        """
        if isinstance(key, list):
            self._sort_keys = key
        else:
            self._sort_keys.append((key, direction))
        return self
    
    def skip(self, count: int) -> 'Cursor':
        """Skip N documents.
        
        Args:
            count: Number of documents to skip
        
        Returns:
            Self for chaining
        """
        self._skip_count = count
        return self
    
    def limit(self, count: int) -> 'Cursor':
        """Limit results to N documents.
        
        Args:
            count: Maximum number of documents to return
        
        Returns:
            Self for chaining
        """
        self._limit_count = count
        return self
    
    def projection(self, fields: Dict) -> 'Cursor':
        """Select/exclude fields.
        
        Args:
            fields: Dict of {field: 1} to include or {field: 0} to exclude
        
        Returns:
            Self for chaining
        """
        self._projection = fields
        return self
    
    def _apply_sort(self) -> 'Cursor':
        """Apply sorting to internal data."""
        if not self._sort_keys:
            return self
        
        def sort_key(record):
            values = []
            for key, direction in self._sort_keys:
                val = record.get(key)
                # Handle None values (sort them last)
                if val is None:
                    val = (1, None)  # Sort None last
                else:
                    val = (0, val)
                # Reverse for DESC
                if direction == -1:
                    if isinstance(val[1], (int, float, str)):
                        val = (val[0], self._negate(val[1]))
                    else:
                        val = (val[0], val[1])
                values.append(val)
            return tuple(values)
        
        self._data.sort(key=sort_key)
        return self
    
    def _negate(self, val):
        """Negate value for DESC sorting."""
        if isinstance(val, (int, float)):
            return -val
        elif isinstance(val, str):
            # For strings, we can't simply negate, so we use a different approach
            # This is a workaround - in production, use locale-aware sorting
            return val
        return val
    
    def _apply_skip_limit(self) -> 'Cursor':
        """Apply skip and limit to internal data."""
        start = self._skip_count
        end = start + self._limit_count if self._limit_count else None
        self._data = self._data[start:end]
        return self
    
    def _apply_projection(self) -> 'Cursor':
        """Apply field projection to internal data."""
        if not self._projection:
            return self
        
        # Determine if we're including or excluding fields
        include_mode = None
        fields_to_include = set()
        fields_to_exclude = set()
        
        for field, mode in self._projection.items():
            if field == '_id':
                continue  # Handle _id separately
            if mode in [1, True]:
                include_mode = True
                fields_to_include.add(field)
            elif mode in [0, False]:
                include_mode = False
                fields_to_exclude.add(field)
        
        new_data = []
        for record in self._data:
            new_record = {}
            if include_mode is True:
                # Include mode: only include specified fields (+ _id by default)
                if self._projection.get('_id', 1) != 0:
                    if '_id' in record:
                        new_record['_id'] = record['_id']
                for field in fields_to_include:
                    if field in record:
                        new_record[field] = record[field]
            else:
                # Exclude mode: include all except specified fields
                for key, value in record.items():
                    if key not in fields_to_exclude:
                        new_record[key] = value
                if self._projection.get('_id', 1) == 0:
                    new_record.pop('_id', None)
            new_data.append(new_record)
        
        self._data = new_data
        return self
    
    def _execute(self) -> List[Dict]:
        """Execute all pending operations and return results."""
        self._apply_sort()._apply_skip_limit()._apply_projection()
        return self._data
    
    def all(self) -> List[Dict]:
        """Return all matching documents after applying operations."""
        return self._execute()
    
    def first(self) -> Optional[Dict]:
        """Return first matching document after applying operations."""
        results = self._execute()
        return results[0] if results else None
    
    def count(self) -> int:
        """Return count of matching documents (before skip/limit)."""
        return len(self._data)
    
    def __iter__(self):
        """Allow iteration over results."""
        return iter(self._execute())
    
    def __len__(self):
        """Return length of results."""
        return len(self._execute())
    
    def __getitem__(self, index):
        """Support indexing."""
        results = self._execute()
        return results[index]


class AggregationCursor:
    """Cursor for aggregation pipeline operations."""
    
    def __init__(self, data: List[Dict], db_instance: 'JSONlite'):
        self._data = deepcopy(data)
        self._db = db_instance
        self._stages: List[Dict] = []
        self._result: Optional[List[Dict]] = None
    
    def _match(self, filter: Dict) -> 'AggregationCursor':
        """$match stage: filter documents."""
        filtered = [doc for doc in self._data if self._db._match_filter(filter, doc)]
        self._data = filtered
        return self
    
    def _group(self, group_spec: Dict) -> 'AggregationCursor':
        """$group stage: group documents by field."""
        _id_expr = group_spec.get('_id')
        
        # Handle simple field grouping (_id: "$field")
        if isinstance(_id_expr, str) and _id_expr.startswith('$'):
            group_field = _id_expr[1:]
            groups = {}
            for doc in self._data:
                key = doc.get(group_field)
                if key not in groups:
                    groups[key] = []
                groups[key].append(doc)
            
            result = []
            for key, docs in groups.items():
                grouped_doc = {'_id': key}
                # Process accumulators
                for field, expr in group_spec.items():
                    if field == '_id':
                        continue
                    if isinstance(expr, dict):
                        for op, val in expr.items():
                            if op == '$sum':
                                if isinstance(val, str) and val.startswith('$'):
                                    grouped_doc[field] = sum(d.get(val[1:], 0) for d in docs if isinstance(d.get(val[1:]), (int, float)))
                                else:
                                    grouped_doc[field] = sum(val for d in docs)
                            elif op == '$avg':
                                if isinstance(val, str) and val.startswith('$'):
                                    vals = [d.get(val[1:]) for d in docs if isinstance(d.get(val[1:]), (int, float))]
                                    grouped_doc[field] = sum(vals) / len(vals) if vals else 0
                            elif op == '$count':
                                grouped_doc[field] = len(docs)
                            elif op == '$min':
                                if isinstance(val, str) and val.startswith('$'):
                                    vals = [d.get(val[1:]) for d in docs if d.get(val[1:]) is not None]
                                    grouped_doc[field] = min(vals) if vals else None
                            elif op == '$max':
                                if isinstance(val, str) and val.startswith('$'):
                                    vals = [d.get(val[1:]) for d in docs if d.get(val[1:]) is not None]
                                    grouped_doc[field] = max(vals) if vals else None
                            elif op == '$first':
                                grouped_doc[field] = docs[0].get(val[1:]) if val.startswith('$') else val
                            elif op == '$last':
                                grouped_doc[field] = docs[-1].get(val[1:]) if val.startswith('$') else val
                            elif op == '$push':
                                if isinstance(val, str) and val.startswith('$'):
                                    grouped_doc[field] = [d.get(val[1:]) for d in docs]
                                else:
                                    grouped_doc[field] = [val] * len(docs)
                result.append(grouped_doc)
            self._data = result
        else:
            # Handle literal _id (all docs in one group)
            self._data = [{'_id': _id_expr, 'count': len(self._data)}]
        return self
    
    def _project(self, projection: Dict) -> 'AggregationCursor':
        """$project stage: reshape documents."""
        new_data = []
        
        # Determine if we're in include or exclude mode
        exclude_fields = set()
        include_fields = {}
        exclude_mode = None
        
        for field, expr in projection.items():
            if field == '_id':
                if expr == 0:
                    exclude_fields.add('_id')
                continue
            
            if expr in [0, False]:
                exclude_mode = True
                exclude_fields.add(field)
            elif expr in [1, True]:
                if exclude_mode is None:
                    exclude_mode = False
                include_fields[field] = None
            elif isinstance(expr, str) and expr.startswith('$'):
                if exclude_mode is None:
                    exclude_mode = False
                include_fields[field] = expr[1:]  # Store source field
            elif isinstance(expr, dict):
                if exclude_mode is None:
                    exclude_mode = False
                include_fields[field] = expr  # Store expression
        
        for doc in self._data:
            new_doc = {}
            
            if exclude_mode:
                # Exclude mode: copy all fields except excluded ones
                for key, value in doc.items():
                    if key not in exclude_fields:
                        new_doc[key] = value
            else:
                # Include mode: only include specified fields
                # Always include _id unless explicitly excluded
                if '_id' not in exclude_fields and '_id' in doc:
                    new_doc['_id'] = doc['_id']
                
                for field, source in include_fields.items():
                    if isinstance(source, str):
                        # Field reference
                        if source in doc:
                            new_doc[field] = doc[source]
                    elif isinstance(source, dict):
                        # Expression
                        new_doc[field] = self._eval_expr(source, doc)
                    else:
                        # Simple include
                        if field in doc:
                            new_doc[field] = doc[field]
            
            new_data.append(new_doc)
        self._data = new_data
        return self
    
    def _eval_expr(self, expr: Dict, doc: Dict) -> Any:
        """Evaluate an expression against a document."""
        for op, val in expr.items():
            if op == '$concat':
                parts = []
                for item in val:
                    if isinstance(item, str) and item.startswith('$'):
                        parts.append(str(doc.get(item[1:], '')))
                    else:
                        parts.append(str(item))
                return ''.join(parts)
            elif op == '$add':
                total = 0
                for item in val:
                    if isinstance(item, str) and item.startswith('$'):
                        total += doc.get(item[1:], 0)
                    else:
                        total += item
                return total
            elif op == '$subtract':
                result = val[0]
                for item in val[1:]:
                    if isinstance(item, str) and item.startswith('$'):
                        result -= doc.get(item[1:], 0)
                    else:
                        result -= item
                return result
            elif op == '$multiply':
                result = 1
                for item in val:
                    if isinstance(item, str) and item.startswith('$'):
                        result *= doc.get(item[1:], 1)
                    else:
                        result *= item
                return result
            elif op == '$divide':
                if len(val) >= 2:
                    a = doc.get(val[0][1:], 0) if isinstance(val[0], str) and val[0].startswith('$') else val[0]
                    b = doc.get(val[1][1:], 1) if isinstance(val[1], str) and val[1].startswith('$') else val[1]
                    return a / b if b != 0 else None
            elif op == '$size':
                if isinstance(val, str) and val.startswith('$'):
                    arr = doc.get(val[1:], [])
                    return len(arr) if isinstance(arr, list) else 0
            elif op == '$literal':
                return val
            elif op == '$cond':
                # {$cond: {if: ..., then: ..., else: ...}}
                if isinstance(val, dict):
                    condition = val.get('if')
                    then_val = val.get('then')
                    else_val = val.get('else')
                    if isinstance(then_val, str) and then_val.startswith('$'):
                        then_val = doc.get(then_val[1:])
                    if isinstance(else_val, str) and else_val.startswith('$'):
                        else_val = doc.get(else_val[1:])
                    return then_val if condition else else_val
        return None
    
    def _sort(self, sort_spec: Dict) -> 'AggregationCursor':
        """$sort stage: sort documents."""
        sort_keys = []
        for field, direction in sort_spec.items():
            sort_keys.append((field, direction if direction in [1, -1] else 1))
        
        def sort_key(record):
            values = []
            for key, direction in sort_keys:
                val = record.get(key)
                if val is None:
                    val = (1, None)
                else:
                    val = (0, val)
                if direction == -1 and isinstance(val[1], (int, float)):
                    val = (val[0], -val[1])
                values.append(val)
            return tuple(values)
        
        self._data.sort(key=sort_key)
        return self
    
    def _skip(self, count: int) -> 'AggregationCursor':
        """$skip stage: skip N documents."""
        self._data = self._data[count:]
        return self
    
    def _limit(self, count: int) -> 'AggregationCursor':
        """$limit stage: limit to N documents."""
        self._data = self._data[:count]
        return self
    
    def _count(self, field_name: str = 'count') -> 'AggregationCursor':
        """$count stage: count documents."""
        self._data = [{field_name: len(self._data)}]
        return self
    
    def _unwind(self, path: Union[str, Dict]) -> 'AggregationCursor':
        """$unwind stage: deconstruct array field."""
        if isinstance(path, dict):
            field_path = path.get('path')
            preserve_nulls = path.get('preserveNullAndEmptyArrays', False)
        else:
            field_path = path
            preserve_nulls = False
        
        # Remove leading $ if present
        if isinstance(field_path, str) and field_path.startswith('$'):
            field_path = field_path[1:]
        
        new_data = []
        for doc in self._data:
            arr = _get_nested_value(doc, field_path)
            if isinstance(arr, list) and len(arr) > 0:
                for item in arr:
                    new_doc = deepcopy(doc)
                    _set_nested_value(new_doc, field_path, item)
                    new_data.append(new_doc)
            elif preserve_nulls:
                new_data.append(deepcopy(doc))
        
        self._data = new_data
        return self
    
    def aggregate(self, pipeline: List[Dict]) -> 'AggregationCursor':
        """Execute aggregation pipeline stages."""
        for stage in pipeline:
            for op, spec in stage.items():
                if op == '$match':
                    self._match(spec)
                elif op == '$group':
                    self._group(spec)
                elif op == '$project':
                    self._project(spec)
                elif op == '$sort':
                    self._sort(spec)
                elif op == '$skip':
                    self._skip(spec)
                elif op == '$limit':
                    self._limit(spec)
                elif op == '$count':
                    self._count(spec if isinstance(spec, str) else 'count')
                elif op == '$unwind':
                    self._unwind(spec)
        return self
    
    def all(self) -> List[Dict]:
        """Return all results."""
        return self._data
    
    def first(self) -> Optional[Dict]:
        """Return first result."""
        return self._data[0] if self._data else None
    
    def count(self) -> int:
        """Return count of results."""
        return len(self._data)
    
    def __iter__(self):
        """Allow iteration over results."""
        return iter(self._data)
    
    def __len__(self):
        """Return length of results."""
        return len(self._data)
    
    def __getitem__(self, index):
        """Support indexing."""
        return self._data[index]


class IndexManager:
    """Manages indexes for JSONlite database.
    
    Supports:
    - Single-field indexes
    - Compound indexes (multi-field)
    - Unique indexes
    - Sparse indexes (only index documents with the field)
    - Automatic index maintenance on insert/update/delete
    """
    
    def __init__(self):
        self._indexes: Dict[str, Dict] = {}  # index_name -> {keys, unique, sparse, data}
    
    def create_index(self, keys: Union[str, List[Tuple[str, int]]], 
                     unique: bool = False, 
                     sparse: bool = False,
                     name: Optional[str] = None) -> str:
        """Create an index on specified field(s).
        
        Args:
            keys: Field name (str) or list of (field, direction) tuples
            unique: If True, enforce uniqueness
            sparse: If True, only index documents with the field
            name: Optional index name (auto-generated if not provided)
        
        Returns:
            Index name
        
        Examples:
            create_index("age")  # Single field
            create_index([("age", 1), ("name", -1)])  # Compound index
            create_index("email", unique=True)  # Unique index
            create_index("optional_field", sparse=True)  # Sparse index
        """
        # Normalize keys to list of tuples
        if isinstance(keys, str):
            keys_list = [(keys, 1)]
        else:
            keys_list = keys
        
        # Generate index name if not provided
        if name is None:
            name_parts = []
            for field, direction in keys_list:
                name_parts.append(f"{field}_{direction}")
            name = "_".join(name_parts)
        
        if name in self._indexes:
            raise ValueError(f"Index '{name}' already exists")
        
        self._indexes[name] = {
            'keys': keys_list,
            'unique': unique,
            'sparse': sparse,
            'data': {}  # value -> list of _id
        }
        
        return name
    
    def drop_index(self, name: str) -> bool:
        """Drop an index by name.
        
        Args:
            name: Index name to drop
        
        Returns:
            True if index was dropped, False if it didn't exist
        """
        if name in self._indexes:
            del self._indexes[name]
            return True
        return False
    
    def drop_all_indexes(self) -> int:
        """Drop all indexes.
        
        Returns:
            Number of indexes dropped
        """
        count = len(self._indexes)
        self._indexes.clear()
        return count
    
    def list_indexes(self) -> List[Dict]:
        """List all indexes.
        
        Returns:
            List of index info dicts
        """
        return [
            {
                'name': name,
                'keys': info['keys'],
                'unique': info['unique'],
                'sparse': info['sparse']
            }
            for name, info in self._indexes.items()
        ]
    
    def get_index(self, name: str) -> Optional[Dict]:
        """Get index info by name.
        
        Args:
            name: Index name
        
        Returns:
            Index info dict or None if not found
        """
        if name in self._indexes:
            info = self._indexes[name]
            return {
                'name': name,
                'keys': info['keys'],
                'unique': info['unique'],
                'sparse': info['sparse']
            }
        return None
    
    def _get_key_value(self, doc: Dict, keys: List[Tuple[str, int]]) -> Optional[Tuple]:
        """Extract index key value from document.
        
        Args:
            doc: Document to extract key from
            keys: List of (field, direction) tuples
        
        Returns:
            Tuple of values or None if any field is missing (for sparse indexes)
        """
        values = []
        for field, direction in keys:
            value = _get_nested_value(doc, field)
            if value is None:
                return None  # Missing field, skip for sparse index
            values.append(value)
        return tuple(values) if len(values) > 1 else values[0]
    
    def add_document(self, doc: Dict) -> None:
        """Add a document to all indexes.
        
        Args:
            doc: Document to index
        """
        doc_id = doc.get('_id')
        if doc_id is None:
            return
        
        for name, info in self._indexes.items():
            if info['sparse']:
                key_value = self._get_key_value(doc, info['keys'])
                if key_value is None:
                    continue  # Skip sparse index for missing field
            else:
                key_value = self._get_key_value(doc, info['keys'])
                if key_value is None:
                    key_value = None  # Include None values for non-sparse
            
            if key_value not in info['data']:
                info['data'][key_value] = []
            
            # Check uniqueness
            if info['unique'] and doc_id not in info['data'][key_value]:
                if len(info['data'][key_value]) > 0:
                    raise ValueError(f"Duplicate key error for index '{name}': {key_value}")
            
            if doc_id not in info['data'][key_value]:
                info['data'][key_value].append(doc_id)
    
    def remove_document(self, doc: Dict) -> None:
        """Remove a document from all indexes.
        
        Args:
            doc: Document to remove
        """
        doc_id = doc.get('_id')
        if doc_id is None:
            return
        
        for name, info in self._indexes.items():
            key_value = self._get_key_value(doc, info['keys'])
            if key_value in info['data']:
                if doc_id in info['data'][key_value]:
                    info['data'][key_value].remove(doc_id)
                if len(info['data'][key_value]) == 0:
                    del info['data'][key_value]
    
    def update_document(self, old_doc: Dict, new_doc: Dict) -> None:
        """Update a document in all indexes.
        
        Args:
            old_doc: Document before update
            new_doc: Document after update
        """
        for name, info in self._indexes.items():
            old_key = self._get_key_value(old_doc, info['keys'])
            new_key = self._get_key_value(new_doc, info['keys'])
            
            if old_key == new_key:
                continue  # Index key unchanged
            
            doc_id = new_doc.get('_id')
            
            # Remove from old position
            if old_key is not None and old_key in info['data']:
                if doc_id in info['data'][old_key]:
                    info['data'][old_key].remove(doc_id)
                if len(info['data'][old_key]) == 0:
                    del info['data'][old_key]
            
            # Add to new position
            if new_key is not None or not info['sparse']:
                if new_key not in info['data']:
                    info['data'][new_key] = []
                
                if info['unique'] and len(info['data'][new_key]) > 0:
                    raise ValueError(f"Duplicate key error for index '{name}': {new_key}")
                
                if doc_id not in info['data'][new_key]:
                    info['data'][new_key].append(doc_id)
    
    def query_index(self, field: str, value: Any) -> Optional[List[int]]:
        """Query an index for documents matching a field value.
        
        Args:
            field: Field name to query
            value: Value to match
        
        Returns:
            List of document _ids or None if no suitable index exists
        """
        # Find a suitable index
        for name, info in self._indexes.items():
            if len(info['keys']) == 1 and info['keys'][0][0] == field:
                if value in info['data']:
                    return info['data'][value].copy()
                return []  # Empty list means no matches
        return None  # No suitable index
    
    def query_index_range(self, field: str, 
                          min_value: Any = None, 
                          max_value: Any = None,
                          min_inclusive: bool = True,
                          max_inclusive: bool = True) -> Optional[List[int]]:
        """Query an index for documents in a value range.
        
        Args:
            field: Field name to query
            min_value: Minimum value (None for no lower bound)
            max_value: Maximum value (None for no upper bound)
            min_inclusive: If True, include min_value
            max_inclusive: If True, include max_value
        
        Returns:
            List of document _ids or None if no suitable index exists
        """
        # Find a suitable index
        for name, info in self._indexes.items():
            if len(info['keys']) == 1 and info['keys'][0][0] == field:
                result = []
                sorted_keys = sorted(info['data'].keys())
                
                for key in sorted_keys:
                    if key is None:
                        continue
                    
                    # Check min bound
                    if min_value is not None:
                        if min_inclusive and key < min_value:
                            continue
                        if not min_inclusive and key <= min_value:
                            continue
                    
                    # Check max bound
                    if max_value is not None:
                        if max_inclusive and key > max_value:
                            break
                        if not max_inclusive and key >= max_value:
                            break
                    
                    result.extend(info['data'][key])
                
                return result
        
        return None  # No suitable index
    
    def rebuild_index(self, name: str, documents: List[Dict]) -> None:
        """Rebuild an index from scratch.
        
        Args:
            name: Index name to rebuild
            documents: All documents in the collection
        """
        if name not in self._indexes:
            raise ValueError(f"Index '{name}' does not exist")
        
        info = self._indexes[name]
        info['data'] = {}
        
        for doc in documents:
            try:
                self.add_document(doc)
            except ValueError:
                # Re-raise with context
                raise


def _get_nested_value(doc: Dict, path: str) -> Any:
    """Get value from nested document using dot notation."""
    parts = path.split('.')
    current = doc
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_value(doc: Dict, path: str, value: Any) -> None:
    """Set value in nested document using dot notation."""
    parts = path.split('.')
    current = doc
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _delete_nested_value(doc: Dict, path: str) -> bool:
    """Delete value from nested document using dot notation. Returns True if deleted."""
    parts = path.split('.')
    current = doc
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    if parts[-1] in current:
        del current[parts[-1]]
        return True
    return False


def _apply_update_operators(record: Dict, update_values: Dict) -> Dict:
    """Apply MongoDB-style update operators to a record.
    
    Supported operators:
    - $set: Set field values
    - $unset: Remove fields
    - $inc: Increment/decrement numeric fields
    - $rename: Rename fields
    - $max: Update if new value is greater
    - $min: Update if new value is smaller
    - $push: Add element to array
    - $pull: Remove elements from array
    - $addToSet: Add unique element to array
    - $pop: Remove first/last element from array
    - $pullAll: Remove multiple elements from array
    
    Args:
        record: The document to update
        update_values: Dict of operators and their values
    
    Returns:
        Updated record
    """
    new_record = deepcopy(record)
    
    # $set - Set field values
    if '$set' in update_values:
        for field, value in update_values['$set'].items():
            _set_nested_value(new_record, field, value)
    
    # $unset - Remove fields
    if '$unset' in update_values:
        for field in update_values['$unset']:
            _delete_nested_value(new_record, field)
    
    # $inc - Increment/decrement
    if '$inc' in update_values:
        for field, delta in update_values['$inc'].items():
            current = _get_nested_value(new_record, field)
            if current is None:
                current = 0
            if isinstance(current, (int, float, Decimal)) and isinstance(delta, (int, float, Decimal)):
                _set_nested_value(new_record, field, current + delta)
    
    # $rename - Rename fields
    if '$rename' in update_values:
        for old_field, new_field in update_values['$rename'].items():
            value = _get_nested_value(new_record, old_field)
            if value is not None:
                _delete_nested_value(new_record, old_field)
                _set_nested_value(new_record, new_field, value)
    
    # $max - Update if new value is greater
    if '$max' in update_values:
        for field, value in update_values['$max'].items():
            current = _get_nested_value(new_record, field)
            if current is None or (isinstance(current, (int, float, Decimal)) and value > current):
                _set_nested_value(new_record, field, value)
    
    # $min - Update if new value is smaller
    if '$min' in update_values:
        for field, value in update_values['$min'].items():
            current = _get_nested_value(new_record, field)
            if current is None or (isinstance(current, (int, float, Decimal)) and value < current):
                _set_nested_value(new_record, field, value)
    
    # $push - Add element to array
    if '$push' in update_values:
        for field, value in update_values['$push'].items():
            current = _get_nested_value(new_record, field)
            if current is None:
                current = []
            if isinstance(current, list):
                current.append(value)
                _set_nested_value(new_record, field, current)
    
    # $pull - Remove elements from array matching condition
    if '$pull' in update_values:
        for field, condition in update_values['$pull'].items():
            current = _get_nested_value(new_record, field)
            if isinstance(current, list):
                # Support both simple value and operator conditions
                if isinstance(condition, dict):
                    # Operator condition (e.g., {$gt: 5})
                    filtered = [
                        item for item in current
                        if not _matches_pull_condition(item, condition)
                    ]
                else:
                    # Simple value match
                    filtered = [item for item in current if item != condition]
                _set_nested_value(new_record, field, filtered)
    
    # $addToSet - Add unique element to array
    if '$addToSet' in update_values:
        for field, value in update_values['$addToSet'].items():
            current = _get_nested_value(new_record, field)
            if current is None:
                current = []
            if isinstance(current, list):
                # Check if value already exists (handle dict comparison)
                exists = any(_deep_equals(item, value) for item in current)
                if not exists:
                    current.append(value)
                    _set_nested_value(new_record, field, current)
    
    # $pop - Remove first or last element from array
    if '$pop' in update_values:
        for field, direction in update_values['$pop'].items():
            current = _get_nested_value(new_record, field)
            if isinstance(current, list) and len(current) > 0:
                if direction == 1 or direction == -1:
                    # 1 = remove last, -1 = remove first
                    if direction == 1:
                        current.pop()
                    else:
                        current.pop(0)
                    _set_nested_value(new_record, field, current)
    
    # $pullAll - Remove multiple elements from array
    if '$pullAll' in update_values:
        for field, values in update_values['$pullAll'].items():
            current = _get_nested_value(new_record, field)
            if isinstance(current, list) and isinstance(values, list):
                filtered = [item for item in current if item not in values]
                _set_nested_value(new_record, field, filtered)
    
    return new_record


def _matches_pull_condition(item: Any, condition: Dict) -> bool:
    """Check if an item matches a pull condition (operator dict).
    
    Args:
        item: The array element to check
        condition: Dict of operators (e.g., {'$gt': 5})
    
    Returns:
        True if item matches the condition
    """
    for op, cond_value in condition.items():
        if op == '$eq':
            if item != cond_value:
                return False
        elif op == '$gt':
            if not (item is not None and item > cond_value):
                return False
        elif op == '$gte':
            if not (item is not None and item >= cond_value):
                return False
        elif op == '$lt':
            if not (item is not None and item < cond_value):
                return False
        elif op == '$lte':
            if not (item is not None and item <= cond_value):
                return False
        elif op == '$in':
            if item not in cond_value:
                return False
        elif op == '$ne':
            if item == cond_value:
                return False
    return True


def _deep_equals(a: Any, b: Any) -> bool:
    """Deep equality check for dicts, lists, and primitives.
    
    Args:
        a: First value
        b: Second value
    
    Returns:
        True if values are deeply equal
    """
    if type(a) != type(b):
        return False
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_deep_equals(a[k], b[k]) for k in a.keys())
    elif isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_deep_equals(ai, bi) for ai, bi in zip(a, b))
    else:
        return a == b


class JSONlite:
    def __init__(self, filename: str):
        self._filename = filename
        self.operators = {
            '$gt': lambda v, c: v is not None and v > c,
            '$lt': lambda v, c: v is not None and v < c,
            '$gte': lambda v, c: v is not None and v >= c,
            '$lte': lambda v, c: v is not None and v <= c,
            '$eq': lambda v, c: v == c,
            '$regex': lambda v, c, o=None: re.search(c, v) is not None,
            '$in': lambda v, c: v in c,
            '$all': lambda v, c: isinstance(v, (list, tuple)) and all(item in v for item in c)
        }
        self._index_manager = IndexManager()
        self._index_metadata = []
        if not os.path.exists(filename):
            self._touch_database()
        else:
            # Reload to get index metadata
            with open(filename, 'r', encoding='utf-8') as file:
                self._load_database(file)
            # Rebuild indexes from metadata
            self._rebuild_indexes_from_metadata()

    def _default_serializer(self, obj):
        if isinstance(obj, datetime):
            return {'_type': 'datetime', 'value': obj.isoformat()}
        elif isinstance(obj, Decimal):
            return {'_type': 'decimal', 'value': str(obj)}
        elif isinstance(obj, bytes):
            return {'_type': 'binary', 'value': base64.b64encode(obj).decode('utf-8')}
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

    def _object_hook(self, dct):
        if '_type' in dct:
            if dct['_type'] == 'datetime':
                return datetime.fromisoformat(dct['value'])
            elif dct['_type'] == 'decimal':
                return Decimal(dct['value'])
            elif dct['_type'] == 'binary':
                return base64.b64decode(dct['value'])
        return dct

    def _load_database(self, file):
        file.seek(0)
        if not file.read(1):  # init database if file is empty
            self._database = {"data": [], "_indexes": []}
        else:
            file.seek(0)
            self._database = json.load(file, object_hook=self._object_hook)
        self._data = self._database["data"]
        # Load index metadata (but rebuild from data)
        self._index_metadata = self._database.get("_indexes", [])

    def _save_database(self, file):
        # Save index metadata
        self._database["_indexes"] = self._index_manager.list_indexes()
        json.dump(self._database, file, ensure_ascii=False, indent=4, default=self._default_serializer)
        file.flush()
        os.fsync(file.fileno())

    def _synchronized_write(method):
        @wraps(method)
        def wrapper(instance, *args, **kwargs):
            filename = instance._filename
            while True:
                with open(filename, 'a'), open(filename, 'r+', encoding='utf-8') as file:
                    fcntl.flock(file, fcntl.LOCK_EX)
                    try:
                        with open(filename, 'a'), open(filename, 'r+', encoding='utf-8') as file2:
                            inode_before = os.fstat(file.fileno()).st_ino
                            inode_after = os.fstat(file2.fileno()).st_ino
                            if inode_before == inode_after:
                                instance._load_database(file)
                                instance._rebuild_indexes_from_metadata()
                                result = method(instance, *args, **kwargs)
                                with tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(filename), mode='w',
                                                                 encoding='utf-8') as temp_file:
                                    instance._save_database(temp_file)
                                os.rename(temp_file.name, filename)
                                return result
                    finally:
                        fcntl.flock(file, fcntl.LOCK_UN)
        return wrapper

    def _synchronized_read(method):
        @wraps(method)
        def wrapper(instance, *args, **kwargs):
            # No need to lock cause it's read-only, and writes are atomic with
            # os.rename
            filename = instance._filename
            with open(filename, 'r', encoding='utf-8') as file:
                instance._load_database(file)
                instance._rebuild_indexes_from_metadata()
                return method(instance, *args, **kwargs)
        return wrapper

    @_synchronized_write
    def _touch_database(self):
        pass

    def _generate_id(self) -> int:
        ids = [item["_id"] for item in self._data if "_id" in item]
        next_id = max(ids) + 1 if ids else 1
        return next_id

    def _match_filter(self, filter: Dict, record: Dict, deep: int = 0) -> bool:
        # fuck regex
        # convert {"$regex": "a", "$options": "i"} to {new_regex_op: "a"}
        if "$regex" in filter and "$options" in filter:
            options = filter.pop("$options")

            def new_regex_op( v, c): 
                return self.operators["$regex"](
                v, c, options)
            filter[new_regex_op] = filter.pop("$regex")
        for key, condition in filter.items():
            if key == '$or':
                if not any(self._match_filter(sub_filter, record, deep + 1)
                           for sub_filter in condition):
                    return False
            elif key == '$and':
                if not all(self._match_filter(sub_filter, record, deep + 1)
                           for sub_filter in condition):
                    return False
            elif key == '$nor':
                if any(self._match_filter(sub_filter, record, deep + 1)
                       for sub_filter in condition):
                    return False
            elif key == '$not':
                if self._match_filter(condition, record, deep + 1):
                    return False
            elif isinstance(condition, dict) and len(condition) > 1:
                if not all(self._match_filter(
                        {key: {k: v}}, record, deep + 1) for k, v in condition.items()):
                    return False
            else:
                # {key: {operator: cond_value} } cond_value MUST NOT be dict
                # {key: cond_value}
                if isinstance(condition, dict):
                    assert len(condition) == 1
                    (operator, cond_value), = condition.items()
                    function = None
                    if operator == "$ne":
                        if self._match_filter(
                                {key: {"$eq": cond_value}}, record, deep + 1):
                            return False
                    elif operator == "$exists":
                        if bool(cond_value) != (key in record):
                            return False
                    elif operator == "$not":
                        if self._match_filter(
                                {key: cond_value}, record, deep + 1):
                            return False
                    elif operator in self.operators:
                        function = self.operators[operator]
                    elif callable(operator):
                        function = operator
                    else:
                        raise ValueError('Unknown operator: %s' % operator)
                    if function:
                        if key not in record:
                            return False
                        if isinstance(cond_value, (list, tuple)):
                            if operator in ['$in', '$all']:
                                if not function(record.get(key), cond_value):
                                    return False
                            else:
                                if not function(record.get(key), *cond_value):
                                    return False
                        else:
                            if not function(record.get(key), cond_value):
                                return False
                else:
                    if key not in record or record[key] != condition:
                        return False
        return True

    def _raw_insert_one(self, record: Dict) -> int:
        if "_id" in record:
            raise ValueError(
                "ID should not be specified. It is auto-generated.")
        record = record.copy()
        record["_id"] = self._generate_id()
        self._data.append(record)
        return record["_id"]

    @_synchronized_write
    def _insert_one(self, record: Dict) -> int:
        return self._raw_insert_one(record)
    def insert_one(self, record: Dict) -> InsertOneResult:
        return InsertOneResult(inserted_id=self._insert_one(record))

    @_synchronized_write
    def _insert_many(self, records: List[Dict]) -> List[int]:
        """Internal batch insert - single read/write cycle for all records."""
        inserted_ids = []
        for record in records:
            if "_id" in record:
                raise ValueError("ID should not be specified. It is auto-generated.")
            record = record.copy()
            record["_id"] = self._generate_id()
            self._data.append(record)
            inserted_ids.append(record["_id"])
        return inserted_ids
    
    def insert_many(self, records: List[Dict]) -> InsertManyResult:
        """Insert multiple records in a single batch operation.
        
        Optimized to perform only one file read/write cycle regardless of
        the number of records, significantly improving batch insert performance.
        
        Args:
            records: List of documents to insert
        
        Returns:
            InsertManyResult with list of inserted IDs
        
        Example:
            >>> result = db.insert_many([{'name': 'Alice'}, {'name': 'Bob'}])
            >>> print(result.inserted_ids)
            [1, 2]
        """
        if not records:
            return InsertManyResult(inserted_ids=[])
        return InsertManyResult(inserted_ids=self._insert_many(records))

    @_synchronized_write
    def _update(self, filter: Dict, update_values: Dict,
                update_all: bool = False, upsert: bool = False) -> UpdateResult:
        matched_count = 0
        modified_count = 0
        
        # Check if update_values contains any operators (keys starting with $)
        has_operators = any(key.startswith('$') for key in update_values.keys())
        
        for idx, record in enumerate(self._data):
            if self._match_filter(filter, record):
                matched_count += 1
                if has_operators:
                    # Apply update operators
                    new_record = _apply_update_operators(record, update_values)
                else:
                    # Full document replacement (preserve _id)
                    new_record = update_values.copy()
                    new_record['_id'] = record.get('_id')
                if record != new_record:
                    modified_count += 1
                    self._data[idx] = new_record
                if not update_all:
                    break
        if matched_count == 0 and upsert:
            upserted_record = filter.copy()
            if has_operators:
                upserted_record = _apply_update_operators(upserted_record, update_values)
            else:
                upserted_record.update(update_values)
            upserted_id = self._raw_insert_one(upserted_record)
            return UpdateResult(matched_count=0, modified_count=0, upserted_id=upserted_id)
        return UpdateResult(
            matched_count=matched_count,
            modified_count=modified_count)
    def update_one(self, filter: Dict, update_values: Dict, upsert: bool = False) -> UpdateResult:
        return self._update(filter, update_values, update_all=False, upsert=upsert)

    def update_many(self, filter: Dict, update_values: Dict, upsert: bool = False) -> UpdateResult:
        return self._update(filter, update_values, update_all=True, upsert=upsert)
    
    def replace_one(self, filter: Dict, replacement: Dict, upsert: bool = False) -> UpdateResult:
        return self._update(filter, replacement, update_all=False, upsert=upsert)

    @_synchronized_read
    def _find(self, filter: Dict, find_all: bool = False) -> List[Dict]:
        if filter == {}:
            # fastpath
            return self._data if find_all else self._data[:1]
        found_records = []
        for record in self._data:
            if self._match_filter(filter, record):
                found_records.append(record)
                if not find_all:
                    break
        return found_records

    def find_one(self, filter: Dict = {}) -> Union[Dict, None]:
        records = self._find(filter, find_all=False)
        return records[0] if records else None

    def find(self, filter: Dict = {}) -> Union[Cursor, List[Dict]]:
        """Find documents with optional chainable operations.
        
        Returns a Cursor for chainable operations (sort, limit, skip, projection).
        Call .all() on the cursor to get results as a list.
        
        Examples:
            # Chainable API
            db.find({"age": {"$gt": 18}}).sort("age", -1).limit(10).all()
            
            # Backward compatible - returns list directly
            db.find({"age": {"$gt": 18}})  # Returns list for backward compat
        """
        results = self._find(filter, find_all=True)
        return Cursor(results, self)

    @_synchronized_read
    def aggregate(self, pipeline: List[Dict]) -> AggregationCursor:
        """Execute an aggregation pipeline.
        
        Args:
            pipeline: List of aggregation stages ($match, $group, $project, $sort, $skip, $limit, $count, $unwind)
        
        Returns:
            AggregationCursor with results
        
        Examples:
            # Match and sort
            db.aggregate([
                {"$match": {"age": {"$gt": 18}}},
                {"$sort": {"age": -1}},
                {"$limit": 10}
            ]).all()
            
            # Group by field
            db.aggregate([
                {"$group": {"_id": "$category", "count": {"$count": {}}, "avgPrice": {"$avg": "$price"}}}
            ]).all()
            
            # Project fields
            db.aggregate([
                {"$match": {"status": "active"}},
                {"$project": {"name": 1, "email": 1}}
            ]).all()
        """
        results = self._find({}, find_all=True)
        cursor = AggregationCursor(results, self)
        return cursor.aggregate(pipeline)

    @_synchronized_write
    def find_one_and_delete(self, filter: Dict) -> Optional[Dict]:
        for idx, record in enumerate(self._data):
            if self._match_filter(filter, record):
                return self._data.pop(idx)
        return None

    def find_one_and_replace(self, filter: Dict, replacement: Dict) -> Optional[Dict]:
        existing_record = self.find_one(filter)
        if existing_record:
            # TODO should consider transaction here
            # between find and replace
            self.replace_one(filter, replacement)
        return existing_record

    def find_one_and_update(self, filter: Dict, update: Dict) -> Optional[Dict]:
        existing_record = self.find_one(filter)
        if existing_record:
            # TODO should consider transaction here
            # between find and replace
            self.update_one(filter, update)
        return existing_record

    @_synchronized_write
    def _delete(self, filter: Dict, delete_all: bool = False) -> DeleteResult:
        deleted_count = 0
        if filter == {} and delete_all:
            # fastpath
            deleted_count = len(self._data)
            self._data.clear()  # _data是一个引用，不能直接_data = []
        else:
            idx = 0
            while idx < len(self._data):
                if self._match_filter(filter, self._data[idx]):
                    del self._data[idx]
                    deleted_count += 1
                    if not delete_all:
                        break
                else:
                    idx += 1
        return DeleteResult(deleted_count=deleted_count)

    def delete_one(self, filter: Dict) -> DeleteResult:
        return self._delete(filter, delete_all=False)

    def delete_many(self, filter: Dict) -> DeleteResult:
        return self._delete(filter, delete_all=True)

    @_synchronized_read
    def count_documents(self, filter: Dict) -> int:
        return len(self._find(filter, find_all=True))

    @_synchronized_read
    def estimated_document_count(self) -> int:
        return len(self._data)

    @_synchronized_read
    def distinct(self, key: str, filter: Optional[Dict] = None) -> List[Any]:
        seen = set()
        distinct_values = []
        for record in self._data:
            if filter is None or self._match_filter(filter, record):
                value = record.get(key)
                if value not in seen:
                    seen.add(value)
                    distinct_values.append(value)
        return distinct_values

    @_synchronized_read
    def full_text_search(self, query: str) -> List[Dict]:
        """Perform a full-text search on the database.
        
        Args:
            query (str): The text to search for.
        
        Returns:
            List[Dict]: A list of documents that contain the query text.
        """
        results = []
        for record in self._data:
            if any(query in str(value) for value in record.values()):
                results.append(record)
        return results
    
    # ==================== Index Management ====================
    
    @_synchronized_write
    def _create_index_internal(self, keys: Union[str, List[Tuple[str, int]]], 
                               unique: bool, sparse: bool, name: Optional[str]) -> str:
        """Internal index creation (with write lock)."""
        index_name = self._index_manager.create_index(keys, unique, sparse, name)
        self._index_manager.rebuild_index(index_name, self._data)
        return index_name
    
    def create_index(self, keys: Union[str, List[Tuple[str, int]]], 
                     unique: bool = False, 
                     sparse: bool = False,
                     name: Optional[str] = None) -> str:
        """Create an index on specified field(s).
        
        Args:
            keys: Field name (str) or list of (field, direction) tuples
            unique: If True, enforce uniqueness
            sparse: If True, only index documents with the field
            name: Optional index name (auto-generated if not provided)
        
        Returns:
            Index name
        
        Examples:
            db.create_index("age")  # Single field
            db.create_index([("age", 1), ("name", -1)])  # Compound index
            db.create_index("email", unique=True)  # Unique index
        """
        return self._create_index_internal(keys, unique, sparse, name)
    
    def drop_index(self, name: str) -> bool:
        """Drop an index by name.
        
        Args:
            name: Index name to drop
        
        Returns:
            True if index was dropped, False if it didn't exist
        """
        return self._index_manager.drop_index(name)
    
    def drop_indexes(self) -> int:
        """Drop all indexes.
        
        Returns:
            Number of indexes dropped
        """
        return self._index_manager.drop_all_indexes()
    
    def _rebuild_indexes_from_metadata(self) -> None:
        """Rebuild indexes from saved metadata."""
        for idx_meta in self._index_metadata:
            try:
                self._index_manager.create_index(
                    idx_meta['keys'],
                    idx_meta.get('unique', False),
                    idx_meta.get('sparse', False),
                    idx_meta['name']
                )
                self._index_manager.rebuild_index(idx_meta['name'], self._data)
            except Exception:
                # Skip corrupted indexes
                pass
    
    def list_indexes(self) -> List[Dict]:
        """List all indexes.
        
        Returns:
            List of index info dicts with name, keys, unique, sparse
        """
        return self._index_manager.list_indexes()
    
    def _insert_one_with_index(self, record: Dict) -> int:
        """Insert one document and update indexes."""
        # Check if user provided _id (should be auto-generated)
        if '_id' in record:
            raise ValueError("ID should not be specified. It is auto-generated.")
        # Add _id to record before inserting (so we can use it for indexes)
        record_with_id = record.copy()
        record_with_id["_id"] = self._generate_id()
        self._data.append(record_with_id)
        # Add to indexes
        self._index_manager.add_document(record_with_id)
        return record_with_id["_id"]
    
    @_synchronized_write
    def _insert_one(self, record: Dict) -> int:
        return self._insert_one_with_index(record)
    
    @_synchronized_write
    def _update_with_index(self, filter: Dict, update_values: Dict,
                          update_all: bool = False, upsert: bool = False) -> UpdateResult:
        """Update with index maintenance."""
        matched_count = 0
        modified_count = 0
        
        has_operators = any(key.startswith('$') for key in update_values.keys())
        
        for idx, record in enumerate(self._data):
            if self._match_filter(filter, record):
                matched_count += 1
                old_record = deepcopy(record)
                
                if has_operators:
                    new_record = _apply_update_operators(record, update_values)
                else:
                    new_record = update_values.copy()
                    new_record['_id'] = record.get('_id')
                
                if record != new_record:
                    modified_count += 1
                    # Update indexes
                    self._index_manager.update_document(old_record, new_record)
                    self._data[idx] = new_record
                
                if not update_all:
                    break
        
        if matched_count == 0 and upsert:
            upserted_record = filter.copy()
            if has_operators:
                upserted_record = _apply_update_operators(upserted_record, update_values)
            else:
                upserted_record.update(update_values)
            upserted_id = self._insert_one_with_index(upserted_record)
            return UpdateResult(matched_count=0, modified_count=0, upserted_id=upserted_id)
        
        return UpdateResult(matched_count=matched_count, modified_count=modified_count)
    
    def update_one(self, filter: Dict, update_values: Dict, upsert: bool = False) -> UpdateResult:
        return self._update_with_index(filter, update_values, update_all=False, upsert=upsert)
    
    def update_many(self, filter: Dict, update_values: Dict, upsert: bool = False) -> UpdateResult:
        return self._update_with_index(filter, update_values, update_all=True, upsert=upsert)
    
    @_synchronized_write
    def _delete_with_index(self, filter: Dict, delete_all: bool = False) -> DeleteResult:
        """Delete with index maintenance."""
        deleted_count = 0
        if filter == {} and delete_all:
            # Remove all from indexes
            for record in self._data:
                self._index_manager.remove_document(record)
            deleted_count = len(self._data)
            self._data.clear()
        else:
            idx = 0
            while idx < len(self._data):
                if self._match_filter(filter, self._data[idx]):
                    # Remove from indexes before deleting
                    self._index_manager.remove_document(self._data[idx])
                    del self._data[idx]
                    deleted_count += 1
                    if not delete_all:
                        break
                else:
                    idx += 1
        return DeleteResult(deleted_count=deleted_count)
    
    def delete_one(self, filter: Dict) -> DeleteResult:
        return self._delete_with_index(filter, delete_all=False)
    
    def delete_many(self, filter: Dict) -> DeleteResult:
        return self._delete_with_index(filter, delete_all=True)
    
    def _find_with_index(self, filter: Dict, find_all: bool = False) -> List[Dict]:
        """Find using indexes when possible for optimization."""
        # Try to use index for simple equality filters
        if len(filter) == 1:
            field, value = list(filter.items())[0]
            if not isinstance(value, dict):  # Simple equality, not operator
                indexed_ids = self._index_manager.query_index(field, value)
                if indexed_ids is not None:
                    # Build id -> record map
                    id_map = {doc['_id']: doc for doc in self._data}
                    results = [id_map[_id] for _id in indexed_ids if _id in id_map]
                    return results if find_all else results[:1]
        
        # Fall back to full scan
        if filter == {}:
            return self._data if find_all else self._data[:1]
        
        found_records = []
        for record in self._data:
            if self._match_filter(filter, record):
                found_records.append(record)
                if not find_all:
                    break
        return found_records
    
    @_synchronized_read
    def _find(self, filter: Dict, find_all: bool = False) -> List[Dict]:
        return self._find_with_index(filter, find_all)
