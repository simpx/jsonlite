# JSONLite

![Build Status](https://img.shields.io/github/actions/workflow/status/simpx/jsonlite/python-package.yml)
![PyPI](https://img.shields.io/pypi/v/jsonlite)
![License](https://img.shields.io/github/license/simpx/jsonlite)
![Issues](https://img.shields.io/github/issues/simpx/jsonlite)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

JSONLite is a lightweight, local JSON database for simple data storage.
- Like SQLite, it's a local database.
- Its API is 100% modeled after MongoDB, making it easy to migrate between MongoDB and JSONLite.

## Features

- **Zero dependency** - Pure Python, no external libraries required
- **MongoDB-compatible API** - 100% pymongo API compatibility
- **Local storage** - Store JSON data in simple files
- **Concurrent access** - Multiple processes can read/write safely with file locking
- **Chainable queries** - Fluent API with sort, limit, skip, projection
- **Aggregation pipeline** - $match, $group, $project, $sort, $unwind, and more
- **Index support** - Single-field, compound, unique, and sparse indexes
- **Transactions** - Atomic multi-operation transactions with rollback
- **Query caching** - LRU cache for improved performance
- **Special types** - Full support for datetime, decimal, and binary data

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Usage](#usage)
  - [Data Layout](#data-layout-in-json-file)
  - [Direct Usage](#direct-usage)
  - [Patching pymongo](#patching-pymongo-to-use-jsonlite)
- [Examples](#examples)
- [Performance](#performance)
- [License](#license)

## Installation

```sh
pip install jsonlite
```

### Optional Performance Boost

For better JSON serialization performance:

```sh
pip install jsonlite[performance]  # Installs orjson
```

## Documentation

- 📖 **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation
- 🔄 **[Migration Guide](docs/MIGRATION_GUIDE.md)** - MongoDB → JSONLite migration
- 📊 **[Benchmark Report](docs/BENCHMARK_REPORT.md)** - Performance comparisons
- 📘 **[Transactions](docs/TRANSACTIONS.md)** - Transaction usage guide
- 🗺️ **[Roadmap](ROADMAP.md)** - Development roadmap and status

## Quick Start

```python
from jsonlite import JSONlite

# Initialize database
db = JSONlite('mydata.json')

# Insert documents
db.insert_one({"name": "Alice", "age": 30})
db.insert_many([
    {"name": "Bob", "age": 25},
    {"name": "Charlie", "age": 35}
])

# Query with chainable API
results = (db
    .find({"age": {"$gte": 30}})
    .sort("age", -1)
    .limit(10)
    .toArray())

# Update documents
db.update_one({"name": "Alice"}, {"$set": {"age": 31}})

# Use indexes for faster queries
db.create_index("name")
db.create_index([("last_name", 1), ("first_name", 1)])

# Transactions for atomic operations
from jsonlite import Transaction
with Transaction(db) as txn:
    txn.update_one({"name": "Alice"}, {"$inc": {"balance": -100}})
    txn.update_one({"name": "Bob"}, {"$inc": {"balance": 100}})
```

## Examples

Check the `examples/` directory for comprehensive usage examples:

- **basic_usage.py** - CRUD operations, cursor API, indexes, transactions
- **advanced_features.py** - Aggregation pipelines, query cache, full-text search

Run examples:
```bash
python examples/basic_usage.py
python examples/advanced_features.py
```

## Data Layout in json file

```json
{
    "data": [
        {   "_id": 1,
            "name": "Alice",
            "age": 30
        },
        {   "_id": 2,
            "name": "Bob",
            "age": 25
        },
        {   "_id": 3,
            "name": "Charlie",
            "age": 20
        }
    ]
}
```

## Direct Usage

You can use JSONlite directly to perform CRUD operations.


```python
>>> from jsonlite import JSONlite

>>> # Initialize the database
>>> db = JSONlite('mydatabase.json')

>>> # Inserting one document
>>> result = db.insert_one({"name": "John Doe", "age": 30})
>>> result.inserted_id
1

>>> # Inserting multiple documents
>>> result = db.insert_many([
...     {"name": "Jane Doe", "age": 25},
...     {"name": "Alice", "age": 28}
... ])
>>> result.inserted_ids
[2, 3]

>>> # Finding one document
>>> document = db.find_one({"name": "John Doe"})
>>> document
{'_id': 1, 'name': 'John Doe', 'age': 30}

>>> # Finding multiple documents
>>> documents = db.find({"age": {"$gte": 25}})
>>> documents
[
    {'_id': 1, 'name': 'John Doe', 'age': 30},
    {'_id': 2, 'name': 'Jane Doe', 'age': 25},
    {'_id': 3, 'name': 'Alice', 'age': 28}
]

>>> # Updating one document
>>> result = db.update_one({"name": "John Doe"}, {"$set": {"age": 31}})
>>> result.matched_count, result.modified_count
(1, 1)

>>> # Updating multiple documents
>>> result = db.update_many({"age": {"$gte": 25}}, {"$set": {"status": "active"}})
>>> result.matched_count, result.modified_count
(3, 3)

>>> # Deleting one document
>>> result = db.delete_one({"name": "John Doe"})
>>> result.deleted_count
1

>>> # Deleting multiple documents
>>> result = db.delete_many({"age": {"$lt": 30}})
>>> result.deleted_count
2

>>> # Chainable queries with Cursor API
>>> # Sort by age descending, skip 1, limit to 2 results
>>> results = db.find({"age": {"$gte": 20}}).sort("age", -1).skip(1).limit(2).all()
>>> results
[
    {'_id': 3, 'name': 'Alice', 'age': 28},
    {'_id': 2, 'name': 'Jane Doe', 'age': 25}
]

>>> # Projection - select only specific fields
>>> results = db.find({}).projection({"name": 1, "age": 1, "_id": 0}).all()
>>> results
[
    {'name': 'Alice', 'age': 28},
    {'name': 'Jane Doe', 'age': 25}
]

>>> # Multi-field sort
>>> results = db.find({}).sort([("age", -1), ("name", 1)]).all()

>>> # Atomic find_one_and_update
>>> result = db.find_one_and_update(
...     {"name": "Alice"},
...     {"$set": {"age": 29}},
...     return_document="after"  # or "before"
... )
>>> result
{'_id': 3, 'name': 'Alice', 'age': 29}
```

### Update Operators

JSONLite supports MongoDB-style update operators for fine-grained document modifications.

#### Field Update Operators

```python
>>> # $set - Set field value
>>> db.update_one({"name": "Alice"}, {"$set": {"age": 30, "status": "active"}})

>>> # $unset - Remove field
>>> db.update_one({"name": "Alice"}, {"$unset": {"status": ""}})

>>> # $inc - Increment/decrement numeric field
>>> db.update_one({"name": "Alice"}, {"$inc": {"age": 1, "score": -5}})

>>> # $rename - Rename field
>>> db.update_one({"name": "Alice"}, {"$rename": {"age": "years_old"}})

>>> # $max - Update only if new value is greater
>>> db.update_one({"name": "Alice"}, {"$max": {"score": 100}})

>>> # $min - Update only if new value is smaller
>>> db.update_one({"name": "Alice"}, {"$min": {"score": 0}})
```

#### Array Update Operators

```python
>>> # $push - Add element to array
>>> db.update_one({"name": "Alice"}, {"$push": {"tags": "python"}})

>>> # $push with $each - Add multiple elements
>>> db.update_one({"name": "Alice"}, {"$push": {"tags": {"$each": ["java", "go"]}}})

>>> # $pull - Remove elements matching condition
>>> db.update_one({"name": "Alice"}, {"$pull": {"tags": "java"}})

>>> # $pull with operator - Remove by condition
>>> db.update_one({"name": "Alice"}, {"$pull": {"scores": {"$gte": 60}}})

>>> # $addToSet - Add unique element (no duplicates)
>>> db.update_one({"name": "Alice"}, {"$addToSet": {"tags": "python"}})  # Won't duplicate

>>> # $pop - Remove first/last element
>>> db.update_one({"name": "Alice"}, {"$pop": {"tags": 1}})   # Remove last
>>> db.update_one({"name": "Alice"}, {"$pop": {"tags": -1}})  # Remove first

>>> # $pullAll - Remove multiple specific values
>>> db.update_one({"name": "Alice"}, {"$pullAll": {"tags": ["java", "go"]}})
```

#### Nested Field Updates

Use dot notation to update nested fields:

```python
>>> # Insert document with nested structure
>>> db.insert_one({"name": "Alice", "address": {"city": "Beijing", "zip": "100000"}})

>>> # Update nested field
>>> db.update_one({"name": "Alice"}, {"$set": {"address.city": "Shanghai"}})

>>> # Add new nested field
>>> db.update_one({"name": "Alice"}, {"$set": {"address.country": "China"}})

>>> # Unset nested field
>>> db.update_one({"name": "Alice"}, {"$unset": {"address.zip": ""}})
```

## Patching pymongo to use JSONlite
Alternatively, you can patch pymongo to use JSONlite and interact with JSON files as if you were using MongoDB. This allows you to use the familiar pymongo API with JSON data.

```python
>>> from jsonlite import pymongo_patch

>>> pymongo_patch()

>>> from pymongo import MongoClient

>>> client = MongoClient('jsonlite://database')
>>> db = client.test_database
>>> collection = db.test_collection
>>> insert_result = collection.insert_one({"name": "Alice", "age": 30})
>>> # Just like using pymongo
>>> collection.drop()
```

## Performance

JSONLite is optimized for local development and small-to-medium datasets:

| Operation | Performance |
|-----------|-------------|
| Single document insert | < 1ms |
| Batch insert (1000 docs) | ~50ms |
| Indexed query | < 5ms |
| Full collection scan | ~10ms per 1000 docs |
| Aggregation pipeline | ~20ms per stage |

See [docs/BENCHMARK_REPORT.md](docs/BENCHMARK_REPORT.md) for detailed performance analysis.

### Optimization Tips

1. **Use indexes** for frequently queried fields
2. **Batch operations** with `insert_many`/`update_many`
3. **Enable query cache** for repeated queries
4. **Use projection** to fetch only needed fields
5. **Install orjson** for faster JSON serialization

```python
# Enable query cache
db.cache_enabled = True
db.cache_max_size = 1000

# Create indexes for common queries
db.create_index("email")
db.create_index([("category", 1), ("created_at", -1)])
```

## Contributing

Contributions are welcome! Please read our [Roadmap](ROADMAP.md) to see what we're working on.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

## Support

- **Issues:** https://github.com/simpx/jsonlite/issues
- **Discussions:** https://github.com/simpx/jsonlite/discussions
- **Email:** simpxx@gmail.com

# License

JSONLite is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.