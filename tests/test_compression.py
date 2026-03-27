"""Test compression support in JSONlite."""

import os
import tempfile
import pytest
from jsonlite import JSONlite, MongoClient


class TestCompression:
    """Test gzip compression functionality."""
    
    def test_compression_enabled_saves_compressed_file(self):
        """Test that enabling compression creates a gzip file."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create database with compression enabled
            db = JSONlite(filename, compression_enabled=True)
            db.insert_one({"name": "Alice", "age": 30})
            
            # Check file starts with gzip magic number
            with open(filename, 'rb') as f:
                magic = f.read(2)
                assert magic == b'\x1f\x8b', "File should start with gzip magic number"
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_compression_disabled_saves_uncompressed_file(self):
        """Test that disabling compression creates a regular JSON file."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create database with compression disabled (default)
            db = JSONlite(filename, compression_enabled=False)
            db.insert_one({"name": "Bob", "age": 25})
            
            # Check file starts with '{' (JSON)
            with open(filename, 'rb') as f:
                first_byte = f.read(1)
                assert first_byte == b'{', "Uncompressed file should start with '{'"
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_compression_read_write_roundtrip(self):
        """Test that compressed data can be read back correctly."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create database with compression
            db = JSONlite(filename, compression_enabled=True)
            
            # Insert test data
            test_data = {
                "name": "Charlie",
                "age": 35,
                "email": "charlie@example.com",
                "active": True
            }
            db.insert_one(test_data)
            
            # Read back and verify
            result = db.find_one({"name": "Charlie"})
            assert result is not None
            assert result["name"] == "Charlie"
            assert result["age"] == 35
            assert result["email"] == "charlie@example.com"
            assert result["active"] is True
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_compression_level_affects_size(self):
        """Test that different compression levels affect file size."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f1:
            filename1 = f1.name
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f2:
            filename2 = f2.name
        
        try:
            # Create database with level 1 (fastest)
            db1 = JSONlite(filename1, compression_enabled=True, compression_level=1)
            for i in range(100):
                db1.insert_one({"id": i, "data": "x" * 100})
            
            # Create database with level 9 (best compression)
            db2 = JSONlite(filename2, compression_enabled=True, compression_level=9)
            for i in range(100):
                db2.insert_one({"id": i, "data": "x" * 100})
            
            # Level 9 should produce smaller file
            size1 = os.path.getsize(filename1)
            size2 = os.path.getsize(filename2)
            assert size2 <= size1, "Level 9 compression should be at least as good as level 1"
        finally:
            if os.path.exists(filename1):
                os.unlink(filename1)
            if os.path.exists(filename2):
                os.unlink(filename2)
    
    def test_compression_with_special_types(self):
        """Test compression works with datetime, decimal, binary types."""
        from datetime import datetime
        from decimal import Decimal
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, compression_enabled=True)
            
            # Insert document with special types
            test_doc = {
                "name": "Test",
                "created": datetime(2026, 3, 27, 10, 30, 0),
                "price": Decimal("99.99"),
                "data": b"binary data here"
            }
            db.insert_one(test_doc)
            
            # Read back and verify
            result = db.find_one({"name": "Test"})
            assert result is not None
            assert result["name"] == "Test"
            assert result["created"] == datetime(2026, 3, 27, 10, 30, 0)
            assert result["price"] == Decimal("99.99")
            assert result["data"] == b"binary data here"
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_compression_with_many_records(self):
        """Test compression with a larger dataset."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, compression_enabled=True)
            
            # Insert 1000 records
            for i in range(1000):
                db.insert_one({
                    "id": i,
                    "name": f"User {i}",
                    "email": f"user{i}@example.com",
                    "score": i * 10
                })
            
            # Verify count
            count = db.count_documents({})
            assert count == 1000
            
            # Verify we can query
            result = db.find_one({"id": 500})
            assert result is not None
            assert result["name"] == "User 500"
            
            # Check file size is reasonable (compressed)
            size = os.path.getsize(filename)
            # 1000 records uncompressed would be much larger
            assert size < 500000, f"Compressed file should be under 500KB, got {size}"
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_compression_with_indexes(self):
        """Test compression works with indexes."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, compression_enabled=True)
            
            # Create index
            db.create_index("name")
            
            # Insert data
            for i in range(50):
                db.insert_one({"name": f"Name{i}", "value": i})
            
            # Query should use index
            result = db.find_one({"name": "Name25"})
            assert result is not None
            assert result["value"] == 25
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_compression_with_queries(self):
        """Test that all query operators work with compression."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, compression_enabled=True)
            
            # Insert test data
            for i in range(10):
                db.insert_one({
                    "name": f"User{i}",
                    "age": 20 + i,
                    "score": i * 10,
                    "tags": ["tag1", "tag2"] if i % 2 == 0 else ["tag3"]
                })
            
            # Test various query operators
            # $gt
            results = db.find({"age": {"$gt": 25}}).toArray()
            assert len(results) == 4
            
            # $in
            results = db.find({"name": {"$in": ["User0", "User5"]}}).toArray()
            assert len(results) == 2
            
            # $regex
            results = db.find({"name": {"$regex": "User[0-2]"}}).toArray()
            assert len(results) == 3
            
            # Sort and limit
            results = db.find({}).sort("age", -1).limit(3).toArray()
            assert len(results) == 3
            assert results[0]["age"] > results[1]["age"] > results[2]["age"]
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_mongo_client_with_compression(self):
        """Test MongoClient with compression enabled."""
        with tempfile.TemporaryDirectory() as data_dir:
            # Create client with compression
            client = MongoClient(data_dir, compression_enabled=True, compression_level=6)
            
            # Get database and collection
            db = client['testdb']
            collection = db['users']
            
            # Insert data
            collection.insert_one({"name": "Alice", "age": 30})
            collection.insert_one({"name": "Bob", "age": 25})
            
            # Verify data
            result = collection.find_one({"name": "Alice"})
            assert result is not None
            assert result["name"] == "Alice"
            
            # Check file is compressed
            collection_file = os.path.join(data_dir, 'testdb', 'users.json')
            with open(collection_file, 'rb') as f:
                magic = f.read(2)
                assert magic == b'\x1f\x8b', "Collection file should be compressed"


class TestCompressionDetection:
    """Test automatic detection of compressed vs uncompressed files."""
    
    def test_read_compressed_file_created_without_compression(self):
        """Test reading a file created with compression, then read without compression flag."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create with compression
            db1 = JSONlite(filename, compression_enabled=True)
            db1.insert_one({"name": "Test", "value": 123})
            
            # Read without compression flag - should auto-detect
            db2 = JSONlite(filename, compression_enabled=False)
            result = db2.find_one({"name": "Test"})
            assert result is not None
            assert result["value"] == 123
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_read_uncompressed_file_created_with_compression_disabled(self):
        """Test reading a file created without compression, then read with compression flag."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create without compression
            db1 = JSONlite(filename, compression_enabled=False)
            db1.insert_one({"name": "Test", "value": 456})
            
            # Read with compression flag - should auto-detect uncompressed
            db2 = JSONlite(filename, compression_enabled=True)
            result = db2.find_one({"name": "Test"})
            assert result is not None
            assert result["value"] == 456
        finally:
            if os.path.exists(filename):
                os.unlink(filename)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
