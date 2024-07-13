import json
import fcntl
import os
import re
import tempfile
from dataclasses import dataclass
from functools import wraps
from typing import List, Dict, Union


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


@dataclass
class DeleteResult:
    deleted_count: int


class JSONlite:
    def __init__(self, filename: str):
        self._filename = filename
        self.operators = {
            '$gt': lambda v, c: v is not None and v > c,
            '$lt': lambda v, c: v is not None and v < c,
            '$gte': lambda v, c: v is not None and v >= c,
            '$lte': lambda v, c: v is not None and v <= c,
            '$eq': lambda v, c: v == c,
            '$regex': lambda v, c, o=None: re.search(c, v) is not None
        }
        if not os.path.exists(filename):
            self._touch_database()

    def _load_database(self, file):
        file.seek(0)
        if not file.read(1):  # init database if file is empty
            self._database = {"data": []}
        else:
            file.seek(0)
            self._database = json.load(file)
        self._data = self._database["data"]

    def _save_database(self, file):
        json.dump(self._database, file, ensure_ascii=False, indent=4)
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

    def _match_filter(self, filter: Dict, record: Dict, deep: int = 0) -> bool:  # noqa: C901
        # fuck regex
        # convert {"$regex": "a", "$options": "i"} to {new_regex_op: "a"}
        if "$regex" in filter and "$options" in filter:
            options = filter.pop("$options")

            def new_regex_op(v, c):
                return self.operators["$regex"](v, c, options)
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
                            if not function(record.get(key), *cond_value):
                                return False
                        else:
                            if not function(record.get(key), cond_value):
                                return False
                else:
                    if key not in record or record[key] != condition:
                        return False
        return True

    @_synchronized_write
    def _insert_one(self, record: Dict) -> int:
        if "_id" in record:
            raise ValueError(
                "ID should not be specified. It is auto-generated.")
        record = record.copy()
        record["_id"] = self._generate_id()
        self._data.append(record)
        return record["_id"]

    def insert_one(self, record: Dict) -> InsertOneResult:
        return InsertOneResult(inserted_id=self._insert_one(record))

    def insert_many(self, records: List[Dict]) -> InsertManyResult:
        return InsertManyResult(
            inserted_ids=[
                self._insert_one(r) for r in records])

    @_synchronized_write
    def _update(self, filter: Dict, update_values: Dict,
                update_all: bool = False) -> UpdateResult:
        matched_count = 0
        modified_count = 0
        for idx, record in enumerate(self._data):
            if self._match_filter(filter, record):
                matched_count += 1
                new_record = record.copy()
                # TODO apply update
                if "$set" in update_values:
                    new_record.update(update_values["$set"])
                else:
                    new_record = update_values
                    new_record['_id'] = record.get('_id')
                if record != new_record:
                    modified_count += 1
                    self._data[idx] = new_record
                if not update_all:
                    break
        return UpdateResult(
            matched_count=matched_count,
            modified_count=modified_count)

    def update_one(self, filter: Dict, update_values: Dict) -> UpdateResult:
        return self._update(filter, update_values, update_all=False)

    def update_many(self, filter: Dict, update_values: Dict) -> UpdateResult:
        return self._update(filter, update_values, update_all=True)

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

    def find(self, filter: Dict = {}) -> List[Dict]:
        return self._find(filter, find_all=True)

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
