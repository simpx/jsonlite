#!/usr/bin/env python3
"""
JSONLite Basic Usage Examples

This file demonstrates common JSONLite operations for new users.
"""

from jsonlite import JSONlite
from datetime import datetime

# Initialize database
db = JSONlite("examples.db.json")

# Clear existing data for demo
db.delete_many({})

print("=" * 60)
print("JSONLite Basic Usage Examples")
print("=" * 60)

# ============================================================================
# 1. INSERT OPERATIONS
# ============================================================================
print("\n1. INSERT OPERATIONS")
print("-" * 40)

# Insert a single document
result = db.insert_one({
    "name": "Alice Johnson",
    "age": 30,
    "email": "alice@example.com",
    "created": datetime.now(),
    "tags": ["python", "database"]
})
print(f"Inserted one document with _id: {result.inserted_id}")

# Insert multiple documents
result = db.insert_many([
    {"name": "Bob Smith", "age": 25, "email": "bob@example.com", "tags": ["java"]},
    {"name": "Charlie Brown", "age": 35, "email": "charlie@example.com", "tags": ["python", "go"]},
    {"name": "Diana Prince", "age": 28, "email": "diana@example.com", "tags": ["rust"]},
    {"name": "Eve Adams", "age": 32, "email": "eve@example.com", "tags": ["python", "ml"]}
])
print(f"Inserted {len(result.inserted_ids)} documents")

# ============================================================================
# 2. FIND OPERATIONS
# ============================================================================
print("\n2. FIND OPERATIONS")
print("-" * 40)

# Find one document
doc = db.find_one({"name": "Alice Johnson"})
print(f"Found: {doc['name']}, age {doc['age']}")

# Find multiple documents
docs = db.find({"age": {"$gte": 30}})
print(f"Found {len(docs)} users aged 30 or older")

# Find with multiple conditions
docs = db.find({"age": {"$gte": 25, "$lte": 32}})
print(f"Found {len(docs)} users aged 25-32")

# Find with $in operator
docs = db.find({"name": {"$in": ["Alice Johnson", "Bob Smith"]}})
print(f"Found {len(docs)} users by name list")

# ============================================================================
# 3. CURSOR OPERATIONS (Chainable API)
# ============================================================================
print("\n3. CURSOR OPERATIONS")
print("-" * 40)

# Sort by age descending
cursor = db.find({}).sort("age", -1)
docs = cursor.toArray()
print(f"Sorted by age (DESC): {[d['name'] for d in docs]}")

# Limit results
cursor = db.find({}).sort("age", -1).limit(2)
docs = cursor.toArray()
print(f"Top 2 oldest: {[d['name'] for d in docs]}")

# Skip and limit (pagination)
cursor = db.find({}).sort("age", 1).skip(1).limit(2)
docs = cursor.toArray()
print(f"Page 2 (skip 1, limit 2): {[d['name'] for d in docs]}")

# Projection (select specific fields)
cursor = db.find({}).projection({"name": 1, "age": 1, "_id": 0})
docs = cursor.toArray()
print(f"Projected (name, age only): {docs[0]}")

# Complex chain
cursor = (db
    .find({"age": {"$gte": 25}})
    .sort("age", -1)
    .limit(3)
    .projection({"name": 1, "age": 1, "_id": 0}))
docs = cursor.toArray()
print(f"Complex query result: {docs}")

# ============================================================================
# 4. UPDATE OPERATIONS
# ============================================================================
print("\n4. UPDATE OPERATIONS")
print("-" * 40)

# Update one document
result = db.update_one(
    {"name": "Alice Johnson"},
    {"$set": {"age": 31}}
)
print(f"Updated {result.modified_count} document(s)")

# Update with $inc
result = db.update_one(
    {"name": "Bob Smith"},
    {"$inc": {"age": 1}}
)
print(f"Bob's age incremented, modified: {result.modified_count}")

# Update with $push (array)
result = db.update_one(
    {"name": "Bob Smith"},
    {"$push": {"tags": "database"}}
)
doc = db.find_one({"name": "Bob Smith"})
print(f"Bob's tags after $push: {doc['tags']}")

# Update with $addToSet (unique array element)
result = db.update_one(
    {"name": "Bob Smith"},
    {"$addToSet": {"tags": "database"}}  # Already exists, won't duplicate
)
doc = db.find_one({"name": "Bob Smith"})
print(f"Bob's tags after $addToSet: {doc['tags']}")

# Update many documents
result = db.update_many(
    {"age": {"$lt": 30}},
    {"$set": {"status": "young"}}
)
print(f"Updated {result.modified_count} documents with status='young'")

# Upsert (update or insert)
result = db.update_one(
    {"name": "Frank Miller"},
    {"$set": {"age": 40, "email": "frank@example.com"}},
    upsert=True
)
print(f"Upsert result - upserted_id: {result.upserted_id}")

# ============================================================================
# 5. DELETE OPERATIONS
# ============================================================================
print("\n5. DELETE OPERATIONS")
print("-" * 40)

# Delete one document
result = db.delete_one({"name": "Frank Miller"})
print(f"Deleted {result.deleted_count} document")

# Delete many documents
result = db.delete_many({"age": {"$lt": 28}})
print(f"Deleted {result.deleted_count} documents")

# ============================================================================
# 6. AGGREGATION PIPELINE
# ============================================================================
print("\n6. AGGREGATION PIPELINE")
print("-" * 40)

# Simple aggregation
pipeline = [
    {"$match": {"age": {"$gte": 25}}},
    {"$group": {
        "_id": "$status",
        "count": {"$sum": 1},
        "avg_age": {"$avg": "$age"}
    }},
    {"$sort": {"count": -1}}
]
results = db.aggregate(pipeline)
print(f"Aggregation by status: {results}")

# Count total
pipeline = [{"$count": "total"}]
results = db.aggregate(pipeline)
print(f"Total count: {results}")

# ============================================================================
# 7. INDEX MANAGEMENT
# ============================================================================
print("\n7. INDEX MANAGEMENT")
print("-" * 40)

# Create index
db.create_index("email")
print("Created index on 'email'")

# Create compound index
db.create_index([("last_name", 1), ("first_name", 1)])
print("Created compound index")

# List indexes
indexes = db.list_indexes()
print(f"Indexes: {[idx['name'] for idx in indexes]}")

# ============================================================================
# 8. TRANSACTIONS
# ============================================================================
print("\n8. TRANSACTIONS")
print("-" * 40)

from jsonlite import Transaction

# Initialize accounts
db.delete_many({})
db.insert_one({"name": "Alice", "balance": 1000})
db.insert_one({"name": "Bob", "balance": 500})

# Transfer money with transaction
try:
    with Transaction(db) as txn:
        txn.update_one({"name": "Alice"}, {"$inc": {"balance": -100}})
        txn.update_one({"name": "Bob"}, {"$inc": {"balance": 100}})
    print("Transaction committed successfully")
except Exception as e:
    print(f"Transaction rolled back: {e}")

# Verify balances
alice = db.find_one({"name": "Alice"})
bob = db.find_one({"name": "Bob"})
print(f"Alice balance: {alice['balance']}, Bob balance: {bob['balance']}")

# ============================================================================
# 9. QUERY CACHE
# ============================================================================
print("\n9. QUERY CACHE")
print("-" * 40)

# Enable cache
db.cache_enabled = True
db.cache_max_size = 1000

# First query (cache miss)
docs1 = db.find({"age": {"$gte": 30}})
print(f"First query returned {len(docs1)} documents")

# Second query (cache hit)
docs2 = db.find({"age": {"$gte": 30}})
print(f"Second query (cached) returned {len(docs2)} documents")

# Clear cache
db.clear_cache()
print("Cache cleared")

# ============================================================================
# 10. SPECIAL TYPES
# ============================================================================
print("\n10. SPECIAL TYPES")
print("-" * 40)

from decimal import Decimal

# DateTime
db.insert_one({"event": "meeting", "time": datetime.now()})
doc = db.find_one({"event": "meeting"})
print(f"DateTime stored and retrieved: {type(doc['time'])}")

# Decimal
db.insert_one({"product": "widget", "price": Decimal("19.99")})
doc = db.find_one({"product": "widget"})
print(f"Decimal stored and retrieved: {doc['price']} ({type(doc['price'])})")

# Binary
db.insert_one({"file": "data.bin", "content": b"binary data here"})
doc = db.find_one({"file": "data.bin"})
print(f"Binary stored and retrieved: {doc['content']} ({type(doc['content'])})")

# ============================================================================
# CLEANUP
# ============================================================================
print("\n" + "=" * 60)
print("Examples completed! Database saved to 'examples.db.json'")
print("=" * 60)
