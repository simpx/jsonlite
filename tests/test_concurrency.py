import unittest
import tempfile
import os
import signal
import re
import time
import random
import multiprocessing
from jsonlite import JSONlite

def mod(value, a, b):
    return value is not None and value % a == b

def is_multiple_of(value, match_value):
    return value is not None and value % match_value == 0

def is_between(value, min_value, max_value):
    return min_value < value < max_value

class TestJSONliteConcurrency(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8")
        self.filename = self.temp_file.name
        self.db = JSONlite(self.filename)

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
    
    @staticmethod
    def multi_insert(filename, records):
        db = JSONlite(filename)
        db.insert_many(records)

    @staticmethod
    def multi_read(filename):
        db = JSONlite(filename)
        time.sleep(1)  # Ensuring some reads happen after some writes
        result = db.find({})
        return len(result)

    def test_concurrent_writes(self):
        records1 = [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}]
        records2 = [{'name': 'Charlie', 'age': 20}, {'name': 'David', 'age': 40}]

        p1 = multiprocessing.Process(target=TestJSONliteConcurrency.multi_insert, args=(self.filename, records1))
        p2 = multiprocessing.Process(target=TestJSONliteConcurrency.multi_insert, args=(self.filename, records2))
        
        p1.start()
        p2.start()
        
        p1.join()
        p2.join()

        result = self.db.find({})
        self.assertEqual(len(result), 4)
        for record in result:
            self.assertIn(record['name'], [r['name'] for r in records1+records2])
    
    def test_concurrent_reads(self):
        records = [
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 20}
        ]
        self.db.insert_many(records)

        processes = [multiprocessing.Process(target=TestJSONliteConcurrency.multi_read, args=(self.filename,)) for _ in range(10)]
        
        for p in processes:
            p.start()
        
        for p in processes:
            p.join()
        
        result = self.db.find({})
        self.assertEqual(len(result), 3)
    
    def test_read_while_writing(self):
        records = [
            {'name': 'Alice', 'age': 30}, 
            {'name': 'Bob', 'age': 25}
        ]
        self.db.insert_many(records)

        records_to_insert = [
            {'name': 'Charlie', 'age': 20}, 
            {'name': 'David', 'age': 40}
        ]

        p_write = multiprocessing.Process(target=TestJSONliteConcurrency.multi_insert, args=(self.filename, records_to_insert))
        p_read = multiprocessing.Process(target=TestJSONliteConcurrency.multi_read, args=(self.filename,))

        p_write.start()
        p_read.start()
        
        p_write.join()
        p_read.join()
        
        result = self.db.find({})
        self.assertIn(len(result), [2, 4])  # Depending on timing, there might be a temporary state
    
    @staticmethod
    def multi_read_with_sleep(filename):
        db = JSONlite(filename)
        result = db.find({})
        time.sleep(2)
        return len(result)

    def test_write_while_reading(self):


        records = [
            {'name': 'Alice', 'age': 30}, 
            {'name': 'Bob', 'age': 25}
        ]
        self.db.insert_many(records)

        records_to_insert = [
            {'name': 'Charlie', 'age': 20}, 
            {'name': 'David', 'age': 40}
        ]

        p_write = multiprocessing.Process(target=TestJSONliteConcurrency.multi_insert, args=(self.filename, records_to_insert))
        p_read = multiprocessing.Process(target=TestJSONliteConcurrency.multi_read_with_sleep, args=(self.filename,))

        p_read.start()
        time.sleep(1)  # Start the write half-way through the read process
        p_write.start()
        
        p_read.join()
        p_write.join()
        
        result = self.db.find({})
        self.assertEqual(len(result), 4)  # Reading should be eventually consistent with all writes

    @staticmethod
    def insert_records(filename, n):
        db = JSONlite(filename)
        for i in range(n):
            db.insert_one({'name': f'Record{i}', 'value': random.randint(1, 100)})

    @staticmethod
    def read_records(filename):
        db = JSONlite(filename)
        while True:
            records = db.find()
            # 简单的合法性检查：确保所有记录都有 'name' 和 'value'
            for record in records:
                assert 'name' in record and 'value' in record
            time.sleep(random.uniform(0.1, 0.5))  # 延迟以模拟不间断读取

    def start_and_kill_processes(self, process_count, record_count):
        insert_processes = []
        read_processes = []

        # 启动插入进程
        for _ in range(process_count):
            p_insert = multiprocessing.Process(target=TestJSONliteConcurrency.insert_records, args=(self.filename, record_count))
            p_insert.start()
            insert_processes.append(p_insert)

        # 启动读取进程
        for _ in range(process_count // 2):  # 例如：读取进程数量是插入进程数量的一半
            p_read = multiprocessing.Process(target=TestJSONliteConcurrency.read_records, args=(self.filename,))
            p_read.start()
            read_processes.append(p_read)

        # 随机杀死一些插入进程
        time.sleep(random.uniform(0.1, 1.0))  # 随机等待时间以确保插入操作正在进行
        for p in insert_processes:
            if random.choice([True, False]):  # 仅随机杀死插入进程
                os.kill(p.pid, signal.SIGKILL)

        # 等待所有进程结束
        for p in insert_processes:
            p.join()

        for p in read_processes:
            p.terminate()
            p.join()

    def test_failover_scenario(self):
        process_count = 10
        record_count = 1000

        # 插入一些初始数据
        initial_records = [{'name': 'Alice', 'value': 30}, {'name': 'Bob', 'value': 25}]
        db = JSONlite(self.filename)
        db.insert_many(initial_records)

        # 启动进程并随机杀死
        self.start_and_kill_processes(process_count, record_count)

        # 检查记录数量是否合理
        result = JSONlite(self.filename).find()
        total_records_expectation = len(initial_records) + (process_count * record_count)
        self.assertLessEqual(len(result), total_records_expectation)
        for record in result:
            self.assertIn('name', record)
            self.assertIn('value', record)

if __name__ == '__main__':
    unittest.main()