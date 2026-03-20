"""Tests for MongoDB-style update operators ($unset, $inc, $rename, $max, $min)."""

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
        {'name': 'Alice', 'age': 30, 'score': 85, 'city': 'NYC'},
        {'name': 'Bob', 'age': 25, 'score': 92, 'city': 'LA'},
        {'name': 'Charlie', 'age': 35, 'score': 78, 'city': 'NYC'},
    ])
    yield db, filename
    temp_file.close()
    os.remove(filename)


# ============== $UNSET TESTS ==============

def test_unset_single_field(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$unset': {'city': 1}})
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert 'city' not in updated
    assert updated['name'] == 'Alice'
    assert updated['age'] == 30


def test_unset_multiple_fields(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Bob'}, {'$unset': {'score': 1, 'city': 1}})
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'Bob'})
    assert 'score' not in updated
    assert 'city' not in updated
    assert updated['name'] == 'Bob'


def test_unset_nonexistent_field(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$unset': {'nonexistent': 1}})
    assert result.matched_count == 1
    assert result.modified_count == 0  # No change


def test_unset_many_documents(temp_db):
    db, _ = temp_db
    result = db.update_many({}, {'$unset': {'score': 1}})
    assert result.matched_count == 3
    assert result.modified_count == 3
    
    all_docs = db.find({})
    for doc in all_docs:
        assert 'score' not in doc


# ============== $INC TESTS ==============

def test_inc_positive(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$inc': {'age': 5}})
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['age'] == 35  # 30 + 5


def test_inc_negative(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Bob'}, {'$inc': {'age': -3}})
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'Bob'})
    assert updated['age'] == 22  # 25 - 3


def test_inc_float(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$inc': {'score': 0.5}})
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['score'] == 85.5


def test_inc_nonexistent_field(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$inc': {'bonus': 10}})
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['bonus'] == 10  # Starts from 0, then +10


def test_inc_many(temp_db):
    db, _ = temp_db
    result = db.update_many({}, {'$inc': {'age': 1}})
    assert result.matched_count == 3
    assert result.modified_count == 3
    
    all_docs = db.find({})
    ages = [doc['age'] for doc in all_docs]
    assert 31 in ages  # Alice: 30+1
    assert 26 in ages  # Bob: 25+1
    assert 36 in ages  # Charlie: 35+1


# ============== $RENAME TESTS ==============

def test_rename_field(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$rename': {'city': 'location'}})
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert 'city' not in updated
    assert updated['location'] == 'NYC'


def test_rename_multiple_fields(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Bob'}, {'$rename': {'score': 'points', 'city': 'location'}})
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'Bob'})
    assert 'score' not in updated
    assert 'city' not in updated
    assert updated['points'] == 92
    assert updated['location'] == 'LA'


def test_rename_nonexistent_field(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$rename': {'nonexistent': 'newname'}})
    assert result.matched_count == 1
    assert result.modified_count == 0


# ============== $MAX TESTS ==============

def test_max_updates_when_higher(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$max': {'score': 90}})
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['score'] == 90  # 90 > 85


def test_max_no_update_when_lower(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$max': {'score': 80}})
    assert result.matched_count == 1
    assert result.modified_count == 0  # 80 < 85, no update
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['score'] == 85  # Unchanged


def test_max_nonexistent_field(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$max': {'bonus': 50}})
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['bonus'] == 50  # Field didn't exist, set to max value


# ============== $MIN TESTS ==============

def test_min_updates_when_lower(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$min': {'score': 80}})
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['score'] == 80  # 80 < 85


def test_min_no_update_when_higher(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$min': {'score': 90}})
    assert result.matched_count == 1
    assert result.modified_count == 0  # 90 > 85, no update
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['score'] == 85  # Unchanged


def test_min_nonexistent_field(temp_db):
    db, _ = temp_db
    result = db.update_one({'name': 'Alice'}, {'$min': {'bonus': 50}})
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['bonus'] == 50  # Field didn't exist, set to min value


# ============== COMBINED OPERATORS TESTS ==============

def test_combined_set_and_inc(temp_db):
    db, _ = temp_db
    result = db.update_one(
        {'name': 'Alice'},
        {'$set': {'city': 'Boston'}, '$inc': {'age': 1}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'Alice'})
    assert updated['city'] == 'Boston'
    assert updated['age'] == 31


def test_combined_unset_and_rename(temp_db):
    db, _ = temp_db
    result = db.update_one(
        {'name': 'Bob'},
        {'$unset': {'score': 1}, '$rename': {'city': 'location'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'Bob'})
    assert 'score' not in updated
    assert 'city' not in updated
    assert updated['location'] == 'LA'


def test_combined_all_operators(temp_db):
    db, _ = temp_db
    result = db.update_one(
        {'name': 'Charlie'},
        {
            '$set': {'status': 'active'},
            '$unset': {'city': 1},
            '$inc': {'age': 2},
            '$rename': {'score': 'points'},
            '$max': {'age': 100},  # Updates: 37 < 100, so age becomes 100
            '$min': {'points': 50}  # Updates: 50 < 78, so points becomes 50
        }
    )
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'Charlie'})
    assert updated['status'] == 'active'
    assert 'city' not in updated
    assert updated['age'] == 100  # 35 + 2 = 37, then $max sets to 100
    assert 'score' not in updated
    assert updated['points'] == 50  # Renamed from score (78), then $min sets to 50


# ============== NESTED FIELD TESTS ==============

def test_set_nested_field(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'address': {'city': 'NYC', 'zip': '10001'}})
    
    result = db.update_one(
        {'name': 'David'},
        {'$set': {'address.city': 'Boston'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['address']['city'] == 'Boston'
    assert updated['address']['zip'] == '10001'


def test_unset_nested_field(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'address': {'city': 'NYC', 'zip': '10001'}})
    
    result = db.update_one(
        {'name': 'David'},
        {'$unset': {'address.zip': 1}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert 'city' in updated['address']
    assert 'zip' not in updated['address']


def test_inc_nested_field(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'stats': {'views': 100, 'likes': 50}})
    
    result = db.update_one(
        {'name': 'David'},
        {'$inc': {'stats.views': 25}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['stats']['views'] == 125


# ============== UPSERT WITH UPDATE OPERATORS ==============

def test_upsert_with_set(temp_db):
    db, _ = temp_db
    result = db.update_one(
        {'name': 'Nonexistent'},
        {'$set': {'age': 25, 'status': 'new'}},
        upsert=True
    )
    assert result.matched_count == 0
    assert result.modified_count == 0
    assert result.upserted_id is not None
    
    created = db.find_one({'name': 'Nonexistent'})
    assert created is not None
    assert created['age'] == 25
    assert created['status'] == 'new'


def test_upsert_with_inc(temp_db):
    db, _ = temp_db
    result = db.update_one(
        {'name': 'NewUser'},
        {'$inc': {'count': 1}},
        upsert=True
    )
    assert result.upserted_id is not None
    
    created = db.find_one({'name': 'NewUser'})
    assert created['count'] == 1  # Started from 0, then +1


# ============== ARRAY OPERATORS: $push TESTS ==============

def test_push_to_existing_array(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$push': {'tags': 'golang'}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'rust', 'golang']


def test_push_creates_array_if_not_exists(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'score': 100})
    
    result = db.update_one(
        {'name': 'David'},
        {'$push': {'tags': 'python'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python']


def test_push_multiple_values(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python']})
    
    # Multiple pushes
    db.update_one({'name': 'David'}, {'$push': {'tags': 'rust'}})
    db.update_one({'name': 'David'}, {'$push': {'tags': 'golang'}})
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'rust', 'golang']


def test_push_to_nested_array(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'skills': {'languages': ['python']}})
    
    result = db.update_one(
        {'name': 'David'},
        {'$push': {'skills.languages': 'rust'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['skills']['languages'] == ['python', 'rust']


# ============== ARRAY OPERATORS: $pull TESTS ==============

def test_pull_simple_value(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust', 'golang']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pull': {'tags': 'rust'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'golang']


def test_pull_all_matching_values(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'scores': [85, 92, 85, 78, 85]})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pull': {'scores': 85}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['scores'] == [92, 78]


def test_pull_with_operator_condition(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'scores': [85, 92, 70, 78, 95]})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pull': {'scores': {'$lt': 80}}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['scores'] == [85, 92, 95]


def test_pull_with_gt_operator(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'scores': [85, 92, 70, 78, 95]})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pull': {'scores': {'$gt': 90}}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['scores'] == [85, 70, 78]


def test_pull_nonexistent_value(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pull': {'tags': 'golang'}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 0  # No change
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'rust']


# ============== ARRAY OPERATORS: $addToSet TESTS ==============

def test_addToSet_adds_unique_value(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$addToSet': {'tags': 'golang'}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'rust', 'golang']


def test_addToSet_skips_duplicate(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$addToSet': {'tags': 'python'}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 0  # No change, already exists
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'rust']


def test_addToSet_creates_array_if_not_exists(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'score': 100})
    
    result = db.update_one(
        {'name': 'David'},
        {'$addToSet': {'tags': 'python'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python']


def test_addToSet_with_dict(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'items': [{'id': 1, 'name': 'a'}]})
    
    # Try to add duplicate dict
    result = db.update_one(
        {'name': 'David'},
        {'$addToSet': {'items': {'id': 1, 'name': 'a'}}}
    )
    assert result.modified_count == 0  # Duplicate, not added
    
    # Add unique dict
    result = db.update_one(
        {'name': 'David'},
        {'$addToSet': {'items': {'id': 2, 'name': 'b'}}}
    )
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert len(updated['items']) == 2
    assert {'id': 2, 'name': 'b'} in updated['items']


# ============== ARRAY OPERATORS: $pop TESTS ==============

def test_pop_remove_last(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust', 'golang']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pop': {'tags': 1}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'rust']


def test_pop_remove_first(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust', 'golang']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pop': {'tags': -1}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['rust', 'golang']


def test_pop_empty_array(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': []})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pop': {'tags': 1}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 0  # No change
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == []


def test_pop_multiple_times(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['a', 'b', 'c']})
    
    db.update_one({'name': 'David'}, {'$pop': {'tags': 1}})  # Remove 'c'
    db.update_one({'name': 'David'}, {'$pop': {'tags': -1}})  # Remove 'a'
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['b']


# ============== ARRAY OPERATORS: $pullAll TESTS ==============

def test_pullAll_single_value(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust', 'golang']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pullAll': {'tags': ['rust']}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'golang']


def test_pullAll_multiple_values(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust', 'golang', 'java']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pullAll': {'tags': ['rust', 'java']}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'golang']


def test_pullAll_nonexistent_values(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pullAll': {'tags': ['golang', 'java']}}
    )
    assert result.matched_count == 1
    assert result.modified_count == 0
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'rust']


# ============== COMBINED ARRAY OPERATORS TESTS ==============

def test_combined_push_and_pull(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust']})
    
    result = db.update_one(
        {'name': 'David'},
        {'$push': {'tags': 'golang'}, '$pull': {'tags': 'rust'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['python', 'golang']


def test_combined_addToSet_and_pop(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['python', 'rust']})
    
    db.update_one({'name': 'David'}, {'$addToSet': {'tags': 'golang'}})
    db.update_one({'name': 'David'}, {'$pop': {'tags': -1}})
    
    updated = db.find_one({'name': 'David'})
    assert updated['tags'] == ['rust', 'golang']


def test_combined_all_array_operators(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'tags': ['a', 'b', 'c'], 'scores': [80, 90, 100]})
    
    result = db.update_one(
        {'name': 'David'},
        {
            '$push': {'tags': 'd'},
            '$pull': {'scores': {'$lt': 85}},
            '$addToSet': {'tags': 'e'},
            '$pop': {'tags': -1},
            '$pullAll': {'tags': ['b']}
        }
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    # tags: ['a', 'b', 'c'] -> push 'd' -> ['a', 'b', 'c', 'd']
    #       -> addToSet 'e' -> ['a', 'b', 'c', 'd', 'e']
    #       -> pop -1 (first) -> ['b', 'c', 'd', 'e']
    #       -> pullAll ['b'] -> ['c', 'd', 'e']
    assert updated['tags'] == ['c', 'd', 'e']
    # scores: [80, 90, 100] -> pull <$lt: 85> -> [90, 100]
    assert updated['scores'] == [90, 100]


# ============== ARRAY OPERATORS WITH NESTED FIELDS ==============

def test_push_nested_array(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'profile': {'tags': ['python']}})
    
    result = db.update_one(
        {'name': 'David'},
        {'$push': {'profile.tags': 'rust'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['profile']['tags'] == ['python', 'rust']


def test_pull_nested_array(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'profile': {'tags': ['python', 'rust', 'golang']}})
    
    result = db.update_one(
        {'name': 'David'},
        {'$pull': {'profile.tags': 'rust'}}
    )
    assert result.matched_count == 1
    
    updated = db.find_one({'name': 'David'})
    assert updated['profile']['tags'] == ['python', 'golang']


def test_addToSet_nested_array(temp_db):
    db, _ = temp_db
    db.insert_one({'name': 'David', 'profile': {'tags': ['python']}})
    
    db.update_one({'name': 'David'}, {'$addToSet': {'profile.tags': 'rust'}})
    db.update_one({'name': 'David'}, {'$addToSet': {'profile.tags': 'python'}})  # Duplicate
    
    updated = db.find_one({'name': 'David'})
    assert updated['profile']['tags'] == ['python', 'rust']
