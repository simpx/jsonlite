import json
import fcntl
import os
import re
import tempfile
import base64
from dataclasses import dataclass
from functools import wraps
from typing import List, Dict, Union, Any, Optional
from datetime import datetime
from decimal import Decimal
from copy import deepcopy


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
    
    return new_record


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
        if not os.path.exists(filename):
            self._touch_database()

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
            self._database = {"data": []}
        else:
            file.seek(0)
            self._database = json.load(file, object_hook=self._object_hook)
        self._data = self._database["data"]

    def _save_database(self, file):
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

    def insert_many(self, records: List[Dict]) -> InsertManyResult:
        return InsertManyResult(
            inserted_ids=[
                self._insert_one(r) for r in records])

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
