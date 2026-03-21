# MongoDB → JSONLite Migration Guide

This guide helps you migrate from MongoDB to JSONLite with minimal code changes.

## Overview

JSONLite is designed to be API-compatible with MongoDB's pymongo driver. Most migrations require only changing the import statement and connection initialization.

---

## Quick Migration

### Before (MongoDB/pymongo)

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["mydatabase"]
collection = db["users"]

results = collection.find({"age": {"$gte": 25}})
```

### After (JSONLite)

```python
from jsonlite import JSONlite

db = JSONlite("mydatabase.json")
collection = db  # JSONLite uses database directly

results = db.find({"age": {"$gte": 25}})
```

---

## Connection & Initialization

### MongoDB

```python
from pymongo import MongoClient

# Connection string
client = MongoClient("mongodb://localhost:27017/")
client = MongoClient("mongodb://user:pass@host:27017/")

# Get database and collection
db = client["mydatabase"]
collection = db["users"]
```

### JSONLite

```python
from jsonlite import JSONlite

# File path (created automatically if doesn't exist)
db = JSONlite("mydatabase.json")
db = JSONlite("./data/users.json")

# With options
db = JSONlite("mydatabase.json", indent=2, ensure_ascii=False)
```

**Key Differences:**
- No connection string - use file path
- No separate collection object - database is the collection
- No connection pooling needed - file-based

---

## CRUD Operations

### Insert

#### Insert One

```python
# MongoDB
result = collection.insert_one({"name": "Alice", "age": 30})
print(result.inserted_id)

# JSONLite (identical)
result = db.insert_one({"name": "Alice", "age": 30})
print(result.inserted_id)
```

#### Insert Many

```python
# MongoDB
result = collection.insert_many([
    {"name": "Bob", "age": 25},
    {"name": "Charlie", "age": 35}
])
print(result.inserted_ids)

# JSONLite (identical)
result = db.insert_many([
    {"name": "Bob", "age": 25},
    {"name": "Charlie", "age": 35}
])
print(result.inserted_ids)
```

### Find

#### Find One

```python
# MongoDB
doc = collection.find_one({"name": "Alice"})
doc = collection.find_one({"age": {"$gte": 30}})

# JSONLite (identical)
doc = db.find_one({"name": "Alice"})
doc = db.find_one({"age": {"$gte": 30}})
```

#### Find Many

```python
# MongoDB
cursor = collection.find({"age": {"$gte": 25}})
for doc in cursor:
    print(doc)

# JSONLite (returns list directly)
docs = db.find({"age": {"$gte": 25}})
for doc in docs:
    print(doc)

# Or use cursor for chainable operations
cursor = db.find({"age": {"$gte": 25}}).sort("age", -1).limit(10)
docs = cursor.toArray()
```

### Update

#### Update One

```python
# MongoDB
result = collection.update_one(
    {"name": "Alice"},
    {"$set": {"age": 31}}
)
print(result.matched_count, result.modified_count)

# JSONLite (identical)
result = db.update_one(
    {"name": "Alice"},
    {"$set": {"age": 31}}
)
print(result.matched_count, result.modified_count)
```

#### Update Many

```python
# MongoDB
result = collection.update_many(
    {"status": "inactive"},
    {"$set": {"status": "archived"}}
)

# JSONLite (identical)
result = db.update_many(
    {"status": "inactive"},
    {"$set": {"status": "archived"}}
)
```

#### Upsert

```python
# MongoDB
result = collection.update_one(
    {"name": "David"},
    {"$set": {"age": 40}},
    upsert=True
)

# JSONLite (identical)
result = db.update_one(
    {"name": "David"},
    {"$set": {"age": 40}},
    upsert=True
)
```

### Delete

```python
# MongoDB
result = collection.delete_one({"name": "Alice"})
result = collection.delete_many({"status": "deleted"})

# JSONLite (identical)
result = db.delete_one({"name": "Alice"})
result = db.delete_many({"status": "deleted"})
```

---

## Query Operators

All MongoDB query operators are supported:

### Comparison

```python
# All these work identically in both
{"age": {"$eq": 30}}
{"age": {"$ne": 30}}
{"age": {"$gt": 30}}
{"age": {"$gte": 30}}
{"age": {"$lt": 30}}
{"age": {"$lte": 30}}
{"age": {"$in": [25, 30, 35]}}
{"age": {"$nin": [20, 25]}}
```

### Logical

```python
# AND (implicit)
{"age": 30, "status": "active"}

# Explicit operators
{"$and": [{"age": 30}, {"status": "active"}]}
{"$or": [{"age": 25}, {"age": 30}]}
{"$nor": [{"age": 25}, {"age": 30}]}
{"$not": {"$gte": 30}}
```

### Element

```python
{"email": {"$exists": True}}
{"email": {"$exists": False}}
```

### Array

```python
{"tags": "python"}  # Contains element
{"tags": {"$all": ["python", "database"]}}
{"tags": {"$size": 3}}  # Via $expr
```

### Regular Expressions

```python
# MongoDB
{"name": {"$regex": "^A", "$options": "i"}}

# JSONLite (identical)
{"name": {"$regex": "^A", "$options": "i"}}
```

---

## Update Operators

### Field Updates

```python
# All these work identically
{"$set": {"age": 30}}
{"$unset": {"temp": ""}}
{"$inc": {"views": 1}}
{"$rename": {"old_name": "new_name"}}
{"$max": {"score": 100}}
{"$min": {"score": 0}}
```

### Array Updates

```python
# All these work identically
{"$push": {"tags": "python"}}
{"$pull": {"tags": "python"}}
{"$addToSet": {"tags": "python"}}
{"$pop": {"items": 1}}    # 1 = last, -1 = first
{"$pullAll": {"tags": ["python", "java"]}}
```

### Nested Fields

```python
# Dot notation works in both
{"$set": {"address.city": "New York", "address.zip": "10001"}}
```

---

## Cursor Operations

### MongoDB

```python
cursor = collection.find({"age": {"$gte": 25}})
cursor = cursor.sort("age", -1)
cursor = cursor.skip(10)
cursor = cursor.limit(20)
cursor = cursor.projection({"name": 1, "age": 1})

for doc in cursor:
    print(doc)
```

### JSONLite

```python
# Method chaining (more concise)
cursor = db.find({"age": {"$gte": 25}})
    .sort("age", -1)
    .skip(10)
    .limit(20)
    .projection({"name": 1, "age": 1})

docs = cursor.toArray()

# Or direct list
docs = db.find({"age": {"$gte": 25}})
```

---

## Aggregation Pipeline

### Basic Aggregation

```python
# MongoDB
pipeline = [
    {"$match": {"age": {"$gte": 25}}},
    {"$group": {
        "_id": "$status",
        "count": {"$sum": 1},
        "avg_age": {"$avg": "$age"}
    }},
    {"$sort": {"count": -1}},
    {"$limit": 10}
]
results = collection.aggregate(pipeline)

# JSONLite (identical)
pipeline = [
    {"$match": {"age": {"$gte": 25}}},
    {"$group": {
        "_id": "$status",
        "count": {"$sum": 1},
        "avg_age": {"$avg": "$age"}
    }},
    {"$sort": {"count": -1}},
    {"$limit": 10}
]
results = db.aggregate(pipeline)
```

### Supported Stages

| Stage | MongoDB | JSONLite |
|-------|---------|----------|
| `$match` | ✅ | ✅ |
| `$group` | ✅ | ✅ |
| `$project` | ✅ | ✅ |
| `$sort` | ✅ | ✅ |
| `$skip` | ✅ | ✅ |
| `$limit` | ✅ | ✅ |
| `$count` | ✅ | ✅ |
| `$unwind` | ✅ | ✅ |

### Group Accumulators

```python
# All these work in both
{"$sum": "$amount"}
{"$avg": "$amount"}
{"$min": "$amount"}
{"$max": "$amount"}
{"$count": 1}
{"$first": "$$ROOT"}
{"$last": "$$ROOT"}
{"$push": "$name"}
```

---

## Index Management

### Create Index

```python
# MongoDB
collection.create_index("name")
collection.create_index([("last_name", 1), ("first_name", 1)])
collection.create_index("email", unique=True)
collection.create_index("optional_field", sparse=True)

# JSONLite (identical)
db.create_index("name")
db.create_index([("last_name", 1), ("first_name", 1)])
db.create_index("email", unique=True)
db.create_index("optional_field", sparse=True)
```

### Drop Index

```python
# MongoDB
collection.drop_index("name_1")
collection.drop_indexes()

# JSONLite (identical)
db.drop_index("name_1")
db.drop_indexes()
```

### List Indexes

```python
# MongoDB
indexes = collection.list_indexes()

# JSONLite (identical)
indexes = db.list_indexes()
```

---

## Transactions

### MongoDB

```python
with client.start_session() as session:
    with session.start_transaction():
        collection.update_one(
            {"name": "Alice"},
            {"$inc": {"balance": -100}},
            session=session
        )
        collection.update_one(
            {"name": "Bob"},
            {"$inc": {"balance": 100}},
            session=session
        )
```

### JSONLite

```python
from jsonlite import Transaction

with Transaction(db) as txn:
    txn.update_one(
        {"name": "Alice"},
        {"$inc": {"balance": -100}}
    )
    txn.update_one(
        {"name": "Bob"},
        {"$inc": {"balance": 100}}
    )
```

---

## Special Types

### DateTime

```python
from datetime import datetime

# MongoDB
doc = {"created": datetime.now()}
collection.insert_one(doc)

# JSONLite (identical)
doc = {"created": datetime.now()}
db.insert_one(doc)
```

### Decimal

```python
from decimal import Decimal

# MongoDB
doc = {"price": Decimal("19.99")}
collection.insert_one(doc)

# JSONLite (identical)
doc = {"price": Decimal("19.99")}
db.insert_one(doc)
```

### Binary

```python
# MongoDB
doc = {"data": b"binary data"}
collection.insert_one(doc)

# JSONLite (identical)
doc = {"data": b"binary data"}
db.insert_one(doc)
```

---

## Compatibility Matrix

| Feature | MongoDB | JSONLite | Notes |
|---------|---------|----------|-------|
| CRUD Operations | ✅ | ✅ | 100% compatible |
| Query Operators | ✅ | ✅ | All comparison, logical, element operators |
| Update Operators | ✅ | ✅ | All field and array operators |
| Cursor API | ✅ | ✅ | sort, limit, skip, projection |
| Aggregation | ✅ | ✅ | Core stages supported |
| Indexes | ✅ | ✅ | Single, compound, unique, sparse |
| Transactions | ✅ | ✅ | Atomic multi-operation |
| Full-Text Search | ✅ | ✅ | Basic text search |
| GridFS | ✅ | ❌ | Not applicable (file-based) |
| Change Streams | ✅ | ❌ | Not implemented |
| Geospatial | ✅ | ❌ | Planned for v1.1 |
| TTL Indexes | ✅ | ❌ | Not implemented |

---

## Migration Checklist

- [ ] Replace `pymongo` import with `jsonlite`
- [ ] Change connection initialization to file path
- [ ] Remove collection references (use database directly)
- [ ] Test all CRUD operations
- [ ] Verify query operator behavior
- [ ] Test aggregation pipelines
- [ ] Validate index creation
- [ ] Test transaction rollback behavior
- [ ] Update connection configuration
- [ ] Run full test suite

---

## Performance Considerations

### When to Use JSONLite

✅ **Good fit:**
- Local development and testing
- Small to medium datasets (< 100k documents)
- Single-machine deployments
- Simple embedded database needs
- Prototyping and MVPs

❌ **Consider MongoDB when:**
- Distributed deployment needed
- Very large datasets (> 1M documents)
- High concurrent write load
- Advanced features (change streams, geospatial)
- Production scale applications

### Optimization Tips

1. **Use indexes** for frequently queried fields
2. **Batch operations** with `insert_many`/`update_many`
3. **Enable query cache** for repeated queries
4. **Use projection** to fetch only needed fields
5. **Limit result sets** to reduce memory usage

---

## Troubleshooting

### Common Issues

**Issue:** `ImportError: No module named 'jsonlite'`

**Solution:**
```bash
pip install jsonlite
```

**Issue:** Performance degradation with large datasets

**Solution:**
```python
# Add indexes for queried fields
db.create_index("email")
db.create_index([("last_name", 1), ("first_name", 1)])

# Enable query cache
db.cache_enabled = True
```

**Issue:** File locking conflicts

**Solution:**
```python
# Ensure proper transaction usage
from jsonlite import Transaction

with Transaction(db) as txn:
    # Atomic operations
    pass
```

---

## Getting Help

- **Documentation:** See [API_REFERENCE.md](./API_REFERENCE.md)
- **Examples:** Check `examples/` directory
- **Issues:** https://github.com/simpx/jsonlite/issues
- **Roadmap:** See [ROADMAP.md](../ROADMAP.md)
