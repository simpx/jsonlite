import unittest
import tempfile
import os
import timeit
import re
from jsonlite import JSONlite

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

    def _measure_performance(self, query_function, num_iterations=1, *args, **kwargs):
        total_time = 0
        start_time = timeit.default_timer()
        for _ in range(num_iterations):
            query_function(*args, **kwargs)
        end_time = timeit.default_timer()
        return (end_time - start_time) / num_iterations

    def test_performance(self):
        records = [{'name': f'User{i}', 'age': i % 100} for i in range(100)]
        self.db.insert_many(records)

        # Test Insert Performance
        single_insert_time = self._measure_performance(self.db.insert_one, 100, {'name': 'SingleUser', 'age': 30}) * 1000
        print(f"Insert One Record Average Time: {single_insert_time:.6f} ms")
        multiple_insert_time = self._measure_performance(self.db.insert_many, 10, records) * 1000
        print(f"Insert Multiple Records Average Time: {multiple_insert_time:.6f} ms")

        # Test Find Performance
        find_single_time = self._measure_performance(self.db.find, 100, {'name': 'User10'}) * 1000
        print(f"Find Single Record Average Time: {find_single_time:.6f} ms")
        find_multiple_time = self._measure_performance(self.db.find, 10, {'age': {"$gt": 50}}) * 1000
        print(f"Find Multiple Records Average Time: {find_multiple_time:.6f} ms")

        # Test Update Performance
        update_single_time = self._measure_performance(self.db.update_one, 100, {'name': 'Alice'}, {'$set': {'age': 31}}) * 1000
        print(f"Update One Record Average Time: {update_single_time:.6f} ms")
        update_multiple_time = self._measure_performance(self.db.update_many, 10, {'age': {"$gt": 50}}, {'$set': {'name': 'Updated'}}) * 1000
        print(f"Update Multiple Records Average Time: {update_multiple_time:.6f} ms")

        # Test Delete Performance
        delete_single_time = self._measure_performance(self.db.delete_one, 100, {'name': 'Alice'}) * 1000
        print(f"Delete One Record Average Time: {delete_single_time:.6f} ms")
        delete_all_time = self._measure_performance(self.db.delete_many, 100, {}) * 1000
        print(f"Delete All Records Average Time: {delete_all_time:.6f} ms")

if __name__ == '__main__':
    unittest.main()