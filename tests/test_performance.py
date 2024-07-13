# tests/test_performance.py

import pytest
import tempfile
import os
from jsonlite import JSONlite


@pytest.fixture
def temp_db():
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, mode="w+", encoding="utf-8")
    filename = temp_file.name
    db = JSONlite(filename)
    db.insert_many([
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob', 'age': 25},
        {'name': 'Charlie', 'age': 20},
        {"name": "David", "age": 40, "value": 2},
        {"name": "Eve", "age": None, "value": 2},
        {"name": "Frank"}  # Missing age
    ])
    yield db
    temp_file.close()
    os.remove(filename)

# 使用 pytest-benchmark 进行性能测试


def test_insert_one(benchmark, temp_db):
    db = temp_db
    record = {'name': 'SingleUser', 'age': 30}
    benchmark(db.insert_one, record)


def test_insert_many(benchmark, temp_db):
    db = temp_db
    records = [{'name': f'User{i}', 'age': i % 100} for i in range(100)]
    benchmark(db.insert_many, records)


def test_find_one(benchmark, temp_db):
    db = temp_db
    benchmark(db.find_one, {'name': 'User10'})


def test_find(benchmark, temp_db):
    db = temp_db
    benchmark(db.find, {'age': {"$gt": 50}})


def test_update_one(benchmark, temp_db):
    db = temp_db
    benchmark(db.update_one, {'name': 'Alice'}, {'$set': {'age': 31}})


def test_update_many(benchmark, temp_db):
    db = temp_db
    benchmark(
        db.update_many, {
            'age': {
                "$gt": 50}}, {
            '$set': {
                'name': 'Updated'}})


def test_delete_one(benchmark, temp_db):
    db = temp_db
    benchmark(db.delete_one, {'name': 'Alice'})


def test_delete_all(benchmark, temp_db):
    db = temp_db
    benchmark(db.delete_many, {})
