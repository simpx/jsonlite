import pytest
from jsonlite import JSONlite
import tempfile
import os
from datetime import datetime

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

def test_datetime_insert_and_retrieve(temp_db):
    db, db2, filename = temp_db
    test_data = {
        "datetime1": datetime(2023, 1, 1, 12, 0, 0),
        "datetime2": datetime(2022, 1, 1, 12, 0, 0)
    }
    insert_result = db.insert_one(test_data)
    inserted_id = insert_result.inserted_id
    retrieved_data = db2.find_one({"_id": inserted_id})
    assert "_id" in retrieved_data
    del retrieved_data["_id"]
    assert test_data == retrieved_data

def test_datetime_comparison(temp_db):
    db, db2, filename = temp_db
    db.insert_one({"datetime": datetime(2022, 1, 1, 12, 0, 0)})
    db.insert_one({"datetime": datetime(2023, 1, 1, 12, 0, 0)})
    found = db2.find_one({"datetime": {"$gt": datetime(2022, 1, 1, 12, 0, 0)}})
    assert found["datetime"] == datetime(2023, 1, 1, 12, 0, 0)
