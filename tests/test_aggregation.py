"""Test aggregation pipeline functionality."""
import pytest
import os
from jsonlite import JSONlite


@pytest.fixture
def db():
    """Create a test database with sample data."""
    test_file = '/tmp/test_aggregation.json'
    if os.path.exists(test_file):
        os.remove(test_file)
    
    db = JSONlite(test_file)
    
    # Insert sample data
    db.insert_many([
        {"name": "Alice", "age": 25, "city": "NYC", "salary": 50000, "department": "Engineering"},
        {"name": "Bob", "age": 30, "city": "LA", "salary": 60000, "department": "Sales"},
        {"name": "Charlie", "age": 35, "city": "NYC", "salary": 70000, "department": "Engineering"},
        {"name": "Diana", "age": 28, "city": "LA", "salary": 55000, "department": "Marketing"},
        {"name": "Eve", "age": 32, "city": "NYC", "salary": 65000, "department": "Sales"},
        {"name": "Frank", "age": 40, "city": "Chicago", "salary": 80000, "department": "Engineering"},
    ])
    
    yield db
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


class TestMatch:
    """Test $match stage."""
    
    def test_match_simple(self, db):
        """Test simple match."""
        result = db.aggregate([
            {"$match": {"city": "NYC"}}
        ]).all()
        
        assert len(result) == 3
        assert all(doc["city"] == "NYC" for doc in result)
    
    def test_match_with_operator(self, db):
        """Test match with comparison operator."""
        result = db.aggregate([
            {"$match": {"age": {"$gt": 30}}}
        ]).all()
        
        assert len(result) == 3
        assert all(doc["age"] > 30 for doc in result)
    
    def test_match_multiple_conditions(self, db):
        """Test match with multiple conditions."""
        result = db.aggregate([
            {"$match": {"city": "NYC", "age": {"$gte": 30}}}
        ]).all()
        
        assert len(result) == 2


class TestGroup:
    """Test $group stage."""
    
    def test_group_by_field(self, db):
        """Test grouping by a field."""
        result = db.aggregate([
            {"$group": {"_id": "$city", "count": {"$count": {}}}}
        ]).all()
        
        assert len(result) == 3  # NYC, LA, Chicago
        
        city_counts = {doc["_id"]: doc["count"] for doc in result}
        assert city_counts["NYC"] == 3
        assert city_counts["LA"] == 2
        assert city_counts["Chicago"] == 1
    
    def test_group_with_sum(self, db):
        """Test grouping with sum accumulator."""
        result = db.aggregate([
            {"$group": {"_id": "$department", "totalSalary": {"$sum": "$salary"}}}
        ]).all()
        
        dept_totals = {doc["_id"]: doc["totalSalary"] for doc in result}
        assert dept_totals["Engineering"] == 50000 + 70000 + 80000  # 200000
        assert dept_totals["Sales"] == 60000 + 65000  # 125000
        assert dept_totals["Marketing"] == 55000
    
    def test_group_with_avg(self, db):
        """Test grouping with avg accumulator."""
        result = db.aggregate([
            {"$group": {"_id": "$department", "avgSalary": {"$avg": "$salary"}}}
        ]).all()
        
        dept_avgs = {doc["_id"]: doc["avgSalary"] for doc in result}
        assert dept_avgs["Engineering"] == 200000 / 3
        assert dept_avgs["Sales"] == 125000 / 2
        assert dept_avgs["Marketing"] == 55000
    
    def test_group_with_min_max(self, db):
        """Test grouping with min/max accumulators."""
        result = db.aggregate([
            {"$group": {"_id": "$department", "minAge": {"$min": "$age"}, "maxAge": {"$max": "$age"}}}
        ]).all()
        
        dept_ages = {doc["_id"]: (doc["minAge"], doc["maxAge"]) for doc in result}
        assert dept_ages["Engineering"] == (25, 40)
        assert dept_ages["Sales"] == (30, 32)
        assert dept_ages["Marketing"] == (28, 28)


class TestProject:
    """Test $project stage."""
    
    def test_project_include_fields(self, db):
        """Test including specific fields."""
        result = db.aggregate([
            {"$project": {"name": 1, "city": 1}}
        ]).all()
        
        assert len(result) == 6
        for doc in result:
            assert "name" in doc
            assert "city" in doc
            assert "age" not in doc
            assert "salary" not in doc
    
    def test_project_exclude_fields(self, db):
        """Test excluding specific fields."""
        result = db.aggregate([
            {"$project": {"salary": 0, "department": 0}}
        ]).all()
        
        assert len(result) == 6
        for doc in result:
            assert "salary" not in doc
            assert "department" not in doc
            assert "name" in doc
    
    def test_project_with_expression(self, db):
        """Test project with expressions."""
        result = db.aggregate([
            {"$project": {"displayName": {"$concat": ["$name", " - ", "$city"]}}}
        ]).all()
        
        assert result[0]["displayName"] == "Alice - NYC"


class TestSort:
    """Test $sort stage."""
    
    def test_sort_ascending(self, db):
        """Test sorting in ascending order."""
        result = db.aggregate([
            {"$sort": {"age": 1}}
        ]).all()
        
        ages = [doc["age"] for doc in result]
        assert ages == sorted(ages)
    
    def test_sort_descending(self, db):
        """Test sorting in descending order."""
        result = db.aggregate([
            {"$sort": {"salary": -1}}
        ]).all()
        
        salaries = [doc["salary"] for doc in result]
        assert salaries == sorted(salaries, reverse=True)


class TestSkipLimit:
    """Test $skip and $limit stages."""
    
    def test_limit(self, db):
        """Test limiting results."""
        result = db.aggregate([
            {"$limit": 3}
        ]).all()
        
        assert len(result) == 3
    
    def test_skip(self, db):
        """Test skipping results."""
        result = db.aggregate([
            {"$skip": 2}
        ]).all()
        
        assert len(result) == 4  # 6 total - 2 skipped
    
    def test_skip_and_limit(self, db):
        """Test pagination with skip and limit."""
        result = db.aggregate([
            {"$skip": 1},
            {"$limit": 3}
        ]).all()
        
        assert len(result) == 3


class TestCount:
    """Test $count stage."""
    
    def test_count_all(self, db):
        """Test counting all documents."""
        result = db.aggregate([
            {"$count": "total"}
        ]).all()
        
        assert len(result) == 1
        assert result[0]["total"] == 6
    
    def test_count_after_match(self, db):
        """Test counting after filtering."""
        result = db.aggregate([
            {"$match": {"city": "NYC"}},
            {"$count": "nyc_count"}
        ]).all()
        
        assert len(result) == 1
        assert result[0]["nyc_count"] == 3


class TestUnwind:
    """Test $unwind stage."""
    
    def test_unwind_array(self, db):
        """Test unwinding an array field."""
        # Insert a document with an array
        db.insert_one({
            "name": "Test",
            "tags": ["python", "database", "json"]
        })
        
        result = db.aggregate([
            {"$match": {"name": "Test"}},
            {"$unwind": "$tags"}
        ]).all()
        
        assert len(result) == 3
        tags = [doc["tags"] for doc in result]
        assert set(tags) == {"python", "database", "json"}


class TestComplexPipeline:
    """Test complex aggregation pipelines."""
    
    def test_multi_stage_pipeline(self, db):
        """Test a multi-stage pipeline."""
        result = db.aggregate([
            {"$match": {"age": {"$gt": 25}}},
            {"$group": {"_id": "$department", "avgSalary": {"$avg": "$salary"}, "count": {"$count": {}}}},
            {"$sort": {"avgSalary": -1}}
        ]).all()
        
        assert len(result) == 3
        # Engineering should have highest avg salary
        assert result[0]["_id"] == "Engineering"
    
    def test_group_project_sort(self, db):
        """Test group, project, and sort together."""
        result = db.aggregate([
            {"$group": {"_id": "$city", "totalSalary": {"$sum": "$salary"}}},
            {"$project": {"city": "$_id", "totalSalary": 1, "_id": 0}},
            {"$sort": {"totalSalary": -1}}
        ]).all()
        
        assert result[0]["city"] == "NYC"  # NYC has highest total salary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
