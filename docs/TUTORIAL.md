# JSONLite 使用教程 (Tutorial)

**JSONLite** 是一个轻量级本地 JSON 数据库，提供 MongoDB 兼容的 API。本教程将带你从零开始掌握 JSONLite 的核心功能。

---

## 📦 安装

```bash
# 基础安装（零依赖）
pip install jsonlite

# 可选：安装性能优化包（使用 orjson 加速序列化）
pip install jsonlite[performance]

# 开发安装
pip install jsonlite[dev]
```

---

## 🚀 快速开始

### 1. 创建数据库和集合

```python
from jsonlite import Database

# 创建数据库（自动在指定路径创建 .jsonlite 文件）
db = Database('./mydata.jsonlite')

# 获取或创建集合
users = db.get_collection('users')
```

### 2. 插入文档

```python
# 插入单个文档
user_id = users.insert_one({
    'name': 'Alice',
    'age': 30,
    'email': 'alice@example.com',
    'skills': ['Python', 'JavaScript'],
    'active': True
})

# 批量插入
users.insert_many([
    {'name': 'Bob', 'age': 25, 'email': 'bob@example.com'},
    {'name': 'Charlie', 'age': 35, 'email': 'charlie@example.com'},
    {'name': 'Diana', 'age': 28, 'email': 'diana@example.com'}
])
```

### 3. 查询文档

```python
# 查找所有文档
all_users = users.find()

# 条件查询
adults = users.find({'age': {'$gte': 30}})

# 逻辑查询
young_or_senior = users.find({
    '$or': [
        {'age': {'$lt': 25}},
        {'age': {'$gt': 35}}
    ]
})

# 查找单个文档
alice = users.find_one({'name': 'Alice'})
```

### 4. 更新文档

```python
# 更新单个文档
users.update_one(
    {'name': 'Alice'},
    {'$set': {'age': 31, 'active': True}}
)

# 自增字段
users.update_one(
    {'name': 'Bob'},
    {'$inc': {'age': 1}}
)

# 数组操作
users.update_one(
    {'name': 'Alice'},
    {'$push': {'skills': 'MongoDB'}}
)

# 批量更新
users.update_many(
    {'active': True},
    {'$set': {'status': 'verified'}}
)
```

### 5. 删除文档

```python
# 删除单个文档
users.delete_one({'name': 'Charlie'})

# 批量删除
users.delete_many({'active': False})

# 清空集合
users.delete_many({})
```

---

## 🔍 高级查询

### 链式查询 API

```python
# 流畅的链式查询
results = (users
    .find({'age': {'$gte': 25}})
    .sort('age', -1)  # 降序
    .skip(0)
    .limit(10)
    .projection(['name', 'age', 'email'])
)

for user in results:
    print(user)
```

### 查询操作符

```python
# 比较操作符
{'age': {'$gt': 18}}           # 大于
{'age': {'$gte': 18}}          # 大于等于
{'age': {'$lt': 65}}           # 小于
{'age': {'$lte': 65}}          # 小于等于
{'age': {'$ne': 30}}           # 不等于
{'age': {'$eq': 30}}           # 等于

# 逻辑操作符
{'$and': [{'age': {'$gt': 18}}, {'active': True}]}
{'$or': [{'age': {'$lt': 18}}, {'age': {'$gt': 65}}]}
{'$nor': [{'status': 'banned'}]}

# 数组操作符
{'skills': {'$in': ['Python', 'Java']}}     # 包含任一
{'skills': {'$all': ['Python', 'JS']}}      # 包含所有
{'skills': {'$size': 3}}                    # 数组长度为 3

# 正则表达式
{'email': {'$regex': r'^[a-z]+@example\.com$'}}

# 字段存在性
{'middle_name': {'$exists': False}}
```

### 投影（字段选择）

```python
# 只选择特定字段
users.find({}, projection=['name', 'email'])

# 排除特定字段
users.find({}, projection={'password': 0, 'secret': 0})

# 嵌套字段投影
users.find({}, projection=['name', 'address.city', 'address.zip'])
```

---

## 📊 聚合管道

```python
# 统计每个年龄段的用户数量
pipeline = [
    {'$match': {'active': True}},
    {'$group': {
        '_id': '$age',
        'count': {'$sum': 1},
        'avg_score': {'$avg': '$score'}
    }},
    {'$sort': {'count': -1}},
    {'$limit': 10}
]

results = users.aggregate(pipeline)

# 常用聚合阶段
# $match - 过滤文档
# $group - 分组聚合
# $project - 投影/计算新字段
# $sort - 排序
# $skip / $limit - 分页
# $count - 计数
# $unwind - 展开数组
```

### 聚合表达式

```python
# 分组时使用的累加器
{'$sum': '$field'}      # 求和
{'$avg': '$field'}      # 平均值
{'$min': '$field'}      # 最小值
{'$max': '$field'}      # 最大值
{'$count': '$field'}    # 计数
{'$first': '$field'}    # 第一个值
{'$last': '$field'}     # 最后一个值
{'$push': '$field'}     # 收集到数组
```

---

## 🔧 更新操作符

### 字段更新

```python
# $set - 设置字段值
{'$set': {'name': 'New Name', 'status': 'active'}}

# $unset - 删除字段
{'$unset': {'temp_field': '', 'old_data': ''}}

# $inc - 自增/自减
{'$inc': {'views': 1, 'counter': -1}}

# $rename - 重命名字段
{'$rename': {'old_name': 'new_name'}}

# $max / $min - 最大值/最小值更新
{'$max': {'high_score': 100}}  # 仅当 100 > 当前值时更新
{'$min': {'low_score': 0}}     # 仅当 0 < 当前值时更新
```

### 数组更新

```python
# $push - 添加元素
{'$push': {'tags': 'new_tag'}}
{'$push': {'scores': {'$each': [90, 85, 88]}}}  # 批量添加

# $pull - 移除匹配元素
{'$pull': {'tags': 'old_tag'}}
{'$pull': {'scores': {'$gte': 60}}}  # 移除>=60 的分数

# $addToSet - 添加唯一元素
{'$addToSet': {'tags': 'python'}}  # 重复则不添加

# $pop - 移除首/尾元素
{'$pop': {'queue': 1}}   # 移除最后一个
{'$pop': {'queue': -1}}  # 移除第一个

# $pullAll - 批量移除
{'$pullAll': {'tags': ['deprecated', 'obsolete']}}
```

---

## 🔐 事务支持

```python
# 使用事务确保多操作原子性
with db.transaction() as txn:
    users_tx = txn.get_collection('users')
    orders_tx = txn.get_collection('orders')
    
    # 创建用户
    user_id = users_tx.insert_one({'name': 'Alice', 'balance': 1000})
    
    # 创建订单
    orders_tx.insert_one({
        'user_id': user_id,
        'amount': 100,
        'status': 'pending'
    })
    
    # 更新余额
    users_tx.update_one(
        {'_id': user_id},
        {'$inc': {'balance': -100}}
    )
    
    # 如果任何操作失败，整个事务回滚
    # 如果所有操作成功，事务提交

# 事务外查询可见提交后的数据
```

---

## ⚡ 性能优化

### 1. 使用索引

```python
# 创建单字段索引
users.create_index('email')

# 创建复合索引
users.create_index([('last_name', 1), ('first_name', 1)])

# 创建唯一索引
users.create_index('email', unique=True)

# 创建稀疏索引（仅索引包含该字段的文档）
users.create_index('optional_field', sparse=True)

# 查看索引
indexes = users.list_indexes()

# 删除索引
users.drop_index('email_1')
```

### 2. 批量操作

```python
# 批量插入（比循环插入快 262 倍）
users.insert_many(large_dataset)

# 批量更新
users.update_many({'status': 'pending'}, {'$set': {'status': 'processed'}})
```

### 3. 查询缓存

```python
# 查询结果自动缓存（LRU 策略）
# 缓存大小默认 1000 条记录

# 手动清除缓存
users.clear_cache()

# 配置缓存大小
db = Database('./data.jsonlite', cache_size=2000)
```

### 4. 使用 orjson 加速

```bash
pip install orjson
```

安装后 JSONLite 自动使用 orjson 进行序列化，性能提升显著。

---

## 📝 最佳实践

### 1. 连接管理

```python
# 推荐：使用上下文管理器
with Database('./data.jsonlite') as db:
    users = db.get_collection('users')
    # 自动清理资源

# 或：手动关闭
db = Database('./data.jsonlite')
# ... 使用 ...
db.close()
```

### 2. 错误处理

```python
from jsonlite import DuplicateKeyError, NotFoundError

try:
    users.insert_one({'_id': 'unique_id', 'name': 'Test'})
except DuplicateKeyError:
    print('文档已存在')

try:
    user = users.find_one({'_id': 'nonexistent'})
except NotFoundError:
    print('文档未找到')
```

### 3. 数据验证

```python
# 在应用层进行验证
from datetime import datetime

def validate_user(data):
    required = ['name', 'email']
    for field in required:
        if field not in data:
            raise ValueError(f'Missing required field: {field}')
    
    if not isinstance(data['name'], str):
        raise ValueError('Name must be a string')
    
    data['created_at'] = datetime.utcnow()
    return data

# 使用验证
validated = validate_user({'name': 'Alice', 'email': 'alice@example.com'})
users.insert_one(validated)
```

### 4. 分页查询

```python
def get_users_page(page_num, page_size=20):
    skip = (page_num - 1) * page_size
    return (users
        .find()
        .sort('created_at', -1)
        .skip(skip)
        .limit(page_size)
    )
```

---

## 🔄 从 MongoDB 迁移

```python
# JSONLite 设计为 MongoDB 兼容
# 大多数 pymongo 代码只需修改导入语句

# MongoDB (pymongo)
from pymongo import MongoClient
client = MongoClient()
db = client.mydb
collection = db.users

# JSONLite
from jsonlite import Database
db = Database('./mydb.jsonlite')
collection = db.get_collection('users')

# 查询语法完全相同
collection.find({'age': {'$gte': 18}})
collection.update_one({'_id': id}, {'$set': {'status': 'active'}})
```

详细迁移指南请参考：[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

---

## 📚 更多资源

- [API 参考文档](API_REFERENCE.md) - 完整的 API 文档
- [基准测试报告](BENCHMARK_REPORT.md) - 性能对比数据
- [事务使用指南](TRANSACTIONS.md) - 事务详细说明
- [示例代码](../examples/) - 完整示例程序
- [GitHub 仓库](https://github.com/simpx/jsonlite) - 源码和问题反馈

---

## ❓ 常见问题

**Q: JSONLite 适合什么场景？**
A: 适合本地开发、小型项目、嵌入式应用、测试环境、原型开发。不适合高并发、分布式、大数据量场景。

**Q: 数据如何存储？**
A: 数据以 JSON 格式存储在单个文件中，使用文件锁确保并发安全。

**Q: 支持多大的数据量？**
A: 建议用于 10 万条记录以下的数据集。更大数据量建议使用 SQLite 或专业数据库。

**Q: 支持并发访问吗？**
A: 支持。使用 fcntl 文件锁确保多进程并发安全。

**Q: 如何备份数据？**
A: 直接复制 .jsonlite 文件即可。建议在应用关闭后或事务外进行备份。

---

**版本**: v1.0.0  
**最后更新**: 2026-03-21
