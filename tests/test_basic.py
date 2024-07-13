import pytest
import tempfile
import os
import re
from jsonlite import JSONlite


def mod(value, a, b):
    return value is not None and value % a == b


def is_multiple_of(value, match_value):
    return value is not None and value % match_value == 0


def is_between(value, min_value, max_value):
    return min_value < value < max_value


@pytest.fixture
def temp_db():
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, mode="w+", encoding="utf-8")
    filename = temp_file.name
    db = JSONlite(filename)
    db2 = JSONlite(filename)
    db.insert_many([
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob', 'age': 25},
        {'name': 'Charlie', 'age': 20},
        {"name": "David", "age": 40, "value": 2},
        {"name": "Eve", "age": None, "value": 2},
        {"name": "Frank"}  # Missing age
    ])
    yield db, db2, filename
    temp_file.close()
    os.remove(filename)


def assert_equal_without_id(a, b):
    def remove_id_fields(d):
        if isinstance(d, dict):
            return {k: remove_id_fields(v) for k, v in d.items() if k != '_id'}
        elif isinstance(d, list):
            return [remove_id_fields(x) for x in d]
        else:
            return d
    assert remove_id_fields(a) == remove_id_fields(b)


def test_new_db():
    filename = 'jsondb_test_db2.json'
    JSONlite(filename)
    assert os.path.exists(filename)
    os.remove(filename)


def test_insert_one(temp_db):
    db, db2, _ = temp_db
    record = {'name': 'Tom', 'age': 10}
    result = db.insert_one(record)
    found = db2.find_one({'_id': result.inserted_id})
    assert_equal_without_id(found, record)


def test_insert_with_id(temp_db):
    db, _, _ = temp_db
    record = {'_id': 10, 'name': 'Dave', 'age': 40}
    with pytest.raises(ValueError, match="ID should not be specified. It is auto-generated."):
        db.insert_one(record)


def test_insert_many(temp_db):
    db, db2, _ = temp_db
    records = [
        {'name': 'Ann', 'age': 80},
        {'name': 'Jim', 'age': 15}
    ]
    result = db.insert_many(records)
    found = db2.find({"$or": [{"_id": inserted_id}
                     for inserted_id in result.inserted_ids]})
    assert_equal_without_id(records, found)


def test_find_one(temp_db):
    db, _, _ = temp_db
    result = db.find_one({'name': 'Alice'})
    assert result is not None
    assert result['name'] == 'Alice'


def test_find(temp_db):
    db, _, _ = temp_db
    result = db.find({'name': 'Alice'})
    assert len(result) == 1
    for record in result:
        assert record['name'] == 'Alice'


@pytest.mark.parametrize("name, query, expected_count, condition", [
    ("all", {}, 6, lambda r: True),
    ("nonexists", {'name': 'Nonexistent'}, 0, lambda r: False),
    ("gt", {'age': {"$gt": 20}}, 3, lambda r: r["age"] > 20),
    ("mod", {'age': {mod: [2, 1]}}, 1, lambda r: mod(r["age"], 2, 1)),
    ("multiple", {'age': {is_multiple_of: 10}}, 3, lambda r: is_multiple_of(r["age"], 10)),
    ("between", {'age': {"$gt": 10, "$lt": 30}}, 2, lambda r: r["age"] > 10 and r["age"] < 30),
    ("or", {'$or': [{'name': 'Alice'}, {'age': 20}]}, 2, lambda r: r['name'] == 'Alice' or r['age'] == 20),
    ("and", {'$and': [{'name': 'Alice'}, {'age': 30}]}, 1, lambda r: r['name'] == 'Alice' and r['age'] == 30),
    ("nested_or",
        {'$or': [
            {'name': 'Alice'},
            {'$and': [{'age': {"$lt": 30}}, {'name': {"$regex": 'lie'}}]}
        ]},
        2,
        lambda r: r['name'] == 'Alice' or (r['age'] < 30 and 'lie' in r['name'])),
    ("nested_or2",
        {'$or': [
            {'name': 'Alice'},
            {'age': {"$lt": 30}, 'name': {"$regex": 'lie'}}
        ]},
        2,
        lambda r: r['name'] == 'Alice' or (r['age'] < 30 and 'lie' in r['name'])),
    ("exists_true", {'age': {"$exists": True}}, 5, lambda r: 'age' in r),
    ("exists_false", {'age': {"$exists": False}}, 1, lambda r: 'age' not in r),
    ("nested_exists",
        {'$and': [
            {'age': {"$exists": True}},
            {'$or': [{'value': {"$exists": True}}, {'name': 'Frank'}]}
        ]},
        2,
        lambda r: ('age' in r) and (('value' in r) or r['name'] == 'Frank')),
    ("nor",
        {'$nor': [{'age': {"$lt": 30}}, {'name': 'Bob'}]},
        4,
        lambda r: not (r["age"] < 30 if "age" in r and r["age"] is not None else False) and r['name'] != 'Bob'),
    ("not",
        {'age': {'$not': {'$gt': 30}}},
        5,
        lambda r: not ("age" in r and r["age"] is not None and r["age"] > 30)),
    ("complex_nested",
        {'$and': [
            {'$or': [{'age': {"$exists": True}}, {'age': {"$lt": 40}}]},
            {'$or': [{'value': {"$gt": 2}}, {'name': {"$regex": 'a', "$exists": True}}]}
        ]},
        2,
        lambda r: (r.get('age') is not None or r.get('age', 0) < 40) and
                  (r.get('value', 0) > 2 or re.search('a', r['name']))),
    ("empty_query", {}, 6, lambda r: True),
    ("lt_edge", {'age': {"$lt": 31}}, 3, lambda r: r["age"] < 31 if r.get("age") is not None else False),
    ("gt_edge", {'age': {"$gt": 39}}, 1, lambda r: r["age"] > 39 if r.get("age") is not None else False),
    ("eq_edge", {'age': {"$eq": 30}}, 1, lambda r: r["age"] == 30 if r.get("age") is not None else False),
    ("ne_edge", {'age': {"$ne": 30}}, 5, lambda r: r["age"] != 30 if r.get("age") is not None else True),
    ("nested_and_or",
        {'$and': [
            {'age': {"$gt": 20}},
            {'$or': [{'name': 'Alice'}, {'value': {"$exists": True}}]}
        ]},
        2,
        lambda r: (r['age'] > 20 if r.get("age") is not None else False) and (r['name'] == 'Alice' or 'value' in r))
])
def test_find_testsuits(name, query, expected_count, condition, temp_db):
    db, _ = temp_db[0:2]
    result = db.find(query)
    assert len(result) == expected_count
    for record in result:
        assert condition(record)


def test_update_one(temp_db):
    db, db2, _ = temp_db
    found = db.find_one({'name': 'Alice'})
    result = db.update_one({'name': 'Alice'}, {"$set": {'name': 'Alicia'}})
    assert result.matched_count == 1
    assert result.modified_count == 1
    found2 = db2.find_one({'_id': found["_id"]})
    found["name"] = "Alicia"
    assert found == found2


def test_update_replace(temp_db):
    db, db2, _ = temp_db
    found = db.find_one({'name': 'Alice'})
    result = db.update_one({'name': 'Alice'}, {'name': 'Alicia'})
    assert result.matched_count == 1
    assert result.modified_count == 1
    found2 = db2.find_one({'_id': found["_id"]})
    assert_equal_without_id({'name': 'Alicia'}, found2)


def test_update_many(temp_db):
    db, db2, _ = temp_db
    # updated
    result = db.update_many({'age': {"$gt": 20}}, {"$set": {'name': 'Alicia'}})
    assert result.matched_count == 3
    assert result.modified_count == 3
    found = db2.find({'name': 'Alicia'})
    assert len(found) == 3

    # not exists
    result = db.update_many({'age': {"$gt": 80}}, {"$set": {'name': 'Alicia'}})
    assert result.matched_count == 0
    assert result.modified_count == 0

    # duplicate update
    result = db.update_many({'age': {"$lt": 30}}, {"$set": {'name': 'Alicia'}})
    assert result.matched_count == 2
    assert result.modified_count == 1


def test_update_by_id(temp_db):
    db, _, _ = temp_db
    record = db.find_one({'name': 'Alice', 'age': 30})
    result = db.update_one({"_id": record['_id']}, {"$set": {'age': 31}})
    assert result.matched_count == 1
    assert result.modified_count == 1


def test_delete_one(temp_db):
    db, _, _ = temp_db
    result = db.delete_one({'name': 'Alice'})
    assert result.deleted_count == 1


def test_delete_many(temp_db):
    db, db2, _ = temp_db
    # delete non-exist
    result = db.delete_many({'name': 'Nonexistent'})
    assert result.deleted_count == 0

    # delete all
    result = db.delete_many({})
    assert result.deleted_count == 6
    assert len(db2.find({})) == 0


def test_delete_by_id(temp_db):
    db, db2, _ = temp_db
    record = db.find_one({'name': 'Alice', 'age': 30})
    db.delete_one({"_id": record['_id']})
    assert db2.find_one({"_id": record['_id']}) is None
