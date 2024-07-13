import unittest
import tempfile
import os
import re
from jsonlite import JSONlite
from parameterized import parameterized

def mod(value, a, b):
    return value is not None and value % a == b
def is_multiple_of(value, match_value):
    return value is not None and value % match_value == 0

def is_between(value, min_value, max_value):
    return min_value < value < max_value

class TestJSONlite(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8")
        self.filename = self.temp_file.name
        self.db = JSONlite(self.filename)
        self.db2 = JSONlite(self.filename)
        self.db.insert_many([
            {'name': 'Alice', 'age': 30}, #
            {'name': 'Bob', 'age': 25}, #
            {'name': 'Charlie', 'age': 20}, #
            {"name": "David", "age": 40, "value": 2},
            {"name": "Eve", "age": None, "value": 2}, #
            {"name": "Frank"}  # Missing age
            ])

    def tearDown(self):
        try:
            self.temp_file.close()
            os.remove(self.filename)
        except OSError as e:
            print(f"Error: {e.strerror}")
    
    def assertEqualWithoutId(self, a, b):
        def remove_id_fields(d):
            if isinstance(d, dict):
                return {k: remove_id_fields(v) for k, v in d.items() if k != '_id'}
            elif isinstance(d, list):
                return [remove_id_fields(x) for x in d]
            else:
                return d
        self.assertEqual(remove_id_fields(a), remove_id_fields(b))
    
    def test_new_db(self):
        filename = 'jsondb_test_db2.json'
        db = JSONlite(filename)
        self.assertEqual(os.path.exists(filename), True)
        os.remove(filename)

    def test_insert_one(self):
        record = {'name': 'Tom', 'age': 10}
        result = self.db.insert_one(record)

        found = self.db2.find_one({'_id': result.inserted_id})
        self.assertEqualWithoutId(found, record)
    
    def test_insert_with_id(self):
        record = {'_id': 10, 'name': 'Dave', 'age': 40}
        with self.assertRaises(ValueError) as context:
            self.db.insert_one(record)
        self.assertEqual(str(context.exception), "ID should not be specified. It is auto-generated.")

    def test_insert_many(self):
        records = [
            {'name': 'Ann', 'age': 80},
            {'name': 'Jim', 'age': 15}
        ]
        result = self.db.insert_many(records)
        found = self.db2.find({"$or":[{"_id": inserted_id} for inserted_id in result.inserted_ids]})
        self.assertEqualWithoutId(records, found)

    def test_find_one(self):
        result = self.db.find_one({'name': 'Alice'})
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Alice')

    def test_find(self):
        result = self.db.find({'name': 'Alice'})
        self.assertEqual(len(result), 1)
        for record in result:
            self.assertEqual(record['name'], 'Alice')

    @parameterized.expand([
        ("all", {}, 6, lambda r: True),
        ("nonexists", {'name': 'Nonexistent'}, 0, lambda r: False),
        ("gt", {'age': {"$gt": 20}}, 3, lambda r: r["age"] > 20),
        ("mod", {'age': {mod: [2, 1]}}, 1, lambda r: mod(r["age"], 2, 1)),
        ("multiple", {'age': {is_multiple_of: 10}}, 3, lambda r: is_multiple_of(r["age"], 10)),
        ("between", {'age': {"$gt": 10, "$lt": 30}}, 2, lambda r: r["age"] > 10 and r["age"] < 30),
        ("or", {'$or': [{'name': 'Alice'}, {'age': 20}]}, 2, lambda r: r['name'] == 'Alice' or r['age'] == 20),
        ("and", {'$and': [{'name': 'Alice'}, {'age': 30}]}, 1, lambda r: r['name'] == 'Alice' and r['age'] == 30),
        ("nested_or", 
            {'$or':
                [
                    {'name': 'Alice'},
                    {'$and': [{'age': {"$lt": 30}}, {'name': {"$regex": 'lie'}}]}
                ]
            }, 2, lambda r: r['name'] == 'Alice' or (r['age'] < 30 and 'lie' in r['name'])),
        ("nested_or2",
            {'$or':
                [
                    {'name': 'Alice'},
                    {'age': {"$lt": 30}, 'name': {"$regex": 'lie'}}
                ]
            }, 2, lambda r: r['name'] == 'Alice' or (r['age'] < 30 and 'lie' in r['name'])),
        ("exists_true", {'age': {"$exists": True}}, 5, lambda r: 'age' in r),
        ("exists_false", {'age': {"$exists": False}}, 1, lambda r: 'age' not in r),
        ("nested_exists", 
            {'$and': [
                {'age': {"$exists": True}},
                {'$or': [{'value': {"$exists": True}}, {'name': 'Frank'}]}
            ]}, 2, lambda r: ('age' in r ) and (('value' in r) or r['name'] == 'Frank')),
        ("nor",
            {'$nor': [{'age': {"$lt": 30}}, {'name': 'Bob'}]}, 4, 
            lambda r: not (r["age"] < 30 if "age" in r and r["age"] is not None else False) and r['name'] != 'Bob'),
        ("not",
            {'age': {'$not': {'$gt': 30}}}, 5,
            lambda r: not ("age" in r and r["age"] is not None and r["age"] > 30)),
       ("complex_nested",
            {'$and': [
                {'$or': [{'age': {"$exists": True}}, {'age': {"$lt": 40}}]},
                {'$or': [{'value': {"$gt": 2}}, {'name': {"$regex": 'a', "$exists": True}}]}
            ]}, 2, lambda r: (r.get('age') is not None or r.get('age', 0) < 40) and 
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
            ]}, 2, lambda r: (r['age'] > 20 if r.get("age") is not None else False) and (r['name'] == 'Alice' or 'value' in r))
    ])
    def test_find_testsuits(self, name, query, expected_count, condition):
        result = self.db.find(query)
        self.assertEqual(len(result), expected_count)
        for record in result:
            self.assertTrue(condition(record))

    def test_update_one(self):
        found = self.db.find_one({'name': 'Alice'})
        result = self.db.update_one({'name': 'Alice'}, {"$set": {'name': 'Alicia'}})
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.modified_count, 1)

        found2 = self.db2.find_one({'_id': found["_id"]})
        found["name"] = "Alicia"
        self.assertEqual(found, found2)
    
    def test_update_replace(self):
        found = self.db.find_one({'name': 'Alice'})
        result = self.db.update_one({'name': 'Alice'}, {'name': 'Alicia'})
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.modified_count, 1)

        found2 = self.db2.find_one({'_id': found["_id"]})
        self.assertEqualWithoutId({'name': 'Alicia'}, found2)
    
    def test_update_many(self):
        # updated
        result = self.db.update_many({'age': {"$gt": 20}}, {"$set": {'name': 'Alicia'}})
        self.assertEqual(result.matched_count, 3)
        self.assertEqual(result.modified_count, 3)
        found = self.db2.find({'name': 'Alicia'})
        self.assertEqual(len(found), 3)

        # not exists
        result = self.db.update_many({'age': {"$gt": 80}}, {"$set": {'name': 'Alicia'}})
        self.assertEqual(result.matched_count, 0)
        self.assertEqual(result.modified_count, 0)

        # duplicate update
        result = self.db.update_many({'age': {"$lt": 30}}, {"$set": {'name': 'Alicia'}})
        self.assertEqual(result.matched_count, 2)
        self.assertEqual(result.modified_count, 1)

    def test_update_by_id(self):
        record = self.db.find_one({'name': 'Alice', 'age': 30})
        result = self.db.update_one({"_id": record['_id']}, {"$set": {'age': 31}})
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.modified_count, 1)

    def test_delete_one(self):
        result = self.db.delete_one({'name': 'Alice'})
        self.assertEqual(result.deleted_count, 1)

    def test_delete_many(self):
        # delete non-exist
        result = self.db.delete_many({'name': 'Nonexistent'})
        self.assertEqual(result.deleted_count, 0)

        # delete all
        result = self.db.delete_many({})
        self.assertEqual(result.deleted_count, 6)
        self.assertEqual(len(self.db2.find({})), 0)

    def test_delete_by_id(self):
        record = self.db.find_one({'name': 'Alice', 'age': 30})
        result = self.db.delete_one({"_id": record['_id']})
        self.assertEqual(self.db2.find_one({"_id": record['_id']}), None)

if __name__ == '__main__':
    unittest.main()