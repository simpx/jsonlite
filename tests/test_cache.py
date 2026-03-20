"""
Test suite for JSONLite query cache functionality.

Tests cover:
- Cache initialization and configuration
- Cache hits and misses
- Cache invalidation on write operations
- Cache statistics
- Cache with different query types
"""

import pytest
import tempfile
import os
from jsonlite import JSONlite


class TestCacheInit:
    """Test cache initialization and configuration."""
    
    def test_cache_enabled_by_default(self):
        """Cache should be enabled by default."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name)
            assert db._cache_enabled is True
            assert db._cache is not None
            db.clear_cache()
            os.unlink(f.name)
    
    def test_cache_can_be_disabled(self):
        """Cache can be disabled via constructor."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name, cache_enabled=False)
            assert db._cache_enabled is False
            assert db._cache is None
            os.unlink(f.name)
    
    def test_cache_size_configuration(self):
        """Cache size can be configured."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name, cache_size=50)
            assert db._cache._max_size == 50
            db.clear_cache()
            os.unlink(f.name)


class TestCacheHits:
    """Test cache hit/miss behavior."""
    
    @pytest.fixture
    def db(self):
        """Create a test database with sample data."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name)
            # Insert test data
            db.insert_many([
                {'name': 'Alice', 'age': 25, 'city': 'NYC'},
                {'name': 'Bob', 'age': 30, 'city': 'LA'},
                {'name': 'Charlie', 'age': 35, 'city': 'NYC'},
                {'name': 'David', 'age': 40, 'city': 'SF'},
            ])
            yield db
            db.clear_cache()
            os.unlink(db._filename)
    
    def test_cache_miss_then_hit(self, db):
        """First query should miss, second should hit."""
        db.reset_cache_stats()
        
        # First query - should miss
        result1 = db.find({'city': 'NYC'}).all()
        stats1 = db.get_cache_stats()
        assert stats1['misses'] == 1
        assert stats1['hits'] == 0
        
        # Same query - should hit
        result2 = db.find({'city': 'NYC'}).all()
        stats2 = db.get_cache_stats()
        assert stats2['hits'] == 1
        assert stats2['misses'] == 1
        
        # Results should be equal but different objects (deep copy)
        assert len(result1) == len(result2) == 2
        assert result1 is not result2
    
    def test_different_queries_different_cache_entries(self, db):
        """Different queries should have separate cache entries."""
        db.reset_cache_stats()
        
        # Query 1
        db.find({'city': 'NYC'}).all()
        # Query 2
        db.find({'city': 'LA'}).all()
        
        stats = db.get_cache_stats()
        assert stats['misses'] == 2
        assert stats['size'] == 2
    
    def test_cache_returns_deep_copy(self, db):
        """Cached results should be deep copies, not references."""
        result1 = db.find({'name': 'Alice'}).all()
        result2 = db.find({'name': 'Alice'}).all()
        
        # Modify result1
        if result1:
            result1[0]['name'] = 'Modified'
        
        # result2 should be unchanged
        assert result2[0]['name'] == 'Alice'


class TestCacheInvalidation:
    """Test cache invalidation on write operations."""
    
    @pytest.fixture
    def db(self):
        """Create a test database with sample data."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name)
            db.insert_many([
                {'name': 'Alice', 'age': 25},
                {'name': 'Bob', 'age': 30},
            ])
            yield db
            db.clear_cache()
            os.unlink(db._filename)
    
    def test_cache_cleared_on_insert_one(self, db):
        """Cache should be cleared after insert_one."""
        # Populate cache
        db.find({'age': 25}).all()
        assert db.get_cache_stats()['size'] == 1
        
        # Insert should clear cache
        db.insert_one({'name': 'Charlie', 'age': 35})
        assert db.get_cache_stats()['size'] == 0
    
    def test_cache_cleared_on_insert_many(self, db):
        """Cache should be cleared after insert_many."""
        # Populate cache
        db.find({}).all()
        assert db.get_cache_stats()['size'] >= 1
        
        # Insert many should clear cache
        db.insert_many([
            {'name': 'Charlie', 'age': 35},
            {'name': 'David', 'age': 40},
        ])
        assert db.get_cache_stats()['size'] == 0
    
    def test_cache_cleared_on_update(self, db):
        """Cache should be cleared after update operations."""
        # Populate cache
        db.find({'name': 'Alice'}).all()
        assert db.get_cache_stats()['size'] == 1
        
        # Update should clear cache
        db.update_one({'name': 'Alice'}, {'$set': {'age': 26}})
        assert db.get_cache_stats()['size'] == 0
    
    def test_cache_cleared_on_delete(self, db):
        """Cache should be cleared after delete operations."""
        # Populate cache
        db.find({}).all()
        assert db.get_cache_stats()['size'] >= 1
        
        # Delete should clear cache
        db.delete_one({'name': 'Alice'})
        assert db.get_cache_stats()['size'] == 0


class TestCacheStats:
    """Test cache statistics functionality."""
    
    @pytest.fixture
    def db(self):
        """Create a test database."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name, cache_size=10)
            db.insert_many([{'i': i} for i in range(20)])
            yield db
            db.clear_cache()
            os.unlink(db._filename)
    
    def test_stats_structure(self, db):
        """Stats should return expected structure."""
        stats = db.get_cache_stats()
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'size' in stats
        assert 'max_size' in stats
        assert 'hit_rate' in stats
    
    def test_hit_rate_calculation(self, db):
        """Hit rate should be calculated correctly."""
        db.reset_cache_stats()
        
        # 2 misses, 2 hits
        db.find({'i': 1}).all()  # miss
        db.find({'i': 1}).all()  # hit
        db.find({'i': 2}).all()  # miss
        db.find({'i': 2}).all()  # hit
        
        stats = db.get_cache_stats()
        assert stats['hits'] == 2
        assert stats['misses'] == 2
        assert stats['hit_rate'] == 50.0
    
    def test_reset_stats(self, db):
        """Stats can be reset."""
        db.find({'i': 1}).all()
        db.find({'i': 1}).all()
        
        stats_before = db.get_cache_stats()
        assert stats_before['hits'] > 0 or stats_before['misses'] > 0
        
        db.reset_cache_stats()
        stats_after = db.get_cache_stats()
        assert stats_after['hits'] == 0
        assert stats_after['misses'] == 0
        assert stats_after['size'] == stats_before['size']  # Cache content unchanged
    
    def test_manual_cache_clear(self, db):
        """Cache can be cleared manually."""
        db.find({'i': 1}).all()
        db.find({'i': 2}).all()
        assert db.get_cache_stats()['size'] == 2
        
        db.clear_cache()
        assert db.get_cache_stats()['size'] == 0
    
    def test_stats_none_when_disabled(self):
        """Stats should return None when cache is disabled."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name, cache_enabled=False)
            assert db.get_cache_stats() is None
            os.unlink(f.name)


class TestCacheLRU:
    """Test LRU (Least Recently Used) cache eviction."""
    
    @pytest.fixture
    def db(self):
        """Create a test database with small cache."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name, cache_size=3)
            db.insert_many([{'i': i, 'v': f'val_{i}'} for i in range(10)])
            yield db
            db.clear_cache()
            os.unlink(db._filename)
    
    def test_lru_eviction(self, db):
        """Oldest entries should be evicted when cache is full."""
        # Fill cache (3 entries max)
        db.find({'i': 1}).all()
        db.find({'i': 2}).all()
        db.find({'i': 3}).all()
        
        assert db.get_cache_stats()['size'] == 3
        
        # Add 4th entry - should evict oldest (i=1)
        db.find({'i': 4}).all()
        
        stats = db.get_cache_stats()
        assert stats['size'] == 3
        
        # Cache now has [2, 3, 4] (i=1 was evicted)
        # Verify by checking that i=2,3,4 are cached but i=1 would be a miss
        db.reset_cache_stats()
        
        # i=2 should be a hit (oldest remaining)
        db.find({'i': 2}).all()
        # i=3 should be a hit
        db.find({'i': 3}).all()
        # i=4 should be a hit (most recent)
        db.find({'i': 4}).all()
        
        stats = db.get_cache_stats()
        assert stats['hits'] == 3
        assert stats['misses'] == 0
        
        # Now verify i=1 was evicted (would be a miss if queried)
        # Note: querying i=1 will add it back and evict i=2
        db.find({'i': 1}).all()
        stats = db.get_cache_stats()
        assert stats['misses'] == 1  # i=1 was evicted, so it's a miss
    
    def test_access_updates_lru_order(self, db):
        """Accessing an entry should move it to most recently used."""
        # Fill cache
        db.find({'i': 1}).all()
        db.find({'i': 2}).all()
        db.find({'i': 3}).all()
        
        # Access i=1 again (moves to end)
        db.find({'i': 1}).all()
        
        # Add new entry - should evict i=2 (oldest not accessed)
        db.find({'i': 4}).all()
        
        # i=1 should still be in cache
        db.reset_cache_stats()
        db.find({'i': 1}).all()
        assert db.get_cache_stats()['hits'] == 1


class TestCacheWithEmptyFilter:
    """Test caching of empty filter queries (find all)."""
    
    @pytest.fixture
    def db(self):
        """Create a test database."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            db = JSONlite(f.name)
            db.insert_many([{'i': i} for i in range(5)])
            yield db
            db.clear_cache()
            os.unlink(db._filename)
    
    def test_empty_filter_cached(self, db):
        """Empty filter queries should be cached."""
        db.reset_cache_stats()
        
        # First query - miss
        db.find({}).all()
        assert db.get_cache_stats()['misses'] == 1
        
        # Second query - hit
        db.find({}).all()
        assert db.get_cache_stats()['hits'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
