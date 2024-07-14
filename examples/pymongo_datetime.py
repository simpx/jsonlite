from jsonlite import pymongo_patch
pymongo_patch()

from pymongo import MongoClient
from datetime import datetime

client = MongoClient('jsonlite://test_database/')

db = client['example_db']
collection = db['example_collection']

documents = [
    {"name": "doc1", "date": datetime(2023, 10, 1, 12, 0)},
    {"name": "doc2", "date": datetime(2023, 10, 5, 12, 0)},
    {"name": "doc3", "date": datetime(2023, 10, 10, 12, 0)},
    {"name": "doc4", "date": datetime(2023, 10, 15, 12, 0)},
]

# 清空集合并插入新文档
collection.delete_many({})
collection.insert_many(documents)

# 定义时间范围
start_date = datetime(2023, 10, 3, 0, 0)
end_date = datetime(2023, 10, 12, 0, 0)

# 查询时间在 start_date 和 end_date 之间的文档
query = {
    "date": {
        "$gte": start_date,
        "$lt": end_date
    }
}

# 执行查询
results = collection.find(query)

# 打印结果
for document in results:
    print(document)
