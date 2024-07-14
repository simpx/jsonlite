import pytest
from jsonlite import JSONlite
import tempfile
import os

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

def test_binary_insert_and_retrieve(temp_db):
    db, db2, filename = temp_db
    test_data = {
        "binary": b'\x00\x01\x02\x03\x04'*1024  # large binary data
    }
    insert_result = db.insert_one(test_data)
    inserted_id = insert_result.inserted_id
    retrieved_data = db2.find_one({"_id": inserted_id})
    assert "_id" in retrieved_data
    del retrieved_data["_id"]
    assert test_data == retrieved_data