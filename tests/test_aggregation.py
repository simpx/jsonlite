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


class TestBucket:
    """Test $bucket stage."""
    
    def test_bucket_basic(self):
        """Test basic bucket grouping by price ranges."""
        test_file = '/tmp/test_bucket_basic.json'
        if os.path.exists(test_file):
            os.remove(test_file)
        
        db = JSONlite(test_file)
        
        # Insert products with different prices
        db.insert_many([
            {"name": "Product A", "price": 50},
            {"name": "Product B", "price": 150},
            {"name": "Product C", "price": 250},
            {"name": "Product D", "price": 350},
            {"name": "Product E", "price": 450},
            {"name": "Product F", "price": 550},
        ])
        
        result = db.aggregate([
            {
                "$bucket": {
                    "groupBy": "$price",
                    "boundaries": [0, 100, 200, 300, 400, 500, 600],
                    "output": {
                        "count": {"$count": {}},
                        "avgPrice": {"$avg": "$price"}
                    }
                }
            }
        ]).all()
        
        # Should have 6 buckets (0-100, 100-200, 200-300, 300-400, 400-500, 500-600)
        assert len(result) == 6
        
        # Check first bucket (0-100)
        bucket_0 = next(b for b in result if b['_id'] == 0)
        assert bucket_0['count'] == 1
        assert bucket_0['avgPrice'] == 50
        
        # Check bucket 100-200
        bucket_100 = next(b for b in result if b['_id'] == 100)
        assert bucket_100['count'] == 1
        assert bucket_100['avgPrice'] == 150
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)
    
    def test_bucket_with_default(self):
        """Test bucket with default label for out-of-range values."""
        test_file = '/tmp/test_bucket_default.json'
        if os.path.exists(test_file):
            os.remove(test_file)
        
        db = JSONlite(test_file)
        
        db.insert_many([
            {"name": "Product A", "price": 50},
            {"name": "Product B", "price": 150},
            {"name": "Product C", "price": 999},  # Out of range
        ])
        
        result = db.aggregate([
            {
                "$bucket": {
                    "groupBy": "$price",
                    "boundaries": [0, 100, 200],
                    "default": "Other",
                    "output": {
                        "count": {"$count": {}},
                        "products": {"$push": "$name"}
                    }
                }
            }
        ]).all()
        
        # Should have 3 buckets: 0-100, 100-200, and Other
        assert len(result) == 3
        
        # Check default bucket
        other = next(b for b in result if b['_id'] == 'Other')
        assert other['count'] == 1
        assert other['products'] == ['Product C']
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)
    
    def test_bucket_with_sum_and_avg(self):
        """Test bucket with multiple accumulators."""
        test_file = '/tmp/test_bucket_sum_avg.json'
        if os.path.exists(test_file):
            os.remove(test_file)
        
        db = JSONlite(test_file)
        
        db.insert_many([
            {"name": "A", "age": 20, "score": 80},
            {"name": "B", "age": 25, "score": 85},
            {"name": "C", "age": 30, "score": 90},
            {"name": "D", "age": 35, "score": 95},
            {"name": "E", "age": 40, "score": 100},
        ])
        
        result = db.aggregate([
            {
                "$bucket": {
                    "groupBy": "$age",
                    "boundaries": [0, 25, 50],
                    "output": {
                        "count": {"$count": {}},
                        "totalScore": {"$sum": "$score"},
                        "avgScore": {"$avg": "$score"},
                        "minScore": {"$min": "$score"},
                        "maxScore": {"$max": "$score"}
                    }
                }
            }
        ]).all()
        
        assert len(result) == 2
        
        # Bucket 0-25: A (20, 80), B (25, 85) - note: 25 is in 25-50 bucket
        bucket_0 = next(b for b in result if b['_id'] == 0)
        assert bucket_0['count'] == 1  # Only A (age 20)
        assert bucket_0['totalScore'] == 80
        assert bucket_0['avgScore'] == 80
        
        # Bucket 25-50: B (25), C (30), D (35), E (40)
        bucket_25 = next(b for b in result if b['_id'] == 25)
        assert bucket_25['count'] == 4
        assert bucket_25['totalScore'] == 85 + 90 + 95 + 100  # 370
        assert bucket_25['avgScore'] == 370 / 4  # 92.5
        assert bucket_25['minScore'] == 85
        assert bucket_25['maxScore'] == 100
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)


class TestBucketAuto:
    """Test $bucketAuto stage."""
    
    def test_bucket_auto_basic(self):
        """Test automatic bucket creation."""
        test_file = '/tmp/test_bucket_auto_basic.json'
        if os.path.exists(test_file):
            os.remove(test_file)
        
        db = JSONlite(test_file)
        
        db.insert_many([
            {"name": "A", "value": 10},
            {"name": "B", "value": 20},
            {"name": "C", "value": 30},
            {"name": "D", "value": 40},
            {"name": "E", "value": 50},
            {"name": "F", "value": 60},
        ])
        
        result = db.aggregate([
            {
                "$bucketAuto": {
                    "groupBy": "$value",
                    "buckets": 3,
                    "output": {
                        "count": {"$count": {}},
                        "avgValue": {"$avg": "$value"}
                    }
                }
            }
        ]).all()
        
        # Should have approximately 3 buckets
        assert len(result) <= 4  # May have slight variation due to boundary calculation
        
        # Total count should be 6
        total_count = sum(b['count'] for b in result)
        assert total_count == 6
        
        # Each bucket should have _id with min and max
        for bucket in result:
            assert '_id' in bucket
            assert 'min' in bucket['_id']
            assert 'max' in bucket['_id']
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)
    
    def test_bucket_auto_with_first_last(self):
        """Test bucketAuto with $first and $last accumulators."""
        test_file = '/tmp/test_bucket_auto_first_last.json'
        if os.path.exists(test_file):
            os.remove(test_file)
        
        db = JSONlite(test_file)
        
        db.insert_many([
            {"name": "A", "value": 10, "category": "X"},
            {"name": "B", "value": 20, "category": "Y"},
            {"name": "C", "value": 30, "category": "Z"},
        ])
        
        result = db.aggregate([
            {
                "$bucketAuto": {
                    "groupBy": "$value",
                    "buckets": 2,
                    "output": {
                        "count": {"$count": {}},
                        "firstName": {"$first": "$name"},
                        "lastName": {"$last": "$name"},
                        "firstCategory": {"$first": "$category"}
                    }
                }
            }
        ]).all()
        
        assert len(result) >= 1
        
        # Check that first/last are captured
        for bucket in result:
            if bucket['count'] > 0:
                assert 'firstName' in bucket
                assert 'lastName' in bucket
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)
    
    def test_bucket_auto_empty_result(self, db):
        """Test bucketAuto with no matching documents."""
        # Clear existing data by creating new db
        test_file = '/tmp/test_bucket_auto_empty.json'
        if os.path.exists(test_file):
            os.remove(test_file)
        
        empty_db = JSONlite(test_file)
        # Don't insert any data
        
        result = empty_db.aggregate([
            {
                "$bucketAuto": {
                    "groupBy": "$value",
                    "buckets": 5,
                    "output": {
                        "count": {"$count": {}}
                    }
                }
            }
        ]).all()
        
        assert result == []
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)


class TestExpressionOperators:
    """Test aggregation expression operators."""
    
    def test_arithmetic_abs(self, db):
        """Test $abs operator."""
        # Add a document with negative value
        db.insert_one({"value": -42, "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {"absolute": {"$abs": "$value"}}}
        ]).all()
        
        assert len(result) == 1
        assert result[0]["absolute"] == 42
    
    def test_arithmetic_ceil_floor(self, db):
        """Test $ceil and $floor operators."""
        db.insert_one({"value": 3.7, "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "ceil": {"$ceil": "$value"},
                "floor": {"$floor": "$value"}
            }}
        ]).all()
        
        assert result[0]["ceil"] == 4
        assert result[0]["floor"] == 3
    
    def test_arithmetic_mod_pow_sqrt(self, db):
        """Test $mod, $pow, $sqrt operators."""
        db.insert_one({"a": 10, "b": 3, "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "mod": {"$mod": ["$a", "$b"]},
                "pow": {"$pow": [2, 3]},
                "sqrt": {"$sqrt": 16}
            }}
        ]).all()
        
        assert result[0]["mod"] == 1  # 10 % 3
        assert result[0]["pow"] == 8  # 2^3
        assert result[0]["sqrt"] == 4
    
    def test_arithmetic_round_trunc(self, db):
        """Test $round and $trunc operators."""
        db.insert_one({"value": 3.14159, "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "rounded": {"$round": ["$value", 2]},
                "truncated": {"$trunc": "$value"}
            }}
        ]).all()
        
        assert result[0]["rounded"] == 3.14
        assert result[0]["truncated"] == 3
    
    def test_comparison_operators(self, db):
        """Test comparison operators: $cmp, $eq, $ne, $gt, $gte, $lt, $lte."""
        db.insert_one({"a": 5, "b": 10, "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "cmp": {"$cmp": ["$a", "$b"]},
                "eq": {"$eq": ["$a", "$b"]},
                "ne": {"$ne": ["$a", "$b"]},
                "gt": {"$gt": ["$a", "$b"]},
                "gte": {"$gte": ["$a", "$b"]},
                "lt": {"$lt": ["$a", "$b"]},
                "lte": {"$lte": ["$a", "$b"]}
            }}
        ]).all()
        
        assert result[0]["cmp"] == -1  # 5 < 10
        assert result[0]["eq"] == False
        assert result[0]["ne"] == True
        assert result[0]["gt"] == False
        assert result[0]["gte"] == False
        assert result[0]["lt"] == True
        assert result[0]["lte"] == True
    
    def test_logical_operators(self, db):
        """Test $and, $or, $not operators."""
        db.insert_one({"a": True, "b": False, "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "and_result": {"$and": ["$a", "$b"]},
                "or_result": {"$or": ["$a", "$b"]},
                "not_a": {"$not": "$a"}
            }}
        ]).all()
        
        assert result[0]["and_result"] == False
        assert result[0]["or_result"] == True
        assert result[0]["not_a"] == False
    
    def test_string_operators(self, db):
        """Test string operators: $substr, $tolower, $toupper, $strlen, $split, $trim."""
        db.insert_one({"text": "  Hello World  ", "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "substr": {"$substr": ["$text", 2, 5]},
                "lower": {"$tolower": "$text"},
                "upper": {"$toupper": "$text"},
                "length": {"$strlen": "$text"},
                "trimmed": {"$trim": "$text"}
            }}
        ]).all()
        
        assert result[0]["substr"] == "Hello"  # Starting at index 2: "Hello"
        assert result[0]["lower"] == "  hello world  "
        assert result[0]["upper"] == "  HELLO WORLD  "
        assert result[0]["length"] == 15
        assert result[0]["trimmed"] == "Hello World"
    
    def test_string_split(self, db):
        """Test $split operator."""
        db.insert_one({"text": "apple,banana,cherry", "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "parts": {"$split": ["$text", ","]}
            }}
        ]).all()
        
        assert result[0]["parts"] == ["apple", "banana", "cherry"]
    
    def test_array_operators(self, db):
        """Test array operators: $arrayElemAt, $concatArrays, $isArray, $in, $slice."""
        db.insert_one({
            "arr1": [1, 2, 3],
            "arr2": [4, 5, 6],
            "value": 3,
            "name": "test"
        })
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "elem": {"$arrayElemAt": ["$arr1", 1]},
                "concat": {"$concatArrays": ["$arr1", "$arr2"]},
                "is_arr": {"$isArray": "$arr1"},
                "in_arr": {"$in": ["$value", "$arr1"]},
                "sliced": {"$slice": ["$arr1", 2]}
            }}
        ]).all()
        
        assert result[0]["elem"] == 2
        assert result[0]["concat"] == [1, 2, 3, 4, 5, 6]
        assert result[0]["is_arr"] == True
        assert result[0]["in_arr"] == True
        assert result[0]["sliced"] == [1, 2]
    
    def test_array_slice_with_skip(self, db):
        """Test $slice with skip parameter."""
        db.insert_one({"arr": [1, 2, 3, 4, 5], "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "sliced": {"$slice": ["$arr", 1, 3]}
            }}
        ]).all()
        
        assert result[0]["sliced"] == [2, 3, 4]
    
    def test_type_conversion(self, db):
        """Test type conversion operators: $toBool, $toInt, $toDouble, $toString."""
        db.insert_one({"num": 42, "str": "123", "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "to_bool": {"$toBool": "$num"},
                "to_int": {"$toInt": "$str"},
                "to_double": {"$toDouble": "$num"},
                "to_string": {"$toString": "$num"}
            }}
        ]).all()
        
        assert result[0]["to_bool"] == True
        assert result[0]["to_int"] == 123
        assert result[0]["to_double"] == 42.0
        assert result[0]["to_string"] == "42"
    
    def test_cond_array_form(self, db):
        """Test $cond in array form."""
        db.insert_one({"value": 10, "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "result": {"$cond": [{"$gt": ["$value", 5]}, "big", "small"]}
            }}
        ]).all()
        
        assert result[0]["result"] == "big"
    
    def test_complex_expression(self, db):
        """Test complex nested expression."""
        db.insert_one({"price": 100, "discount": 0.2, "name": "test"})
        
        result = db.aggregate([
            {"$match": {"name": "test"}},
            {"$project": {
                "final_price": {
                    "$multiply": [
                        "$price",
                        {"$subtract": [1, "$discount"]}
                    ]
                }
            }}
        ]).all()
        
        assert result[0]["final_price"] == 80.0
    
    def test_conditional_with_comparison(self, db):
        """Test conditional logic with comparison operators."""
        db.insert_many([
            {"score": 85, "name": "Alice"},
            {"score": 59, "name": "Bob"},
            {"score": 72, "name": "Charlie"}
        ])
        
        result = db.aggregate([
            {"$project": {
                "name": 1,
                "passed": {"$cond": [{"$gte": ["$score", 60]}, "Yes", "No"]}
            }}
        ]).all()
        
        passed = {r["name"]: r["passed"] for r in result}
        assert passed["Alice"] == "Yes"
        assert passed["Bob"] == "No"
        assert passed["Charlie"] == "Yes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
