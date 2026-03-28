"""Test $addFields aggregation stage for virtual/computed fields."""
import pytest
import os
from jsonlite import JSONlite


@pytest.fixture
def db():
    """Create a test database with sample data."""
    test_file = '/tmp/test_add_fields.json'
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


@pytest.fixture
def products_db():
    """Create a test database with product data."""
    test_file = '/tmp/test_add_fields_products.json'
    if os.path.exists(test_file):
        os.remove(test_file)
    
    db = JSONlite(test_file)
    
    # Insert product data
    db.insert_many([
        {"name": "Laptop", "price": 1000, "quantity": 10, "category": "electronics"},
        {"name": "Mouse", "price": 25, "quantity": 50, "category": "electronics"},
        {"name": "Desk Chair", "price": 200, "quantity": 0, "category": "furniture"},
        {"name": "Notebook", "price": 5, "quantity": 100, "category": "stationery"},
    ])
    
    yield db
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


class TestAddFieldsBasic:
    """Test basic $addFields functionality."""
    
    def test_add_constant_field(self, db):
        """Test adding a constant field to all documents."""
        result = db.aggregate([
            {"$addFields": {"status": "active"}}
        ]).all()
        
        assert len(result) == 6
        assert all(doc["status"] == "active" for doc in result)
        # Original fields should be preserved
        assert all("name" in doc for doc in result)
        assert all("age" in doc for doc in result)
    
    def test_add_field_reference(self, db):
        """Test adding a field that references another field."""
        result = db.aggregate([
            {"$addFields": {"employee_name": "$name"}}
        ]).all()
        
        assert len(result) == 6
        for doc in result:
            assert doc["employee_name"] == doc["name"]
    
    def test_add_multiple_fields(self, db):
        """Test adding multiple fields at once."""
        result = db.aggregate([
            {"$addFields": {
                "status": "active",
                "employee_name": "$name",
                "location": "$city"
            }}
        ]).all()
        
        assert len(result) == 6
        assert all(doc["status"] == "active" for doc in result)
        assert all(doc["employee_name"] == doc["name"] for doc in result)
        assert all(doc["location"] == doc["city"] for doc in result)


class TestAddFieldsArithmetic:
    """Test arithmetic expressions in $addFields."""
    
    def test_multiply_fields(self, products_db):
        """Test computing total price with multiplication."""
        result = products_db.aggregate([
            {"$addFields": {
                "totalValue": {"$multiply": ["$price", "$quantity"]}
            }}
        ]).all()
        
        assert len(result) == 4
        laptop = next(d for d in result if d["name"] == "Laptop")
        assert laptop["totalValue"] == 1000 * 10  # 10000
        
        mouse = next(d for d in result if d["name"] == "Mouse")
        assert mouse["totalValue"] == 25 * 50  # 1250
    
    def test_add_fields(self, db):
        """Test adding numeric fields."""
        result = db.aggregate([
            {"$addFields": {
                "doubleAge": {"$add": ["$age", "$age"]}
            }}
        ]).all()
        
        for doc in result:
            assert doc["doubleAge"] == doc["age"] * 2
    
    def test_complex_arithmetic(self, products_db):
        """Test complex arithmetic expression."""
        result = products_db.aggregate([
            {"$addFields": {
                "discountedPrice": {"$multiply": ["$price", 0.9]},  # 10% off
                "taxAmount": {"$multiply": ["$price", 0.08]}  # 8% tax
            }}
        ]).all()
        
        laptop = next(d for d in result if d["name"] == "Laptop")
        assert laptop["discountedPrice"] == 1000 * 0.9  # 900
        assert laptop["taxAmount"] == 1000 * 0.08  # 80


class TestAddFieldsString:
    """Test string expressions in $addFields."""
    
    def test_to_upper(self, db):
        """Test converting field to uppercase."""
        result = db.aggregate([
            {"$addFields": {
                "upperName": {"$toupper": "$name"}
            }}
        ]).all()
        
        alice = next(d for d in result if d["name"] == "Alice")
        assert alice["upperName"] == "ALICE"
    
    def test_to_lower(self, products_db):
        """Test converting field to lowercase."""
        result = products_db.aggregate([
            {"$addFields": {
                "category_lower": {"$tolower": "$category"}
            }}
        ]).all()
        
        assert all(doc["category_lower"] == doc["category"].lower() for doc in result)
    
    def test_concat(self, db):
        """Test concatenating strings."""
        result = db.aggregate([
            {"$addFields": {
                "fullName": {"$concat": ["$name", " (", "$department", ")"]}
            }}
        ]).all()
        
        alice = next(d for d in result if d["name"] == "Alice")
        assert alice["fullName"] == "Alice (Engineering)"


class TestAddFieldsComparison:
    """Test comparison expressions in $addFields."""
    
    def test_greater_than(self, db):
        """Test computing boolean with $gt."""
        result = db.aggregate([
            {"$addFields": {
                "isHighEarner": {"$gt": ["$salary", 60000]}
            }}
        ]).all()
        
        for doc in result:
            expected = doc["salary"] > 60000
            assert doc["isHighEarner"] == expected
    
    def test_in_stock_check(self, products_db):
        """Test computing in-stock status."""
        result = products_db.aggregate([
            {"$addFields": {
                "inStock": {"$gt": ["$quantity", 0]}
            }}
        ]).all()
        
        for doc in result:
            assert doc["inStock"] == (doc["quantity"] > 0)
        
        # Verify specific products
        laptop = next(d for d in result if d["name"] == "Laptop")
        assert laptop["inStock"] == True
        
        chair = next(d for d in result if d["name"] == "Desk Chair")
        assert chair["inStock"] == False


class TestAddFieldsConditional:
    """Test conditional expressions in $addFields."""
    
    def test_conditional_salary_tier(self, db):
        """Test computing salary tier with $cond."""
        result = db.aggregate([
            {"$addFields": {
                "salaryTier": {
                    "$cond": [
                        {"$gt": ["$salary", 70000]},
                        "Senior",
                        {"$cond": [
                            {"$gt": ["$salary", 55000]},
                            "Mid",
                            "Junior"
                        ]}
                    ]
                }
            }}
        ]).all()
        
        frank = next(d for d in result if d["name"] == "Frank")  # 80000
        assert frank["salaryTier"] == "Senior"
        
        eve = next(d for d in result if d["name"] == "Eve")  # 65000
        assert eve["salaryTier"] == "Mid"
        
        alice = next(d for d in result if d["name"] == "Alice")  # 50000
        assert alice["salaryTier"] == "Junior"


class TestAddFieldsNested:
    """Test $addFields with nested documents."""
    
    def test_nested_field_access(self):
        """Test accessing nested fields."""
        test_file = '/tmp/test_add_fields_nested.json'
        if os.path.exists(test_file):
            os.remove(test_file)
        
        db = JSONlite(test_file)
        
        db.insert_many([
            {"name": "Alice", "address": {"city": "NYC", "zip": "10001"}},
            {"name": "Bob", "address": {"city": "LA", "zip": "90001"}},
        ])
        
        result = db.aggregate([
            {"$addFields": {
                "city": "$address.city",
                "zipCode": "$address.zip"
            }}
        ]).all()
        
        alice = next(d for d in result if d["name"] == "Alice")
        assert alice["city"] == "NYC"
        assert alice["zipCode"] == "10001"
        
        if os.path.exists(test_file):
            os.remove(test_file)


class TestAddFieldsPipeline:
    """Test $addFields in combination with other stages."""
    
    def test_add_fields_then_match(self, db):
        """Test adding computed field then filtering."""
        result = db.aggregate([
            {"$addFields": {
                "annualBonus": {"$multiply": ["$salary", 0.1]}
            }},
            {"$match": {"annualBonus": {"$gte": 6000}}},
            {"$sort": {"annualBonus": -1}}
        ]).all()
        
        # Only employees with salary >= 60000 should match
        assert len(result) <= 6
        assert all(doc["annualBonus"] >= 6000 for doc in result)
    
    def test_add_fields_then_project(self, products_db):
        """Test adding computed field then projecting."""
        result = products_db.aggregate([
            {"$addFields": {
                "totalValue": {"$multiply": ["$price", "$quantity"]}
            }},
            {"$project": {
                "name": 1,
                "totalValue": 1,
                "_id": 0
            }}
        ]).all()
        
        assert len(result) == 4
        for doc in result:
            assert "name" in doc
            assert "totalValue" in doc
            assert "price" not in doc  # Should be excluded
            assert "quantity" not in doc  # Should be excluded
    
    def test_multiple_add_fields_stages(self, db):
        """Test multiple $addFields stages in sequence."""
        result = db.aggregate([
            {"$addFields": {
                "bonus": {"$multiply": ["$salary", 0.1]}
            }},
            {"$addFields": {
                "totalCompensation": {"$add": ["$salary", "$bonus"]}
            }}
        ]).all()
        
        for doc in result:
            expected_bonus = doc["salary"] * 0.1
            assert doc["bonus"] == expected_bonus
            assert doc["totalCompensation"] == doc["salary"] + expected_bonus


class TestAddFieldsEdgeCases:
    """Test edge cases for $addFields."""
    
    def test_overwrite_existing_field(self, db):
        """Test that $addFields can overwrite existing fields."""
        # Get original ages first
        original = db.find().all()
        original_by_name = {doc["name"]: doc["age"] for doc in original}
        
        result = db.aggregate([
            {"$addFields": {
                "age": {"$add": ["$age", 1]}  # Add 1 year to age
            }}
        ]).all()
        
        # Ages should be incremented
        for doc in result:
            original_age = original_by_name[doc["name"]]
            assert doc["age"] == original_age + 1
    
    def test_empty_collection(self):
        """Test $addFields on empty collection."""
        test_file = '/tmp/test_add_fields_empty.json'
        if os.path.exists(test_file):
            os.remove(test_file)
        
        db = JSONlite(test_file)
        
        result = db.aggregate([
            {"$addFields": {"computed": "value"}}
        ]).all()
        
        assert len(result) == 0
        
        if os.path.exists(test_file):
            os.remove(test_file)
    
    def test_null_handling(self, db):
        """Test handling of null/missing fields."""
        # Insert a document with missing field
        db.insert_one({"name": "Test", "age": None})
        
        result = db.aggregate([
            {"$addFields": {
                "agePlus10": {"$add": ["$age", 10]}
            }}
        ]).all()
        
        test_doc = next(d for d in result if d["name"] == "Test")
        # None + 10 should result in None (graceful handling)
        # Note: This behavior may be implementation-dependent
        # The key is that it doesn't crash
        assert "agePlus10" in test_doc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
