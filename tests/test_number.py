import pytest
from jsonlite import JSONlite
import tempfile
import os
from decimal import Decimal

@pytest.fixture
def temp_db():
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, mode="w+", encoding="utf-8")
    filename = temp_file.name
    db = JSONlite(filename)
    db2 = JSONlite(filename)
    yield db, db2, filename
    temp_file.close()
    os.remove(filename)

def test_number_precision(temp_db):
    db, db2, filename = temp_db
    test_data = {
        "integer": 123,
        "float": 123.456789,
        "decimal": Decimal('123.456789012345678901234567890')
    }
    insert_result = db.insert_one(test_data)
    inserted_id = insert_result.inserted_id
    retrieved_data = db2.find_one({"_id": inserted_id})
    assert "_id" in retrieved_data
    del retrieved_data["_id"]
    assert test_data == retrieved_data

def test_number_comparison(temp_db):
    db, db2, filename = temp_db
    db.insert_one({"number": 100})
    db.insert_one({"number": 200})
    found = db2.find_one({"number": {"$gt": 150}})
    assert found["number"] == 200