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

- Zero dependency
- Store JSON data locally
- MongoDB-like API, Compatible with pymongo
- Allows multiple processes to read/write concurrently
- Chainable query API (sort, limit, skip, projection)

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
  - [Data Layout](#data-layout-in-json-file)
  - [Direct Usage](#direct-usage)
  - [Patching pymongo](#patching-pymongo-to-use-jsonlite)
- [License](#license)

## Installation

```sh
pip install jsonlite
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

# License

JSONLite is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.