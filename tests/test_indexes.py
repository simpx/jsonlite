"""Test suite for JSONlite index functionality."""

import pytest
import os
import tempfile
from jsonlite import JSONlite


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    db = JSONlite(path)
    yield db
    os.unlink(path)


@pytest.fixture
def populated_db(db):
    """Create a database with test data."""
    test_data = [
        {"name": "Alice", "age": 25, "city": "NYC", "score": 85},
        {"name": "Bob", "age": 30, "city": "LA", "score": 90},
        {"name": "Charlie", "age": 25, "city": "NYC", "score": 75},
        {"name": "Diana", "age": 35, "city": "Chicago", "score": 95},
        {"name": "Eve", "age": 28, "city": "LA", "score": 88},
    ]
    for record in test_data:
        db.insert_one(record)
    return db


class TestIndexCreation:
    """Test index creation functionality."""
    
    def test_create_single_field_index(self, populated_db):
        """Test creating a single-field index."""
        index_name = populated_db.create_index("age")
        assert index_name == "age_1"
        
        indexes = populated_db.list_indexes()
        assert len(indexes) == 1
        assert indexes[0]['name'] == "age_1"
        assert indexes[0]['keys'] == [("age", 1)]
        assert indexes[0]['unique'] is False
        assert indexes[0]['sparse'] is False
    
    def test_create_index_with_custom_name(self, populated_db):
        """Test creating an index with a custom name."""
        index_name = populated_db.create_index("age", name="custom_age_idx")
        assert index_name == "custom_age_idx"
        
        indexes = populated_db.list_indexes()
        assert len(indexes) == 1
        assert indexes[0]['name'] == "custom_age_idx"
    
    def test_create_compound_index(self, populated_db):
        """Test creating a compound (multi-field) index."""
        index_name = populated_db.create_index([("age", 1), ("city", -1)])
        assert index_name == "age_1_city_-1"
        
        indexes = populated_db.list_indexes()
        assert len(indexes) == 1
        assert indexes[0]['keys'] == [("age", 1), ("city", -1)]
    
    def test_create_unique_index(self, db):
        """Test creating a unique index."""
        db.insert_one({"email": "alice@example.com"})
        db.insert_one({"email": "bob@example.com"})
        
        index_name = db.create_index("email", unique=True)
        assert index_name == "email_1"
        
        # Try to insert duplicate
        with pytest.raises(ValueError, match="Duplicate key error"):
            db.insert_one({"email": "alice@example.com"})
    
    def test_create_sparse_index(self, db):
        """Test creating a sparse index."""
        db.insert_one({"name": "Alice", "age": 25})
        db.insert_one({"name": "Bob"})  # No age field
        db.insert_one({"name": "Charlie", "age": 30})
        
        index_name = db.create_index("age", sparse=True)
        indexes = db.list_indexes()
        assert indexes[0]['sparse'] is True
        
        # Query should only return documents with the field
        results = db.find({"age": 25}).all()
        assert len(results) == 1
        assert results[0]['name'] == "Alice"
    
    def test_duplicate_index_name_error(self, populated_db):
        """Test error when creating duplicate index name."""
        populated_db.create_index("age")
        
        with pytest.raises(ValueError, match="already exists"):
            populated_db.create_index("age", name="age_1")


class TestIndexDrop:
    """Test index dropping functionality."""
    
    def test_drop_index(self, populated_db):
        """Test dropping a specific index."""
        populated_db.create_index("age")
        assert len(populated_db.list_indexes()) == 1
        
        result = populated_db.drop_index("age_1")
        assert result is True
        assert len(populated_db.list_indexes()) == 0
    
    def test_drop_nonexistent_index(self, populated_db):
        """Test dropping an index that doesn't exist."""
        result = populated_db.drop_index("nonexistent")
        assert result is False
    
    def test_drop_all_indexes(self, populated_db):
        """Test dropping all indexes."""
        populated_db.create_index("age")
        populated_db.create_index("city")
        populated_db.create_index("score")
        assert len(populated_db.list_indexes()) == 3
        
        count = populated_db.drop_indexes()
        assert count == 3
        assert len(populated_db.list_indexes()) == 0


class TestIndexQuery:
    """Test index-accelerated queries."""
    
    def test_query_with_index(self, populated_db):
        """Test that queries use indexes when available."""
        populated_db.create_index("age")
        
        # Query should use index
        results = populated_db.find({"age": 25}).all()
        assert len(results) == 2
        names = {r['name'] for r in results}
        assert names == {"Alice", "Charlie"}
    
    def test_query_without_index(self, populated_db):
        """Test that queries work without indexes (full scan)."""
        results = populated_db.find({"age": 25}).all()
        assert len(results) == 2
        names = {r['name'] for r in results}
        assert names == {"Alice", "Charlie"}
    
    def test_index_maintained_after_insert(self, populated_db):
        """Test that indexes are updated on insert."""
        populated_db.create_index("age")
        
        # Insert new document
        populated_db.insert_one({"name": "Frank", "age": 25, "city": "Boston"})
        
        # Query should find the new document
        results = populated_db.find({"age": 25}).all()
        assert len(results) == 3
        names = {r['name'] for r in results}
        assert "Frank" in names
    
    def test_index_maintained_after_update(self, populated_db):
        """Test that indexes are updated on update."""
        populated_db.create_index("age")
        
        # Update Alice's age
        populated_db.update_one({"name": "Alice"}, {"$set": {"age": 26}})
        
        # Query old value should return 1 result (Charlie)
        results = populated_db.find({"age": 25}).all()
        assert len(results) == 1
        assert results[0]['name'] == "Charlie"
        
        # Query new value should return 1 result (Alice)
        results = populated_db.find({"age": 26}).all()
        assert len(results) == 1
        assert results[0]['name'] == "Alice"
    
    def test_index_maintained_after_delete(self, populated_db):
        """Test that indexes are updated on delete."""
        populated_db.create_index("age")
        
        # Delete Alice
        populated_db.delete_one({"name": "Alice"})
        
        # Query should only return Charlie
        results = populated_db.find({"age": 25}).all()
        assert len(results) == 1
        assert results[0]['name'] == "Charlie"


class TestUniqueIndex:
    """Test unique index constraints."""
    
    def test_unique_index_prevents_duplicates(self, db):
        """Test that unique index prevents duplicate values."""
        db.insert_one({"email": "test@example.com"})
        db.create_index("email", unique=True)
        
        with pytest.raises(ValueError, match="Duplicate key"):
            db.insert_one({"email": "test@example.com"})
    
    def test_unique_index_on_update(self, db):
        """Test that unique index is enforced on update."""
        db.insert_one({"email": "alice@example.com", "name": "Alice"})
        db.insert_one({"email": "bob@example.com", "name": "Bob"})
        db.create_index("email", unique=True)
        
        # Try to update Bob to have Alice's email
        with pytest.raises(ValueError, match="Duplicate key"):
            db.update_one({"name": "Bob"}, {"$set": {"email": "alice@example.com"}})


class TestCompoundIndex:
    """Test compound (multi-field) indexes."""
    
    def test_compound_index_creation(self, populated_db):
        """Test creating and using compound index."""
        index_name = populated_db.create_index([("city", 1), ("age", -1)])
        assert index_name == "city_1_age_-1"
        
        indexes = populated_db.list_indexes()
        assert len(indexes) == 1
        assert indexes[0]['keys'] == [("city", 1), ("age", -1)]
    
    def test_compound_index_maintenance(self, populated_db):
        """Test that compound indexes are maintained."""
        populated_db.create_index([("city", 1), ("age", -1)])
        
        # Insert new document
        populated_db.insert_one({"name": "Frank", "age": 40, "city": "NYC"})
        
        # Verify index exists
        indexes = populated_db.list_indexes()
        assert len(indexes) == 1


class TestIndexPersistence:
    """Test that indexes work correctly with database operations."""
    
    def test_index_with_full_scan_fallback(self, populated_db):
        """Test that queries work even when index doesn't cover the field."""
        populated_db.create_index("age")
        
        # Query on non-indexed field should still work
        results = populated_db.find({"city": "NYC"}).all()
        assert len(results) == 2
        names = {r['name'] for r in results}
        assert names == {"Alice", "Charlie"}
    
    def test_multiple_indexes(self, populated_db):
        """Test database with multiple indexes."""
        populated_db.create_index("age")
        populated_db.create_index("city")
        populated_db.create_index("score", unique=False)
        
        indexes = populated_db.list_indexes()
        assert len(indexes) == 3
        
        # Query should work with multiple indexes
        results = populated_db.find({"age": 25}).all()
        assert len(results) == 2
        
        results = populated_db.find({"city": "LA"}).all()
        assert len(results) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
