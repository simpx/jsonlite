# JSONLite

JSONLite is a lightweight, local JSON database for simple data storage.

- Like SQLite, it's a local database
- It's API is 100% modeled after MongoDB, making it easy to migrate between MongoDB and JSONLite

## Installation

```sh
pip install jsonlite
```

## Data Layout

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

## Usage

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