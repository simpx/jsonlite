# pymongo_demo.py
from jsonlite import pymongo_patch
pymongo_patch()

from pymongo import MongoClient

# 连接到本地 JSONlite 实例
client = MongoClient('jsonlite://database')

# 创建/选择数据库
db = client.test_database

# 创建/选择集合
collection = db.test_collection

# 插入单个文档
insert_result = collection.insert_one({"name": "Alice", "age": 30})
print(f"Inserted document id: {insert_result.inserted_id}")

# 插入多个文档
insert_many_result = collection.insert_many([
    {"name": "Bob", "age": 25},
    {"name": "Charlie", "age": 35},
    {"name": "David", "age": 40}
])
print(f"Inserted document ids: {insert_many_result.inserted_ids}")

# 查询单个文档
document = collection.find_one({"name": "Alice"})
print(f"Found one document: {document}")

# 查询多个文档
documents = collection.find({"age": {"$gte": 30}})
print("Found documents:")
for doc in documents:
    print(doc)

# 更新单个文档
update_result = collection.update_one(
    {"name": "Alice"},
    {"$set": {"age": 31}}
)
print(f"Matched count: {update_result.matched_count}, Modified count: {update_result.modified_count}")

# 更新多个文档
update_many_result = collection.update_many(
    {"age": {"$gte": 30}},
    {"$set": {"status": "adult"}}
)
print(f"Matched count: {update_many_result.matched_count}, Modified count: {update_many_result.modified_count}")

# 删除单个文档
delete_result = collection.delete_one({"name": "Alice"})
print(f"Deleted count: {delete_result.deleted_count}")

# 删除多个文档
delete_many_result = collection.delete_many({"age": {"$gte": 40}})
print(f"Deleted count: {delete_many_result.deleted_count}")

# 清除集合
collection.drop()