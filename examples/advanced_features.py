#!/usr/bin/env python3
"""
JSONLite Advanced Features Examples

Demonstrates advanced JSONLite features including:
- Complex aggregation pipelines
- Index optimization
- Transaction rollback scenarios
- Query cache performance
- Full-text search
"""

from jsonlite import JSONlite, Transaction
from datetime import datetime, timedelta
from decimal import Decimal
import time

# Initialize database
db = JSONlite("advanced_examples.db.json")

# Clear existing data
db.delete_many({})

print("=" * 60)
print("JSONLite Advanced Features Examples")
print("=" * 60)

# ============================================================================
# 1. COMPLEX AGGREGATION PIPELINES
# ============================================================================
print("\n1. COMPLEX AGGREGATION PIPELINES")
print("-" * 40)

# Insert sample sales data
sales_data = [
    {"product": "laptop", "category": "electronics", "price": 999.99, "quantity": 2, "date": "2026-03-01", "region": "north"},
    {"product": "mouse", "category": "electronics", "price": 29.99, "quantity": 10, "date": "2026-03-01", "region": "south"},
    {"product": "keyboard", "category": "electronics", "price": 79.99, "quantity": 5, "date": "2026-03-02", "region": "north"},
    {"product": "desk", "category": "furniture", "price": 299.99, "quantity": 3, "date": "2026-03-02", "region": "east"},
    {"product": "chair", "category": "furniture", "price": 199.99, "quantity": 8, "date": "2026-03-03", "region": "south"},
    {"product": "monitor", "category": "electronics", "price": 399.99, "quantity": 4, "date": "2026-03-03", "region": "north"},
    {"product": "lamp", "category": "furniture", "price": 49.99, "quantity": 15, "date": "2026-03-04", "region": "west"},
    {"product": "headphones", "category": "electronics", "price": 149.99, "quantity": 6, "date": "2026-03-04", "region": "south"},
]

db.insert_many(sales_data)
print(f"Inserted {len(sales_data)} sales records")

# Aggregation 1: Group by category with multiple accumulators
pipeline = [
    {"$group": {
        "_id": "$category",
        "total_revenue": {"$sum": {"$multiply": ["$price", "$quantity"]}},
        "total_quantity": {"$sum": "$quantity"},
        "avg_price": {"$avg": "$price"},
        "min_price": {"$min": "$price"},
        "max_price": {"$max": "$price"},
        "product_count": {"$sum": 1}
    }},
    {"$sort": {"total_revenue": -1}}
]
results = db.aggregate(pipeline)
print("\nSales by Category:")
for r in results:
    print(f"  {r['_id']}: ${r['total_revenue']:.2f} revenue, {r['total_quantity']} units")

# Aggregation 2: Group by region and category (multi-field grouping)
pipeline = [
    {"$group": {
        "_id": {"region": "$region", "category": "$category"},
        "revenue": {"$sum": {"$multiply": ["$price", "$quantity"]}}
    }},
    {"$sort": {"_id.region": 1, "revenue": -1}}
]
results = db.aggregate(pipeline)
print("\nSales by Region & Category:")
for r in results:
    print(f"  {r['_id']['region']} - {r['_id']['category']}: ${r['revenue']:.2f}")

# Aggregation 3: Project with computed fields
pipeline = [
    {"$project": {
        "product": 1,
        "unit_price": "$price",
        "quantity": 1,
        "total": {"$multiply": ["$price", "$quantity"]},
        "category": 1,
        "price_tier": {
            "$cond": [
                {"$gte": ["$price", 300]},
                "premium",
                {"$cond": [{"$gte": ["$price", 100]}, "mid-range", "budget"]}
            ]
        }
    }}
]
results = db.aggregate(pipeline)
print("\nProducts with Price Tiers:")
for r in results:
    print(f"  {r['product']}: ${r['total']:.2f} ({r['price_tier']})")

# Aggregation 4: Unwind array (simulate with nested data)
db.delete_many({})
users = [
    {"name": "Alice", "skills": ["python", "java", "sql"]},
    {"name": "Bob", "skills": ["javascript", "react", "node"]},
    {"name": "Charlie", "skills": ["python", "ml", "data"]},
]
db.insert_many(users)

pipeline = [
    {"$unwind": "$skills"},
    {"$group": {
        "_id": "$skills",
        "users": {"$push": "$name"},
        "count": {"$sum": 1}
    }},
    {"$sort": {"count": -1}}
]
results = db.aggregate(pipeline)
print("\nSkills Distribution:")
for r in results:
    print(f"  {r['_id']}: {r['users']} ({r['count']} users)")

# ============================================================================
# 2. INDEX OPTIMIZATION
# ============================================================================
print("\n2. INDEX OPTIMIZATION")
print("-" * 40)

# Create large dataset for benchmark
db.delete_many({})
print("Creating benchmark dataset (10,000 records)...")

bulk_data = []
for i in range(10000):
    bulk_data.append({
        "user_id": i,
        "email": f"user{i}@example.com",
        "age": (i % 50) + 18,
        "score": (i * 17) % 1000,
        "category": f"cat_{i % 100}",
        "active": i % 3 != 0
    })

start = time.time()
db.insert_many(bulk_data)
insert_time = time.time() - start
print(f"Inserted 10,000 records in {insert_time:.3f}s")

# Query without index
start = time.time()
results = db.find({"email": "user5000@example.com"})
no_index_time = time.time() - start
print(f"Query without index: {no_index_time:.6f}s")

# Create index
start = time.time()
db.create_index("email")
index_time = time.time() - start
print(f"Index creation: {index_time:.3f}s")

# Query with index
start = time.time()
results = db.find({"email": "user5000@example.com"})
with_index_time = time.time() - start
print(f"Query with index: {with_index_time:.6f}s")

if no_index_time > 0:
    speedup = no_index_time / max(with_index_time, 0.000001)
    print(f"Speedup: {speedup:.1f}x faster")

# Compound index
db.create_index([("category", 1), ("age", 1)])
results = db.find({"category": "cat_50", "age": 25})
print(f"Compound index query returned {len(results)} results")

# ============================================================================
# 3. TRANSACTION ROLLBACK SCENARIOS
# ============================================================================
print("\n3. TRANSACTION ROLLBACK SCENARIOS")
print("-" * 40)

db.delete_many({})
db.insert_one({"account": "A", "balance": 1000})
db.insert_one({"account": "B", "balance": 1000})

print("Initial balances: A=1000, B=1000")

# Scenario 1: Successful transaction
try:
    with Transaction(db) as txn:
        txn.update_one({"account": "A"}, {"$inc": {"balance": -100}})
        txn.update_one({"account": "B"}, {"$inc": {"balance": 100}})
    print("✓ Transaction 1 committed successfully")
except Exception as e:
    print(f"✗ Transaction 1 failed: {e}")

a = db.find_one({"account": "A"})
b = db.find_one({"account": "B"})
print(f"Balances after: A={a['balance']}, B={b['balance']}")

# Scenario 2: Failed transaction (rollback)
try:
    with Transaction(db) as txn:
        txn.update_one({"account": "A"}, {"$inc": {"balance": -500}})
        txn.update_one({"account": "B"}, {"$inc": {"balance": 500}})
        # This will fail - invalid operation
        txn.insert_one({"invalid": {"$unsupported": "operation"}})
    print("✓ Transaction 2 committed")
except Exception as e:
    print(f"✗ Transaction 2 failed (expected): {type(e).__name__}")

a = db.find_one({"account": "A"})
b = db.find_one({"account": "B"})
print(f"Balances after rollback: A={a['balance']}, B={b['balance']} (unchanged)")

# ============================================================================
# 4. QUERY CACHE PERFORMANCE
# ============================================================================
print("\n4. QUERY CACHE PERFORMANCE")
print("-" * 40)

db.cache_enabled = True
db.cache_max_size = 100

# Warm up cache
print("Warming up cache...")
for _ in range(3):
    db.find({"category": "cat_50"})

# Measure cached query performance
times = []
for i in range(10):
    start = time.time()
    db.find({"category": "cat_50"})
    times.append(time.time() - start)

avg_time = sum(times) / len(times)
print(f"Average cached query time: {avg_time*1000:.3f}ms")
print(f"Cache enabled: {db.cache_enabled}, Max size: {db.cache_max_size}")

# Clear and test uncached
db.clear_cache()
start = time.time()
db.find({"category": "cat_50"})
uncached_time = time.time() - start
print(f"Uncached query time: {uncached_time*1000:.3f}ms")

# ============================================================================
# 5. FULL-TEXT SEARCH
# ============================================================================
print("\n5. FULL-TEXT SEARCH")
print("-" * 40)

db.delete_many({})

# Insert documents with text content
articles = [
    {"title": "Python Database Tutorial", "content": "Learn how to use Python with databases including MongoDB and SQLite", "tags": ["python", "database", "tutorial"]},
    {"title": "Advanced JavaScript", "content": "Deep dive into JavaScript closures, promises, and async programming", "tags": ["javascript", "advanced"]},
    {"title": "Machine Learning Basics", "content": "Introduction to machine learning with Python, scikit-learn, and neural networks", "tags": ["ml", "python", "ai"]},
    {"title": "Web Development Guide", "content": "Full stack web development with React, Node.js, and MongoDB", "tags": ["web", "javascript", "fullstack"]},
    {"title": "Data Science with Python", "content": "Data analysis, visualization, and machine learning using Python pandas and numpy", "tags": ["python", "data", "science"]},
]

db.insert_many(articles)
print(f"Inserted {len(articles)} articles")

# Search for "python"
results = db.find({"$text": {"$search": "python"}})
print(f"\nSearch 'python': Found {len(results)} articles")
for r in results:
    print(f"  - {r['title']}")

# Search for "database"
results = db.find({"$text": {"$search": "database"}})
print(f"\nSearch 'database': Found {len(results)} articles")
for r in results:
    print(f"  - {r['title']}")

# ============================================================================
# 6. COMPLEX QUERY OPERATORS
# ============================================================================
print("\n6. COMPLEX QUERY OPERATORS")
print("-" * 40)

db.delete_many({})

# Insert test data
users = [
    {"name": "Alice", "age": 30, "status": "active", "score": 85, "tags": ["python", "java"]},
    {"name": "Bob", "age": 25, "status": "inactive", "score": 92, "tags": ["javascript"]},
    {"name": "Charlie", "age": 35, "status": "active", "score": 78, "tags": ["python", "go"]},
    {"name": "Diana", "age": 28, "status": "active", "score": 95, "tags": ["rust", "python"]},
    {"name": "Eve", "age": 32, "status": "inactive", "score": 88, "tags": ["java", "scala"]},
]
db.insert_many(users)

# $or query
results = db.find({"$or": [{"age": {"$lt": 27}}, {"score": {"$gte": 90}}]})
print(f"$or (age<27 OR score>=90): {[r['name'] for r in results]}")

# $and query
results = db.find({"$and": [{"status": "active"}, {"score": {"$gte": 85}}]})
print(f"$and (active AND score>=85): {[r['name'] for r in results]}")

# $nor query
results = db.find({"$nor": [{"status": "inactive"}]})
print(f"$nor (NOT inactive): {[r['name'] for r in results]}")

# $not with operator
results = db.find({"score": {"$not": {"$lt": 85}}})
print(f"$not (score NOT < 85): {[r['name'] for r in results]}")

# $all (array contains all)
results = db.find({"tags": {"$all": ["python", "java"]}})
print(f"$all (tags has python AND java): {[r['name'] for r in results]}")

# $exists
results = db.find({"email": {"$exists": False}})
print(f"$exists (no email field): {len(results)} users")

# ============================================================================
# 7. NESTED FIELD OPERATIONS
# ============================================================================
print("\n7. NESTED FIELD OPERATIONS")
print("-" * 40)

db.delete_many({})

# Insert documents with nested structure
employees = [
    {"name": "Alice", "address": {"city": "New York", "zip": "10001", "country": "USA"}, "contact": {"email": "alice@example.com", "phone": "123-456"}},
    {"name": "Bob", "address": {"city": "London", "zip": "SW1A", "country": "UK"}, "contact": {"email": "bob@example.com", "phone": "234-567"}},
    {"name": "Charlie", "address": {"city": "Paris", "zip": "75001", "country": "France"}, "contact": {"email": "charlie@example.com", "phone": "345-678"}},
]
db.insert_many(employees)

# Query nested field
results = db.find({"address.city": "London"})
print(f"Find by nested city: {[r['name'] for r in results]}")

# Update nested field
db.update_one(
    {"name": "Alice"},
    {"$set": {"address.zip": "10002", "contact.phone": "999-999"}}
)
alice = db.find_one({"name": "Alice"})
print(f"Updated Alice: zip={alice['address']['zip']}, phone={alice['contact']['phone']}")

# Projection on nested fields
cursor = db.find({}).projection({"name": 1, "address.city": 1, "contact.email": 1, "_id": 0})
docs = cursor.toArray()
print(f"Projected nested fields: {docs[0]}")

# ============================================================================
# CLEANUP
# ============================================================================
print("\n" + "=" * 60)
print("Advanced examples completed!")
print(f"Databases saved to: advanced_examples.db.json")
print("=" * 60)
