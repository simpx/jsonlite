"""Tests for Cursor chainable API (sort, limit, skip, projection)."""

import pytest
import tempfile
import os
from jsonlite import JSONlite


@pytest.fixture
def temp_db():
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8")
    filename = temp_file.name
    db = JSONlite(filename)
    db.insert_many([
        {'name': 'Alice', 'age': 30, 'city': 'NYC', 'score': 85},
        {'name': 'Bob', 'age': 25, 'city': 'LA', 'score': 92},
        {'name': 'Charlie', 'age': 35, 'city': 'NYC', 'score': 78},
        {'name': 'David', 'age': 28, 'city': 'Chicago', 'score': 88},
        {'name': 'Eve', 'age': 32, 'city': 'LA', 'score': 95},
        {'name': 'Frank', 'age': 22, 'city': 'NYC', 'score': 70},
    ])
    yield db, filename
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


# ============== SORT TESTS ==============

def test_sort_single_field_asc(temp_db):
    db, _ = temp_db
    results = db.find({}).sort("age", 1).all()
    ages = [r['age'] for r in results]
    assert ages == sorted(ages)
    assert ages[0] == 22  # Frank
    assert ages[-1] == 35  # Charlie


def test_sort_single_field_desc(temp_db):
    db, _ = temp_db
    results = db.find({}).sort("age", -1).all()
    ages = [r['age'] for r in results]
    assert ages == sorted(ages, reverse=True)
    assert ages[0] == 35  # Charlie
    assert ages[-1] == 22  # Frank


def test_sort_by_name(temp_db):
    db, _ = temp_db
    results = db.find({}).sort("name", 1).all()
    names = [r['name'] for r in results]
    assert names == ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank']


def test_sort_multi_field(temp_db):
    db, _ = temp_db
    # Sort by city (ASC), then by age (DESC) within each city
    results = db.find({}).sort([("city", 1), ("age", -1)]).all()
    # Chicago: David(28)
    # LA: Eve(32), Bob(25)
    # NYC: Charlie(35), Alice(30), Frank(22)
    assert results[0]['city'] == 'Chicago'
    assert results[0]['age'] == 28  # David
    assert results[1]['city'] == 'LA'
    assert results[1]['age'] == 32  # Eve (older first in LA)


def test_sort_with_filter(temp_db):
    db, _ = temp_db
    results = db.find({'age': {'$gt': 25}}).sort("age", -1).all()
    ages = [r['age'] for r in results]
    assert ages == sorted(ages, reverse=True)
    assert all(age > 25 for age in ages)


# ============== LIMIT TESTS ==============

def test_limit(temp_db):
    db, _ = temp_db
    results = db.find({}).limit(3).all()
    assert len(results) == 3


def test_limit_with_sort(temp_db):
    db, _ = temp_db
    results = db.find({}).sort("age", -1).limit(2).all()
    assert len(results) == 2
    assert results[0]['age'] == 35  # Charlie
    assert results[1]['age'] == 32  # Eve


def test_limit_exceeds_count(temp_db):
    db, _ = temp_db
    results = db.find({}).limit(100).all()
    assert len(results) == 6  # Only 6 records exist


# ============== SKIP TESTS ==============

def test_skip(temp_db):
    db, _ = temp_db
    results = db.find({}).skip(2).all()
    assert len(results) == 4  # 6 - 2 = 4


def test_skip_with_sort(temp_db):
    db, _ = temp_db
    results = db.find({}).sort("age", 1).skip(2).all()
    ages = [r['age'] for r in results]
    assert ages == sorted(ages)
    # Sorted ages: 22, 25, 28, 30, 32, 35
    # Skip 2: skip Frank(22) and Bob(25), start at David(28)
    assert ages[0] == 28


def test_skip_exceeds_count(temp_db):
    db, _ = temp_db
    results = db.find({}).skip(10).all()
    assert len(results) == 0


# ============== COMBINED SKIP + LIMIT ==============

def test_skip_and_limit(temp_db):
    db, _ = temp_db
    results = db.find({}).sort("age", 1).skip(2).limit(2).all()
    assert len(results) == 2
    ages = [r['age'] for r in results]
    # Sorted: 22, 25, 28, 30, 32, 35
    # Skip 2: start at 28
    # Limit 2: 28, 30
    assert ages == [28, 30]


# ============== PROJECTION TESTS ==============

def test_projection_include_fields(temp_db):
    db, _ = temp_db
    results = db.find({}).projection({'name': 1, 'age': 1}).all()
    for r in results:
        assert 'name' in r
        assert 'age' in r
        assert 'city' not in r
        assert 'score' not in r
        assert '_id' in r  # _id included by default


def test_projection_exclude_fields(temp_db):
    db, _ = temp_db
    results = db.find({}).projection({'city': 0, 'score': 0}).all()
    for r in results:
        assert 'name' in r
        assert 'age' in r
        assert '_id' in r
        assert 'city' not in r
        assert 'score' not in r


def test_projection_exclude_id(temp_db):
    db, _ = temp_db
    results = db.find({}).projection({'name': 1, 'age': 1, '_id': 0}).all()
    for r in results:
        assert 'name' in r
        assert 'age' in r
        assert '_id' not in r


def test_projection_with_filter(temp_db):
    db, _ = temp_db
    results = db.find({'age': {'$gt': 30}}).projection({'name': 1}).all()
    # Sorted ages: Alice=30, Bob=25, Charlie=35, David=28, Eve=32, Frank=22
    # age > 30: Charlie(35), Eve(32) = 2 records
    assert len(results) == 2
    for r in results:
        assert 'name' in r
        assert 'age' not in r


# ============== CHAINING TESTS ==============

def test_full_chain(temp_db):
    db, _ = temp_db
    results = (db.find({'age': {'$gt': 20}})
               .sort("age", -1)
               .skip(1)
               .limit(3)
               .projection({'name': 1, 'age': 1, '_id': 0})
               .all())
    
    assert len(results) == 3
    for r in results:
        assert 'name' in r
        assert 'age' in r
        assert '_id' not in r
        assert 'city' not in r
    
    # Verify sorting (DESC) and skip/limit
    ages = [r['age'] for r in results]
    assert ages == sorted(ages, reverse=True)


def test_cursor_first(temp_db):
    db, _ = temp_db
    result = db.find({}).sort("age", -1).first()
    assert result is not None
    assert result['age'] == 35  # Charlie
    assert result['name'] == 'Charlie'


def test_cursor_first_empty(temp_db):
    db, _ = temp_db
    result = db.find({'age': {'$gt': 100}}).first()
    assert result is None


def test_cursor_count(temp_db):
    db, _ = temp_db
    cursor = db.find({'age': {'$gt': 25}})
    count = cursor.count()
    assert count == 4  # Alice(30), Charlie(35), David(28), Eve(32)


def test_cursor_iteration(temp_db):
    db, _ = temp_db
    names = []
    for record in db.find({}).sort("name", 1).projection({'name': 1}):
        names.append(record['name'])
    assert names == ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank']


def test_cursor_indexing(temp_db):
    db, _ = temp_db
    cursor = db.find({}).sort("age", 1)
    first = cursor[0]
    last = cursor[-1]
    assert first['age'] == 22  # Frank
    assert last['age'] == 35  # Charlie


def test_cursor_len(temp_db):
    db, _ = temp_db
    cursor = db.find({}).sort("age", 1).limit(3)
    assert len(cursor) == 3


# ============== EDGE CASES ==============

def test_sort_with_none_values(temp_db):
    db, _ = temp_db
    # Add a record with None age
    db.insert_one({'name': 'Grace', 'age': None, 'city': 'Boston'})
    results = db.find({}).sort("age", 1).all()
    # None values should sort last
    assert results[-1]['name'] == 'Grace'


def test_empty_cursor(temp_db):
    db, _ = temp_db
    results = db.find({'name': 'Nonexistent'}).all()
    assert results == []
    assert len(results) == 0


def test_projection_no_match(temp_db):
    db, _ = temp_db
    results = db.find({'name': 'Nonexistent'}).projection({'name': 1}).all()
    assert results == []
