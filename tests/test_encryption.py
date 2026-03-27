"""Test encryption support in JSONlite."""

import os
import tempfile
import pytest
from jsonlite import JSONlite, MongoClient


class TestEncryption:
    """Test AES-256-GCM encryption functionality."""
    
    def test_encryption_enabled_saves_encrypted_file(self):
        """Test that enabling encryption creates an encrypted file."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create database with encryption enabled
            db = JSONlite(filename, encryption_enabled=True, encryption_password="secret123")
            db.insert_one({"name": "Alice", "age": 30})
            
            # Check file starts with encryption magic number
            with open(filename, 'rb') as f:
                magic = f.read(4)
                assert magic == b'ENCR', "File should start with ENCR magic number"
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_encryption_disabled_saves_unencrypted_file(self):
        """Test that disabling encryption creates a regular JSON file."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create database with encryption disabled (default)
            db = JSONlite(filename, encryption_enabled=False)
            db.insert_one({"name": "Bob", "age": 25})
            
            # Check file starts with '{' (JSON)
            with open(filename, 'rb') as f:
                first_byte = f.read(1)
                assert first_byte == b'{', "Unencrypted file should start with '{'"
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_encryption_read_write_roundtrip(self):
        """Test that encrypted data can be read back correctly."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create database with encryption
            db = JSONlite(filename, encryption_enabled=True, encryption_password="mypassword")
            
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
    
    def test_encryption_requires_password(self):
        """Test that encryption_enabled without password raises error."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            with pytest.raises(ValueError, match="encryption_password is required"):
                JSONlite(filename, encryption_enabled=True)
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_wrong_password_fails_decryption(self):
        """Test that wrong password fails to decrypt."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create with one password
            db1 = JSONlite(filename, encryption_enabled=True, encryption_password="correct_password")
            db1.insert_one({"name": "Test", "value": 123})
            
            # Try to read with wrong password
            with pytest.raises(ValueError, match="Decryption failed"):
                db2 = JSONlite(filename, encryption_enabled=True, encryption_password="wrong_password")
                db2.find_one({"name": "Test"})
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_encryption_with_special_types(self):
        """Test encryption works with datetime, decimal, binary types."""
        from datetime import datetime
        from decimal import Decimal
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, encryption_enabled=True, encryption_password="test123")
            
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
    
    def test_encryption_with_compression(self):
        """Test that encryption and compression can be used together."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create database with both compression and encryption
            db = JSONlite(
                filename,
                compression_enabled=True,
                compression_level=6,
                encryption_enabled=True,
                encryption_password="compress_and_encrypt"
            )
            
            # Insert test data with repetitive content (compresses well)
            for i in range(50):
                db.insert_one({
                    "id": i,
                    "name": f"User {i}",
                    "description": "This is a test description that repeats" * 10
                })
            
            # Read back and verify
            count = db.count_documents({})
            assert count == 50
            
            result = db.find_one({"id": 25})
            assert result is not None
            assert result["name"] == "User 25"
            
            # Check file starts with encryption magic (encryption wraps compression)
            with open(filename, 'rb') as f:
                magic = f.read(4)
                assert magic == b'ENCR', "Encrypted+compressed file should start with ENCR"
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_encryption_with_indexes(self):
        """Test encryption works with indexes."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, encryption_enabled=True, encryption_password="index_test")
            
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
    
    def test_encryption_with_queries(self):
        """Test that all query operators work with encryption."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, encryption_enabled=True, encryption_password="query_test")
            
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
    
    def test_encryption_with_many_records(self):
        """Test encryption with a larger dataset."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, encryption_enabled=True, encryption_password="bulk_test")
            
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
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_encryption_with_update_operators(self):
        """Test encryption works with update operations."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, encryption_enabled=True, encryption_password="update_test")
            
            # Insert document
            db.insert_one({"name": "Alice", "age": 30, "score": 100})
            
            # Update with $set
            db.update_one({"name": "Alice"}, {"$set": {"age": 31}})
            result = db.find_one({"name": "Alice"})
            assert result["age"] == 31
            
            # Update with $inc
            db.update_one({"name": "Alice"}, {"$inc": {"score": 10}})
            result = db.find_one({"name": "Alice"})
            assert result["score"] == 110
            
            # Update with $push
            db.update_one({"name": "Alice"}, {"$push": {"tags": "admin"}})
            result = db.find_one({"name": "Alice"})
            assert "admin" in result["tags"]
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_encryption_with_aggregation(self):
        """Test encryption works with aggregation pipeline."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            db = JSONlite(filename, encryption_enabled=True, encryption_password="agg_test")
            
            # Insert test data
            for i in range(10):
                db.insert_one({
                    "category": "A" if i % 2 == 0 else "B",
                    "value": i * 10
                })
            
            # Run aggregation
            pipeline = [
                {"$group": {"_id": "$category", "total": {"$sum": "$value"}}}
            ]
            results = db.aggregate(pipeline)
            
            assert len(results) == 2
            totals = {r["_id"]: r["total"] for r in results}
            assert totals["A"] == 0 + 20 + 40 + 60 + 80  # 200
            assert totals["B"] == 10 + 30 + 50 + 70 + 90  # 250
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_mongo_client_with_encryption(self):
        """Test MongoClient with encryption enabled."""
        with tempfile.TemporaryDirectory() as data_dir:
            # Create client with encryption
            client = MongoClient(
                data_dir,
                encryption_enabled=True,
                encryption_password="mongo_test"
            )
            
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
            
            # Check file is encrypted
            collection_file = os.path.join(data_dir, 'testdb', 'users.json')
            with open(collection_file, 'rb') as f:
                magic = f.read(4)
                assert magic == b'ENCR', "Collection file should be encrypted"


class TestEncryptionDetection:
    """Test automatic detection of encrypted vs unencrypted files."""
    
    def test_read_encrypted_file_without_password_fails(self):
        """Test reading an encrypted file without password raises error."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create with encryption
            db1 = JSONlite(filename, encryption_enabled=True, encryption_password="secret")
            db1.insert_one({"name": "Test", "value": 123})
            
            # Try to read without password
            with pytest.raises(ValueError, match="File is encrypted but no encryption_password"):
                db2 = JSONlite(filename, encryption_enabled=False)
                db2.find_one({"name": "Test"})
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_read_unencrypted_file_with_password_flag(self):
        """Test reading an unencrypted file with encryption flag fails gracefully."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Create without encryption
            db1 = JSONlite(filename, encryption_enabled=False)
            db1.insert_one({"name": "Test", "value": 456})
            
            # Try to read with encryption flag - should detect it's not encrypted
            # and either work or fail gracefully
            db2 = JSONlite(filename, encryption_enabled=True, encryption_password="test")
            # This should work because we detect it's not encrypted
            result = db2.find_one({"name": "Test"})
            # If we get here, the file was read as unencrypted
            assert result is not None
            assert result["value"] == 456
        except ValueError as e:
            # It's also acceptable if it fails with a clear error
            assert "not encrypted" in str(e).lower() or "magic" in str(e).lower()
        finally:
            if os.path.exists(filename):
                os.unlink(filename)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
