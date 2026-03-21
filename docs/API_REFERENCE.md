# JSONLite API Reference

Complete API documentation for JSONLite v1.0.0

## Table of Contents

- [Database Operations](#database-operations)
- [Document Operations](#document-operations)
- [Query Operators](#query-operators)
- [Update Operators](#update-operators)
- [Cursor API](#cursor-api)
- [Aggregation Pipeline](#aggregation-pipeline)
- [Index Management](#index-management)
- [Transactions](#transactions)
- [Configuration](#configuration)

---

## Database Operations

### Initialize Database

```python
from jsonlite import JSONlite

# Create or open a database
db = JSONlite('mydatabase.json')

# With custom options
db = JSONlite('mydatabase.json', indent=2, ensure_ascii=False)
```

**Parameters:**
- `path` (str): Path to the JSON file
- `indent` (int, optional): JSON indentation level (default: 2)
- `ensure_ascii` (bool, optional): Escape non-ASCII characters (default: False)

---

## Document Operations

### Insert Operations

#### insert_one()
Insert a single document.

```python
result = db.insert_one({"name": "Alice", "age": 30})
print(result.inserted_id)  # Returns the _id of inserted document
```

#### insert_many()
Insert multiple documents.

```python
result = db.insert_many([
    {"name": "Bob", "age": 25},
    {"name": "Charlie", "age": 35}
])
print(result.inserted_ids)  # [2, 3]
```

### Find Operations

#### find_one()
Find a single document matching the filter.

```python
doc = db.find_one({"name": "Alice"})
doc = db.find_one({"age": {"$gte": 30}})
```

#### find()
Find multiple documents. Returns a Cursor for chainable operations.

```python
# Returns list of documents
docs = db.find({"age": {"$gte": 25}})

# Chainable cursor
cursor = db.find({"age": {"$gte": 25}}).sort("age", -1).limit(10)
docs = cursor.toArray()
```

### Update Operations

#### update_one()
Update a single document.

```python
result = db.update_one(
    {"name": "Alice"},
    {"$set": {"age": 31}}
)
print(result.matched_count)   # 1
print(result.modified_count)  # 1
```

#### update_many()
Update multiple documents.

```python
result = db.update_many(
    {"age": {"$lt": 30}},
    {"$set": {"status": "young"}}
)
print(result.matched_count)   # Number matched
print(result.modified_count)  # Number modified
```

#### find_one_and_update()
Atomically find and update a document.

```python
doc = db.find_one_and_update(
    {"name": "Alice"},
    {"$set": {"age": 32}},
    return_document="after"  # or "before"
)
```

#### find_one_and_replace()
Atomically find and replace a document.

```python
doc = db.find_one_and_replace(
    {"name": "Alice"},
    {"name": "Alice Smith", "age": 32}
)
```

#### find_one_and_delete()
Atomically find and delete a document.

```python
doc = db.find_one_and_delete({"name": "Alice"})
```

### Delete Operations

#### delete_one()
Delete a single document.

```python
result = db.delete_one({"name": "Alice"})
print(result.deleted_count)  # 1
```

#### delete_many()
Delete multiple documents.

```python
result = db.delete_many({"age": {"$lt": 18}})
print(result.deleted_count)  # Number deleted
```

### Upsert Operations

```python
# Update or insert
result = db.update_one(
    {"name": "David"},
    {"$set": {"age": 40}},
    upsert=True
)
print(result.upserted_id)  # New _id if inserted
```

---

## Query Operators

### Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `$eq` | Equal to | `{"age": {"$eq": 30}}` |
| `$ne` | Not equal to | `{"age": {"$ne": 30}}` |
| `$gt` | Greater than | `{"age": {"$gt": 30}}` |
| `$gte` | Greater than or equal | `{"age": {"$gte": 30}}` |
| `$lt` | Less than | `{"age": {"$lt": 30}}` |
| `$lte` | Less than or equal | `{"age": {"$lte": 30}}` |
| `$in` | In array | `{"age": {"$in": [25, 30, 35]}}` |
| `$nin` | Not in array | `{"age": {"$nin": [25, 30]}}` |

### Logical Operators

```python
# AND (implicit)
db.find({"age": 30, "status": "active"})

# Explicit AND
db.find({"$and": [{"age": 30}, {"status": "active"}]})

# OR
db.find({"$or": [{"age": 25}, {"age": 30}]})

# NOR
db.find({"$nor": [{"age": 25}, {"age": 30}]})

# NOT
db.find({"age": {"$not": {"$gte": 30}}})
```

### Element Operators

```python
# Exists
db.find({"email": {"$exists": True}})

# Type (limited support)
db.find({"created": {"$exists": True}})
```

### Array Operators

```python
# Contains element
db.find({"tags": "python"})

# Contains all elements
db.find({"tags": {"$all": ["python", "database"]}})

# Array size (via expression)
db.find({"$expr": {"$eq": [{"$size": "$tags"}, 3]}})
```

### Regular Expressions

```python
# Regex match
db.find({"name": {"$regex": "^A", "$options": "i"}})

# Options: i (case-insensitive), m (multiline), s (dotall)
```

### Full-Text Search

```python
# Search across all text fields
db.find({"$text": {"$search": "python database"}})
```

---

## Update Operators

### Field Update Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `$set` | Set field value | `{"$set": {"age": 30}}` |
| `$unset` | Remove field | `{"$unset": {"temp": ""}}` |
| `$inc` | Increment value | `{"$inc": {"views": 1}}` |
| `$rename` | Rename field | `{"$rename": {"old": "new"}}` |
| `$max` | Max value update | `{"$max": {"score": 100}}` |
| `$min` | Min value update | `{"$min": {"score": 0}}` |

### Array Update Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `$push` | Add to array | `{"$push": {"tags": "python"}}` |
| `$pull` | Remove from array | `{"$pull": {"tags": "python"}}` |
| `$addToSet` | Add unique element | `{"$addToSet": {"tags": "python"}}` |
| `$pop` | Remove first/last | `{"$pop": {"items": 1}}` (1=last, -1=first) |
| `$pullAll` | Batch remove | `{"$pullAll": {"tags": ["python", "java"]}}` |

### Nested Field Updates

```python
# Dot notation for nested fields
db.update_one(
    {"name": "Alice"},
    {"$set": {"address.city": "New York", "address.zip": "10001"}}
)
```

---

## Cursor API

Chainable query operations:

```python
cursor = db.find({"age": {"$gte": 25}})
    .sort("age", -1)           # DESC: -1, ASC: 1
    .skip(10)                   # Skip first 10
    .limit(20)                  # Limit to 20
    .projection({"name": 1, "age": 1})  # Select fields

docs = cursor.toArray()
```

### Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `sort()` | `key: str`, `direction: int` | Sort by field (1=ASC, -1=DESC) |
| `skip()` | `n: int` | Skip first N documents |
| `limit()` | `n: int` | Limit results to N documents |
| `projection()` | `fields: dict` | Select/exclude fields |
| `toArray()` | - | Execute and return list |
| `count()` | - | Count matching documents |
| `first()` | - | Return first document or None |

### Multi-field Sort

```python
cursor.sort([("age", -1), ("name", 1)])  # Sort by age DESC, then name ASC
```

### Projection Examples

```python
# Include fields
.projection({"name": 1, "age": 1})

# Exclude fields
.projection({"password": 0, "internal": 0})

# Nested field projection
.projection({"name": 1, "address.city": 1, "address.zip": 1})
```

---

## Aggregation Pipeline

```python
results = db.aggregate([
    {"$match": {"age": {"$gte": 25}}},
    {"$group": {
        "_id": "$status",
        "count": {"$sum": 1},
        "avg_age": {"$avg": "$age"}
    }},
    {"$sort": {"count": -1}},
    {"$limit": 10}
])
```

### Pipeline Stages

#### $match
Filter documents (same syntax as find).

```python
{"$match": {"status": "active", "age": {"$gte": 18}}}
```

#### $group
Group documents by key.

```python
{"$group": {
    "_id": "$category",
    "total": {"$sum": "$amount"},
    "average": {"$avg": "$amount"},
    "min_val": {"$min": "$amount"},
    "max_val": {"$max": "$amount"},
    "count": {"$sum": 1},
    "first_doc": {"$first": "$$ROOT"},
    "last_doc": {"$last": "$$ROOT"},
    "items": {"$push": "$name"}
}}
```

#### $project
Select/compute fields.

```python
# Include/exclude
{"$project": {"name": 1, "age": 1, "_id": 0}}

# Computed fields
{"$project": {
    "full_name": {"$concat": ["$first_name", " ", "$last_name"]},
    "age_group": {"$cond": [{"$gt": ["$age", 30]}, "senior", "junior"]}
}}
```

#### $sort
Sort documents.

```python
{"$sort": {"age": -1, "name": 1}}
```

#### $skip / $limit
Pagination.

```python
{"$skip": 10}
{"$limit": 20}
```

#### $count
Count documents.

```python
{"$count": "total"}  # Returns [{"total": 100}]
```

#### $unwind
Deconstruct array field.

```python
{"$unwind": "$tags"}
{"$unwind": {"path": "$tags", "preserveNullAndEmptyArrays": True}}
```

---

## Index Management

### Create Index

```python
# Single field index
db.create_index("name")

# Compound index
db.create_index([("last_name", 1), ("first_name", 1)])

# Unique index
db.create_index("email", unique=True)

# Sparse index
db.create_index("optional_field", sparse=True)
```

### Drop Index

```python
# Drop specific index
db.drop_index("name_1")

# Drop all indexes
db.drop_indexes()
```

### List Indexes

```python
indexes = db.list_indexes()
for idx in indexes:
    print(idx["name"], idx["key"])
```

### Index Performance

Indexes automatically accelerate queries:

```python
# Without index: O(n) scan
db.find({"email": "user@example.com"})

# With index: O(log n) lookup
db.create_index("email")
db.find({"email": "user@example.com"})  # Much faster!
```

---

## Transactions

Atomic multi-operation transactions:

```python
from jsonlite import Transaction

# Start transaction
with Transaction(db) as txn:
    # All operations are atomic
    txn.insert_one({"name": "Alice", "balance": 1000})
    txn.insert_one({"name": "Bob", "balance": 500})
    
    # Transfer money
    txn.update_one({"name": "Alice"}, {"$inc": {"balance": -100}})
    txn.update_one({"name": "Bob"}, {"$inc": {"balance": 100}})

# If any operation fails, all changes are rolled back
```

### Transaction Methods

| Method | Description |
|--------|-------------|
| `insert_one()` | Insert within transaction |
| `insert_many()` | Insert multiple within transaction |
| `update_one()` | Update within transaction |
| `update_many()` | Update multiple within transaction |
| `delete_one()` | Delete within transaction |
| `delete_many()` | Delete multiple within transaction |
| `find_one()` | Find within transaction |
| `find()` | Find multiple within transaction |

### Error Handling

```python
try:
    with Transaction(db) as txn:
        txn.update_one({"name": "Alice"}, {"$inc": {"balance": -100}})
        txn.update_one({"name": "Bob"}, {"$inc": {"balance": 100}})
        # If this fails, both updates are rolled back
        txn.insert_one({"invalid": doc})  # Raises exception
except Exception as e:
    print(f"Transaction rolled back: {e}")
```

---

## Configuration

### Database Options

```python
db = JSONlite(
    'database.json',
    indent=2,              # JSON indentation
    ensure_ascii=False,    # Preserve Unicode
    auto_index=True        # Auto-create indexes (default: True)
)
```

### Query Cache

```python
# Enable/disable cache
db.cache_enabled = True
db.cache_enabled = False

# Configure cache size
db.cache_max_size = 1000  # LRU cache entries

# Clear cache
db.clear_cache()
```

---

## Error Handling

```python
from jsonlite import JSONliteError, DocumentNotFoundError, DuplicateKeyError

try:
    db.create_index("email", unique=True)
    db.insert_one({"email": "test@example.com"})
    db.insert_one({"email": "test@example.com"})  # Raises DuplicateKeyError
except DuplicateKeyError as e:
    print(f"Duplicate key: {e}")
except DocumentNotFoundError as e:
    print(f"Document not found: {e}")
except JSONliteError as e:
    print(f"Database error: {e}")
```

---

## Best Practices

1. **Use indexes** for frequently queried fields
2. **Batch operations** with `insert_many`/`update_many` for better performance
3. **Use transactions** for multi-step atomic operations
4. **Enable query cache** for repeated queries
5. **Limit result sets** with `.limit()` to reduce memory usage
6. **Use projection** to fetch only needed fields

---

## Migration from MongoDB

See [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) for detailed MongoDB → JSONLite migration instructions.
