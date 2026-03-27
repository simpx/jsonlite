"""Tests for $lookup aggregation stage."""

import pytest
import os
import shutil
from jsonlite import JSONlite, MongoClient


class TestLookupBasic:
    """Test basic $lookup functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test databases."""
        self.test_dir = tmp_path / "lookup_test"
        self.test_dir.mkdir()
        
        # Create orders collection
        self.orders_path = str(self.test_dir / "orders.json")
        self.orders = JSONlite(self.orders_path)
        self.orders.insert_many([
            {"order_num": 1, "item": "laptop", "customer_id": 101, "quantity": 1},
            {"order_num": 2, "item": "mouse", "customer_id": 102, "quantity": 2},
            {"order_num": 3, "item": "keyboard", "customer_id": 101, "quantity": 1},
            {"order_num": 4, "item": "monitor", "customer_id": 103, "quantity": 1},
        ])
        
        # Create customers collection
        self.customers_path = str(self.test_dir / "customers.json")
        self.customers = JSONlite(self.customers_path)
        self.customers.insert_many([
            {"customer_id": 101, "name": "Alice", "email": "alice@example.com", "city": "NYC"},
            {"customer_id": 102, "name": "Bob", "email": "bob@example.com", "city": "LA"},
            {"customer_id": 103, "name": "Charlie", "email": "charlie@example.com", "city": "SF"},
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_lookup_basic_join(self):
        """Test basic $lookup with localField and foreignField."""
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "localField": "customer_id",
                    "foreignField": "customer_id",
                    "as": "customer"
                }
            }
        ]).all()
        
        assert len(result) == 4
        
        # Check first order (customer_id: 101 -> Alice)
        order1 = next(r for r in result if r["order_num"] == 1)
        assert "customer" in order1
        assert len(order1["customer"]) == 1
        assert order1["customer"][0]["name"] == "Alice"
        
        # Check second order (customer_id: 102 -> Bob)
        order2 = next(r for r in result if r["order_num"] == 2)
        assert len(order2["customer"]) == 1
        assert order2["customer"][0]["name"] == "Bob"
    
    def test_lookup_no_match(self):
        """Test $lookup when no matching foreign document exists."""
        # Insert an order with non-existent customer
        self.orders.insert_one({"order_num": 5, "item": "headphones", "customer_id": 999, "quantity": 1})
        
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "localField": "customer_id",
                    "foreignField": "customer_id",
                    "as": "customer"
                }
            }
        ]).all()
        
        order5 = next(r for r in result if r["order_num"] == 5)
        assert order5["customer"] == []
    
    def test_lookup_multiple_matches(self):
        """Test $lookup when multiple foreign documents match."""
        # Add another customer in same city
        self.customers.insert_one({"customer_id": 104, "name": "Diana", "email": "diana@example.com", "city": "NYC"})
        self.orders.insert_one({"order_num": 5, "item": "webcam", "city": "NYC", "quantity": 1})
        
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "localField": "city",
                    "foreignField": "city",
                    "as": "customers_in_city"
                }
            }
        ]).all()
        
        order5 = next(r for r in result if r["order_num"] == 5)
        assert len(order5["customers_in_city"]) == 2  # Alice and Diana are in NYC
    
    def test_lookup_with_match_after(self):
        """Test $lookup followed by $match."""
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "localField": "customer_id",
                    "foreignField": "customer_id",
                    "as": "customer"
                }
            },
            {
                "$match": {
                    "customer.name": "Alice"
                }
            }
        ]).all()
        
        assert len(result) == 2  # Orders 1 and 3
        assert all(r["customer"][0]["name"] == "Alice" for r in result)
    
    def test_lookup_with_project(self):
        """Test $lookup followed by $project."""
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "localField": "customer_id",
                    "foreignField": "customer_id",
                    "as": "customer"
                }
            },
            {
                "$project": {
                    "item": 1,
                    "customer_name": "$customer.name",
                    "_id": 0
                }
            }
        ]).all()
        
        assert len(result) == 4
        order1 = next(r for r in result if r["item"] == "laptop")
        assert order1["customer_name"] == ["Alice"]


class TestLookupWithMongoClient:
    """Test $lookup with MongoClient (multi-database)."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test with MongoClient."""
        self.test_dir = tmp_path / "mongo_test"
        self.test_dir.mkdir()
        
        # Use MongoClient
        self.client = MongoClient(str(self.test_dir))
        self.db = self.client["shop"]
        
        # Create orders collection
        self.orders = self.db.get_collection("orders")
        self.orders.insert_many([
            {"order_num": 1, "item": "laptop", "customer_id": 101, "quantity": 1},
            {"order_num": 2, "item": "mouse", "customer_id": 102, "quantity": 2},
            {"order_num": 3, "item": "keyboard", "customer_id": 101, "quantity": 1},
        ])
        
        # Create customers collection
        self.customers = self.db.get_collection("customers")
        self.customers.insert_many([
            {"customer_id": 101, "name": "Alice", "email": "alice@example.com"},
            {"customer_id": 102, "name": "Bob", "email": "bob@example.com"},
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_lookup_with_mongo_client(self):
        """Test $lookup using MongoClient collections."""
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "localField": "customer_id",
                    "foreignField": "customer_id",
                    "as": "customer_info"
                }
            }
        ]).all()
        
        assert len(result) == 3
        
        order1 = next(r for r in result if r["order_num"] == 1)
        assert len(order1["customer_info"]) == 1
        assert order1["customer_info"][0]["name"] == "Alice"
    
    def test_lookup_unwind_after(self):
        """Test $lookup followed by $unwind."""
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "localField": "customer_id",
                    "foreignField": "customer_id",
                    "as": "customer_info"
                }
            },
            {
                "$unwind": "$customer_info"
            }
        ]).all()
        
        assert len(result) == 3
        assert all("customer_info" in r and isinstance(r["customer_info"], dict) for r in result)
    
    def test_lookup_complex_pipeline(self):
        """Test $lookup with multiple stages after."""
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "localField": "customer_id",
                    "foreignField": "customer_id",
                    "as": "customer_info"
                }
            },
            {
                "$unwind": "$customer_info"
            },
            {
                "$project": {
                    "item": 1,
                    "customer_name": "$customer_info.name",
                    "customer_email": "$customer_info.email"
                }
            },
            {
                "$sort": {"item": 1}
            }
        ]).all()
        
        assert len(result) == 3
        assert result[0]["item"] == "keyboard"
        assert result[0]["customer_name"] == "Alice"


class TestLookupPipelineSyntax:
    """Test $lookup with pipeline syntax (advanced)."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test databases."""
        self.test_dir = tmp_path / "pipeline_test"
        self.test_dir.mkdir()
        
        # Create orders collection
        self.orders_path = str(self.test_dir / "orders.json")
        self.orders = JSONlite(self.orders_path)
        self.orders.insert_many([
            {"order_num": 1, "item": "laptop", "customer_id": 101, "quantity": 1},
            {"order_num": 2, "item": "mouse", "customer_id": 102, "quantity": 2},
        ])
        
        # Create customers collection
        self.customers_path = str(self.test_dir / "customers.json")
        self.customers = JSONlite(self.customers_path)
        self.customers.insert_many([
            {"customer_id": 101, "name": "Alice", "orders_count": 5, "city": "NYC"},
            {"customer_id": 102, "name": "Bob", "orders_count": 3, "city": "LA"},
            {"customer_id": 103, "name": "Charlie", "orders_count": 10, "city": "NYC"},
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_lookup_with_pipeline_basic(self):
        """Test $lookup with pipeline syntax."""
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "let": {"cust_id": "$customer_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$customer_id", "$$cust_id"]}}}
                    ],
                    "as": "customer"
                }
            }
        ]).all()
        
        assert len(result) == 2
        
        order1 = next(r for r in result if r["order_num"] == 1)
        assert len(order1["customer"]) == 1
        assert order1["customer"][0]["name"] == "Alice"
    
    def test_lookup_pipeline_with_filter(self):
        """Test $lookup with pipeline that filters results."""
        result = self.orders.aggregate([
            {
                "$lookup": {
                    "from": "customers",
                    "let": {"cust_id": "$customer_id"},
                    "pipeline": [
                        {"$match": {
                            "$expr": {"$eq": ["$customer_id", "$$cust_id"]},
                            "city": "NYC"
                        }}
                    ],
                    "as": "ny_customer"
                }
            }
        ]).all()
        
        order1 = next(r for r in result if r["order_num"] == 1)
        assert len(order1["ny_customer"]) == 1  # Alice is in NYC
        
        order2 = next(r for r in result if r["order_num"] == 2)
        assert len(order2["ny_customer"]) == 0  # Bob is in LA


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
