import pytest
from jsonlite import pymongo_patch

# Apply the pymongo patch to use JSONlite before importing pymongo
pymongo_patch()

from pymongo import MongoClient
import shutil
import pathlib

@pytest.fixture(scope='module')
def client():
    client = MongoClient('jsonlite://test_database')
    try:
        yield client
    finally:
        # Clean up the test_database folder
        db_path = pathlib.Path('test_database')
        if db_path.exists() and db_path.is_dir():
            shutil.rmtree(db_path)

@pytest.fixture(scope='function')
def collection(client):
    db = client.test_database
    collection = db.test_collection
    collection.drop()  # Ensure collection is empty before each test
    return collection

def test_insert_one(collection):
    result = collection.insert_one({"name": "Alice", "age": 30})
    assert result.inserted_id is not None
    document = collection.find_one({"name": "Alice"})
    assert document is not None
    assert document["name"] == "Alice"
    assert document["age"] == 30

def test_insert_many(collection):
    result = collection.insert_many([
        {"name": "Bob", "age": 25},
        {"name": "Charlie", "age": 35}
    ])
    assert len(result.inserted_ids) == 2
    documents = list(collection.find({"age": {"$gte": 25}}))
    assert len(documents) == 2

def test_find_one(collection):
    collection.insert_one({"name": "Alice", "age": 30})
    document = collection.find_one({"name": "Alice"})
    assert document is not None
    assert document["name"] == "Alice"
    assert document["age"] == 30

def test_find_many(collection):
    collection.insert_many([
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
        {"name": "Charlie", "age": 35}
    ])
    documents = list(collection.find({"age": {"$gte": 30}}))
    assert len(documents) == 2

def test_update_one(collection):
    collection.insert_one({"name": "Alice", "age": 30})
    result = collection.update_one({"name": "Alice"}, {"$set": {"age": 31}})
    assert result.matched_count == 1
    assert result.modified_count == 1
    document = collection.find_one({"name": "Alice"})
    assert document["age"] == 31

def test_update_many(collection):
    collection.insert_many([
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25}
    ])
    result = collection.update_many({"age": {"$gte": 25}}, {"$set": {"status": "active"}})
    assert result.matched_count == 2
    assert result.modified_count == 2
    documents = list(collection.find({"status": "active"}))
    assert len(documents) == 2

def test_delete_one(collection):
    collection.insert_one({"name": "Alice", "age": 30})
    result = collection.delete_one({"name": "Alice"})
    assert result.deleted_count == 1
    document = collection.find_one({"name": "Alice"})
    assert document is None

def test_delete_many(collection):
    collection.insert_many([
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25}
    ])
    result = collection.delete_many({"age": {"$lt": 30}})
    assert result.deleted_count == 1
    documents = list(collection.find({}))
    assert len(documents) == 1
