import pytest
from jsonlite import JSONlite
import shutil
import pathlib
from datetime import datetime
from decimal import Decimal

@pytest.fixture(scope='module')
def db():
    # Create a test database
    db_path = pathlib.Path('test_database.json')
    db = JSONlite(db_path)
    try:
        yield db
    finally:
        # Clean up the test_database.json file
        if db_path.exists():
            db_path.unlink()

@pytest.fixture(scope='function')
def clear_db(db):
    # Ensure the database is empty before each test
    db.delete_many({})
    yield
    db.delete_many({})  # Cleanup after test

def assert_documents_equal(doc1, doc2):
    assert doc1 == doc2, f"{doc1} != {doc2}"

def test_data_integrity_across_various_types(db, clear_db):
    # Test data containing various data types
    test_data = {
        "integer": 123,
        "float": 123.456,
        "string": "Hello, world!",
        "datetime": datetime(2023, 1, 1, 12, 0, 0),
        "decimal": Decimal('123.456'),
        "binary": b'\x00\x01\x02\x03\x04',
        "long_text": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 10,
        "markdown": "# Title\n\nSome **bold** text and _italic_ text.\n\n- List item 1\n- List item 2",
        "boolean_true": True,
        "boolean_false": False,
        "list": [1, "two", 3.0, {"four": 4}],
        "dict": {"key1": "value1", "key2": 2},
        "none": None
    }
    
    # Insert the test data
    insert_result = db.insert_one(test_data)
    inserted_id = insert_result.inserted_id
    
    # Retrieve the inserted data
    retrieved_data = db.find_one({"_id": inserted_id})
    
    # Ensure the _id field is present in the retrieved data
    assert "_id" in retrieved_data
    del retrieved_data["_id"]  # Remove _id for comparison

    # Ensure that the retrieved data matches the original data
    assert_documents_equal(test_data, retrieved_data)

if __name__ == "__main__":
    pytest.main()

