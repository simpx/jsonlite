"""Test query planner and optimizer."""

import pytest
import os
from jsonlite import JSONlite


@pytest.fixture
def db():
    """Create a test database."""
    test_file = "test_query_planner.json"
    database = JSONlite(test_file)
    
    # Insert test data
    database.insert_many([
        {"name": "Alice", "age": 25, "city": "New York", "score": 85},
        {"name": "Bob", "age": 30, "city": "London", "score": 90},
        {"name": "Charlie", "age": 35, "city": "Paris", "score": 75},
        {"name": "Diana", "age": 28, "city": "New York", "score": 88},
        {"name": "Eve", "age": 32, "city": "London", "score": 92},
    ])
    
    yield database
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


class TestQueryPlanner:
    """Test query planner functionality."""
    
    def test_query_stats_initial(self, db):
        """Test initial query statistics."""
        stats = db.get_query_stats()
        
        assert stats["total_queries"] == 0
        assert stats["optimized_queries"] == 0
        assert stats["slow_queries"] == 0
        assert stats["unique_patterns"] == 0
    
    def test_query_stats_after_find(self, db):
        """Test query statistics after running queries."""
        # Run some queries
        db.find({"age": 25}).all()
        db.find({"age": 30}).all()
        db.find({"city": "New York"}).all()
        db.find({"age": {"$gt": 28}}).all()
        
        stats = db.get_query_stats()
        
        assert stats["total_queries"] >= 4
        assert stats["unique_patterns"] >= 2
        assert "age" in stats["top_fields"] or "city" in stats["top_fields"]
    
    def test_query_stats_top_fields(self, db):
        """Test that top fields are tracked correctly."""
        # Run queries on specific fields
        for _ in range(5):
            db.find({"age": 25}).all()
        for _ in range(3):
            db.find({"city": "London"}).all()
        
        stats = db.get_query_stats()
        
        # Age should be the top field
        assert stats["top_fields"].get("age", 0) >= 5
        assert stats["top_fields"].get("city", 0) >= 3
    
    def test_suggest_indexes_no_existing(self, db):
        """Test index suggestions with no existing indexes."""
        # Run queries to build pattern
        for _ in range(5):
            db.find({"age": 25}).all()
        
        suggestions = db.suggest_indexes()
        
        # Should suggest index on frequently queried field
        assert len(suggestions) >= 1
        assert any("age" in str(s.get("fields", [])) for s in suggestions)
    
    def test_suggest_indexes_with_existing(self, db):
        """Test index suggestions respects existing indexes."""
        # Create an index
        db.create_index("age")
        
        # Run queries
        for _ in range(5):
            db.find({"age": 25}).all()
        for _ in range(5):
            db.find({"city": "London"}).all()
        
        suggestions = db.suggest_indexes()
        
        # Should not suggest age again (already indexed)
        age_suggestions = [s for s in suggestions if "age" in str(s.get("fields", []))]
        assert len(age_suggestions) == 0
        
        # Should suggest city
        city_suggestions = [s for s in suggestions if "city" in str(s.get("fields", []))]
        assert len(city_suggestions) >= 1
    
    def test_reset_query_stats(self, db):
        """Test resetting query statistics."""
        # Run some queries
        db.find({"age": 25}).all()
        db.find({"city": "London"}).all()
        
        # Reset stats
        db.reset_query_stats()
        
        stats = db.get_query_stats()
        assert stats["total_queries"] == 0
        assert stats["top_fields"] == {}
    
    def test_query_optimization_basic(self, db):
        """Test query optimization reorders conditions."""
        from jsonlite.jsonlite import QueryPlanner
        
        planner = QueryPlanner()
        
        # Create a filter with multiple conditions
        filter = {
            "city": "New York",
            "age": 30,
            "score": {"$gt": 80}
        }
        
        # Optimize with age as indexed field
        optimized = planner.optimize_filter(filter, available_indexes=["age"])
        
        # Age should come first (indexed field)
        keys = list(optimized.keys())
        assert keys[0] == "age"
    
    def test_query_optimization_equality_first(self, db):
        """Test that equality conditions come before range conditions."""
        from jsonlite.jsonlite import QueryPlanner
        
        planner = QueryPlanner()
        
        filter = {
            "score": {"$gt": 80},
            "city": "London",
            "age": {"$lt": 35}
        }
        
        optimized = planner.optimize_filter(filter, available_indexes=[])
        keys = list(optimized.keys())
        
        # Equality (city) should come before range conditions
        assert keys[0] == "city"
    
    def test_analyze_filter(self, db):
        """Test filter analysis."""
        from jsonlite.jsonlite import QueryPlanner
        
        planner = QueryPlanner()
        
        filter = {
            "age": {"$gt": 25, "$lt": 35},
            "city": "London",
            "$or": [{"score": {"$gte": 80}}, {"name": "Alice"}]
        }
        
        analysis = planner.analyze_filter(filter)
        
        assert "age" in analysis["fields"]
        assert "city" in analysis["fields"]
        assert "$gt" in analysis["operators"] or "$or" in analysis["operators"]
        assert analysis["field_count"] >= 2
    
    def test_slow_query_tracking(self, db):
        """Test that slow queries are tracked."""
        # Run a query (won't actually be slow in test, but we can check the mechanism)
        db.find({"age": 25}).all()
        
        stats = db.get_query_stats()
        assert "slow_queries" in stats
        assert isinstance(stats["slow_queries"], int)
    
    def test_query_pattern_tracking(self, db):
        """Test that query patterns are tracked."""
        # Run same pattern multiple times
        for i in range(5):
            db.find({"age": 20 + i}).all()
        
        stats = db.get_query_stats()
        
        # Should have multiple queries but fewer unique patterns
        assert stats["total_queries"] >= 5
        assert stats["unique_patterns"] >= 1


class TestQueryPlannerIntegration:
    """Test query planner integration with database operations."""
    
    def test_query_planner_with_index_usage(self, db):
        """Test query planner tracks index usage."""
        # Create index
        db.create_index("city")
        
        # Run queries
        db.find({"city": "London"}).all()
        db.find({"city": "Paris"}).all()
        
        stats = db.get_query_stats()
        assert stats["total_queries"] >= 2
    
    def test_query_planner_with_cache(self, db):
        """Test query planner works with caching enabled."""
        # Enable cache (already enabled by default)
        db.find({"age": 25}).all()
        db.find({"age": 25}).all()  # Should hit cache
        
        stats = db.get_query_stats()
        assert stats["total_queries"] >= 2
    
    def test_query_planner_complex_query(self, db):
        """Test query planner with complex queries."""
        db.find({
            "age": {"$gt": 25, "$lt": 35},
            "city": {"$in": ["New York", "London"]}
        }).all()
        
        stats = db.get_query_stats()
        assert stats["total_queries"] >= 1
        assert "age" in stats["top_fields"] or "city" in stats["top_fields"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
