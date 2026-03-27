"""Tests for $facet aggregation stage."""

import pytest
import os
import shutil
from jsonlite import JSONlite, MongoClient


class TestFacetBasic:
    """Test basic $facet functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.test_dir = tmp_path / "facet_test"
        self.test_dir.mkdir()
        
        # Create products collection
        self.products_path = str(self.test_dir / "products.json")
        self.products = JSONlite(self.products_path)
        self.products.insert_many([
            {"product_id": 1, "name": "Laptop", "category": "electronics", "price": 999.99, "stock": 50},
            {"product_id": 2, "name": "Phone", "category": "electronics", "price": 699.99, "stock": 100},
            {"product_id": 3, "name": "Headphones", "category": "electronics", "price": 199.99, "stock": 200},
            {"product_id": 4, "name": "Desk Chair", "category": "furniture", "price": 299.99, "stock": 30},
            {"product_id": 5, "name": "Standing Desk", "category": "furniture", "price": 599.99, "stock": 20},
            {"product_id": 6, "name": "Monitor", "category": "electronics", "price": 449.99, "stock": 75},
            {"product_id": 7, "name": "Keyboard", "category": "electronics", "price": 149.99, "stock": 150},
            {"product_id": 8, "name": "Bookshelf", "category": "furniture", "price": 199.99, "stock": 40},
            {"product_id": 9, "name": "Mouse", "category": "electronics", "price": 79.99, "stock": 300},
            {"product_id": 10, "name": "Desk Lamp", "category": "furniture", "price": 49.99, "stock": 100},
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_facet_multiple_pipelines(self):
        """Test $facet running multiple independent pipelines."""
        result = self.products.aggregate([
            {
                "$facet": {
                    "by_category": [
                        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                        {"$sort": {"_id": 1}}
                    ],
                    "expensive_products": [
                        {"$match": {"price": {"$gte": 500}}},
                        {"$project": {"_id": 0, "name": 1, "price": 1}}
                    ],
                    "total_count": [
                        {"$count": "total"}
                    ]
                }
            }
        ]).first()
        
        # Check by_category facet
        assert "by_category" in result
        assert len(result["by_category"]) == 2  # electronics and furniture
        
        categories = {item["_id"]: item["count"] for item in result["by_category"]}
        assert categories["electronics"] == 6
        assert categories["furniture"] == 4
        
        # Check expensive_products facet
        assert "expensive_products" in result
        assert len(result["expensive_products"]) == 3  # Laptop, Phone, Standing Desk (Monitor is 449.99 < 500)
        expensive_names = {p["name"] for p in result["expensive_products"]}
        assert "Laptop" in expensive_names
        assert "Phone" in expensive_names
        assert "Standing Desk" in expensive_names
        
        # Check total_count facet
        assert "total_count" in result
        assert len(result["total_count"]) == 1
        assert result["total_count"][0]["total"] == 10
    
    def test_facet_empty_results(self):
        """Test $facet when some pipelines return no results."""
        result = self.products.aggregate([
            {
                "$facet": {
                    "cheap_items": [
                        {"$match": {"price": {"$lt": 10}}}
                    ],
                    "all_items": [
                        {"$limit": 3}
                    ]
                }
            }
        ]).first()
        
        # cheap_items should be empty
        assert result["cheap_items"] == []
        
        # all_items should have 3 items
        assert len(result["all_items"]) == 3
    
    def test_facet_with_match_and_group(self):
        """Test $facet with complex match and group operations."""
        result = self.products.aggregate([
            {
                "$facet": {
                    "electronics_stats": [
                        {"$match": {"category": "electronics"}},
                        {"$group": {
                            "_id": None,
                            "avg_price": {"$avg": "$price"},
                            "total_stock": {"$sum": "$stock"},
                            "count": {"$sum": 1}
                        }}
                    ],
                    "furniture_stats": [
                        {"$match": {"category": "furniture"}},
                        {"$group": {
                            "_id": None,
                            "avg_price": {"$avg": "$price"},
                            "total_stock": {"$sum": "$stock"},
                            "count": {"$sum": 1}
                        }}
                    ]
                }
            }
        ]).first()
        
        # Check electronics stats
        assert len(result["electronics_stats"]) == 1
        electronics = result["electronics_stats"][0]
        assert electronics["count"] == 6
        assert electronics["total_stock"] == 50 + 100 + 200 + 75 + 150 + 300  # 875
        assert abs(electronics["avg_price"] - 429.99) < 0.01  # (999.99+699.99+199.99+449.99+149.99+79.99)/6
        
        # Check furniture stats
        assert len(result["furniture_stats"]) == 1
        furniture = result["furniture_stats"][0]
        assert furniture["count"] == 4
        assert furniture["total_stock"] == 30 + 20 + 40 + 100  # 190
        assert abs(furniture["avg_price"] - 287.49) < 0.01  # (299.99+599.99+199.99+49.99)/4


class TestFacetAdvanced:
    """Test advanced $facet scenarios."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.test_dir = tmp_path / "facet_adv_test"
        self.test_dir.mkdir()
        
        # Create orders collection
        self.orders_path = str(self.test_dir / "orders.json")
        self.orders = JSONlite(self.orders_path)
        self.orders.insert_many([
            {"order_id": 1, "customer": "Alice", "amount": 150.00, "status": "completed", "items": 3},
            {"order_id": 2, "customer": "Bob", "amount": 75.50, "status": "pending", "items": 2},
            {"order_id": 3, "customer": "Alice", "amount": 200.00, "status": "completed", "items": 5},
            {"order_id": 4, "customer": "Charlie", "amount": 50.00, "status": "cancelled", "items": 1},
            {"order_id": 5, "customer": "Bob", "amount": 300.00, "status": "completed", "items": 8},
            {"order_id": 6, "customer": "Alice", "amount": 125.00, "status": "pending", "items": 4},
            {"order_id": 7, "customer": "Diana", "amount": 450.00, "status": "completed", "items": 10},
            {"order_id": 8, "customer": "Charlie", "amount": 80.00, "status": "completed", "items": 2},
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_facet_customer_analysis(self):
        """Test $facet for multi-dimensional customer analysis."""
        result = self.orders.aggregate([
            {
                "$facet": {
                    "by_customer": [
                        {"$group": {
                            "_id": "$customer",
                            "total_spent": {"$sum": "$amount"},
                            "order_count": {"$sum": 1},
                            "avg_order": {"$avg": "$amount"}
                        }},
                        {"$sort": {"total_spent": -1}}
                    ],
                    "by_status": [
                        {"$group": {
                            "_id": "$status",
                            "count": {"$sum": 1},
                            "total_revenue": {"$sum": "$amount"}
                        }}
                    ],
                    "top_orders": [
                        {"$sort": {"amount": -1}},
                        {"$limit": 3},
                        {"$project": {"_id": 1, "customer": 1, "amount": 1}}
                    ]
                }
            }
        ]).first()
        
        # Check by_customer
        assert len(result["by_customer"]) == 4  # Alice, Bob, Charlie, Diana
        
        customer_totals = {c["_id"]: c["total_spent"] for c in result["by_customer"]}
        assert customer_totals["Alice"] == 150.00 + 200.00 + 125.00  # 475.00
        assert customer_totals["Bob"] == 75.50 + 300.00  # 375.50
        assert customer_totals["Diana"] == 450.00
        assert customer_totals["Charlie"] == 50.00 + 80.00  # 130.00
        
        # Alice should be first (highest total: 475.00)
        assert result["by_customer"][0]["_id"] == "Alice"
        
        # Check by_status
        status_map = {s["_id"]: s["count"] for s in result["by_status"]}
        assert status_map["completed"] == 5
        assert status_map["pending"] == 2
        assert status_map["cancelled"] == 1
        
        # Check top_orders
        assert len(result["top_orders"]) == 3
        assert result["top_orders"][0]["amount"] == 450.00  # Diana
        assert result["top_orders"][1]["amount"] == 300.00  # Bob
        assert result["top_orders"][2]["amount"] == 200.00  # Alice
    
    def test_facet_with_lookup(self):
        """Test $facet combined with $lookup."""
        # Create customers collection
        customers_path = str(self.test_dir / "customers.json")
        customers = JSONlite(customers_path)
        customers.insert_many([
            {"customer_id": "Alice", "email": "alice@example.com", "tier": "gold"},
            {"customer_id": "Bob", "email": "bob@example.com", "tier": "silver"},
            {"customer_id": "Charlie", "email": "charlie@example.com", "tier": "bronze"},
            {"customer_id": "Diana", "email": "diana@example.com", "tier": "gold"},
        ])
        
        result = self.orders.aggregate([
            {
                "$facet": {
                    "with_customer_info": [
                        {
                            "$lookup": {
                                "from": "customers",
                                "localField": "customer",
                                "foreignField": "customer_id",
                                "as": "customer_details"
                            }
                        },
                        {"$limit": 2}
                    ],
                    "order_summary": [
                        {"$group": {
                            "_id": None,
                            "total_orders": {"$sum": 1},
                            "total_revenue": {"$sum": "$amount"}
                        }}
                    ]
                }
            }
        ]).first()
        
        # Check with_customer_info has lookup results
        assert len(result["with_customer_info"]) == 2
        for order in result["with_customer_info"]:
            assert "customer_details" in order
            assert len(order["customer_details"]) == 1
        
        # Check order_summary
        assert len(result["order_summary"]) == 1
        summary = result["order_summary"][0]
        assert summary["total_orders"] == 8
        assert abs(summary["total_revenue"] - 1430.50) < 0.01
    
    def test_facet_nested_facets(self):
        """Test $facet with nested $facet stages."""
        result = self.orders.aggregate([
            {
                "$facet": {
                    "completed_orders": [
                        {"$match": {"status": "completed"}},
                        {
                            "$facet": {
                                "by_customer": [
                                    {"$group": {"_id": "$customer", "count": {"$sum": 1}}}
                                ],
                                "total_revenue": [
                                    {"$group": {"_id": None, "sum": {"$sum": "$amount"}}}
                                ]
                            }
                        }
                    ],
                    "all_orders_count": [
                        {"$count": "total"}
                    ]
                }
            }
        ]).first()
        
        # Check nested facet results
        assert len(result["completed_orders"]) == 1
        nested = result["completed_orders"][0]
        
        assert "by_customer" in nested
        assert len(nested["by_customer"]) == 4  # Alice, Bob, Charlie, Diana all have completed orders
        
        assert "total_revenue" in nested
        assert len(nested["total_revenue"]) == 1
        # Sum of completed orders: 150+200+300+450+80 = 1180
        assert abs(nested["total_revenue"][0]["sum"] - 1180.00) < 0.01
        
        # Check all_orders_count
        assert result["all_orders_count"][0]["total"] == 8


class TestFacetEdgeCases:
    """Test edge cases for $facet."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.test_dir = tmp_path / "facet_edge_test"
        self.test_dir.mkdir()
        
        self.db = JSONlite(str(self.test_dir / "test.json"))
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_facet_empty_input(self):
        """Test $facet with empty input collection."""
        # Don't insert any data
        
        result = self.db.aggregate([
            {
                "$facet": {
                    "results": [
                        {"$match": {"status": "active"}}
                    ],
                    "count": [
                        {"$count": "total"}
                    ]
                }
            }
        ]).first()
        
        # Should still produce one result document with empty arrays
        assert result["results"] == []
        assert len(result["count"]) == 1
        assert result["count"][0]["total"] == 0
    
    def test_facet_single_pipeline(self):
        """Test $facet with only one pipeline."""
        self.db.insert_many([
            {"item_id": 1, "value": 10},
            {"item_id": 2, "value": 20},
            {"item_id": 3, "value": 30},
        ])
        
        result = self.db.aggregate([
            {
                "$facet": {
                    "doubled": [
                        {"$project": {"_id": 0, "doubled": {"$multiply": ["$value", 2]}}}
                    ]
                }
            }
        ]).first()
        
        assert len(result["doubled"]) == 3
        values = [r["doubled"] for r in result["doubled"]]
        assert 20 in values
        assert 40 in values
        assert 60 in values
    
    def test_facet_with_skip_and_limit(self):
        """Test $facet with pagination operators."""
        self.db.insert_many([
            {"item_id": i, "value": i * 10} for i in range(1, 11)  # 10 documents
        ])
        
        result = self.db.aggregate([
            {
                "$facet": {
                    "first_half": [
                        {"$sort": {"item_id": 1}},
                        {"$skip": 0},
                        {"$limit": 5}
                    ],
                    "second_half": [
                        {"$sort": {"item_id": 1}},
                        {"$skip": 5},
                        {"$limit": 5}
                    ]
                }
            }
        ]).first()
        
        assert len(result["first_half"]) == 5
        assert len(result["second_half"]) == 5
        
        first_ids = [r["item_id"] for r in result["first_half"]]
        second_ids = [r["item_id"] for r in result["second_half"]]
        
        assert first_ids == [1, 2, 3, 4, 5]
        assert second_ids == [6, 7, 8, 9, 10]


class TestFacetMongoClient:
    """Test $facet with MongoClient multi-database API."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database with MongoClient."""
        self.test_dir = tmp_path / "mongo_facet_test"
        self.test_dir.mkdir()
        
        self.client = MongoClient(str(self.test_dir))
        self.db = self.client["store"]
        
        # Create products collection
        self.products = self.db["products"]
        self.products.insert_many([
            {"product_id": 1, "name": "Widget", "category": "gadgets", "price": 29.99, "in_stock": True},
            {"product_id": 2, "name": "Gadget", "category": "gadgets", "price": 49.99, "in_stock": True},
            {"product_id": 3, "name": "Chair", "category": "furniture", "price": 199.99, "in_stock": False},
            {"product_id": 4, "name": "Table", "category": "furniture", "price": 299.99, "in_stock": True},
            {"product_id": 5, "name": "Lamp", "category": "lighting", "price": 39.99, "in_stock": True},
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_facet_mongo_client_api(self):
        """Test $facet through MongoClient/Collection API."""
        result = self.products.aggregate([
            {
                "$facet": {
                    "available_items": [
                        {"$match": {"in_stock": True}},
                        {"$project": {"_id": 0, "name": 1, "price": 1}}
                    ],
                    "category_breakdown": [
                        {"$group": {"_id": "$category", "count": {"$sum": 1}}}
                    ],
                    "price_range": [
                        {"$group": {
                            "_id": None,
                            "min_price": {"$min": "$price"},
                            "max_price": {"$max": "$price"},
                            "avg_price": {"$avg": "$price"}
                        }}
                    ]
                }
            }
        ]).first()
        
        # Check available_items
        assert len(result["available_items"]) == 4  # All except Chair
        
        # Check category_breakdown
        assert len(result["category_breakdown"]) == 3
        categories = {c["_id"]: c["count"] for c in result["category_breakdown"]}
        assert categories["gadgets"] == 2
        assert categories["furniture"] == 2
        assert categories["lighting"] == 1
        
        # Check price_range
        assert len(result["price_range"]) == 1
        price_info = result["price_range"][0]
        assert abs(price_info["min_price"] - 29.99) < 0.01
        assert abs(price_info["max_price"] - 299.99) < 0.01
        # Avg: (29.99 + 49.99 + 199.99 + 299.99 + 39.99) / 5 = 123.99
        assert abs(price_info["avg_price"] - 123.99) < 0.01
