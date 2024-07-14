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