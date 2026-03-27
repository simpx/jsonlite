# JSONLite 开发路线图 (Roadmap)

**项目**: JSONLite - 轻量级本地 JSON 数据库  
**版本目标**: v1.0.0 (Stable Release)  
**时间周期**: 4 周 (2026-03-20 ~ 2026-04-17)  
**发布状态**: 🚀 Ready for v1.0.0 Release (2026-03-21)  
**GitHub**: https://github.com/simpx/jsonlite

---

## 📊 当前状态评估

### ✅ 已完成功能
- [x] 基本 CRUD 操作 (insert/find/update/delete)
- [x] 查询操作符：$gt, $lt, $gte, $lte, $eq, $regex, $in, $all, $ne, $exists, $not
- [x] 逻辑操作符：$or, $and, $nor
- [x] 并发支持（文件锁 fcntl）
- [x] 特殊类型序列化：datetime, decimal, binary
- [x] pymongo 兼容补丁
- [x] upsert 支持
- [x] 原子操作：find_one_and_delete, find_one_and_replace, find_one_and_update
- [x] 全文搜索
- [x] 测试套件（基础测试 + 并发测试 + 性能测试）
- [x] 链式查询 API (Cursor: sort/limit/skip/projection)
- [x] 更新操作符 ($set, $unset, $inc, $rename, $max, $min)
- [x] 数组更新操作符 ($push, $pull, $addToSet, $pop, $pullAll)
- [x] 聚合管道 (aggregate: $match, $group, $project, $sort, $skip, $limit, $count, $unwind)

### ⚠️ 待完善功能
- [x] 所有核心功能已完成 ✅
- [🔄] v1.1+ 迭代功能开发中 (2026-03-27 开始)

### 🔄 v1.1 开发进度 (2026-03-27 ~ )
**当前重点**: 地理空间查询支持

#### 已完成 (v1.1-alpha)
- [x] **地理空间查询基础** ✅ (2026-03-27)
  - Haversine 距离计算 (地球球面距离)
  - 坐标提取 (支持 [lng,lat]、GeoJSON Point、{lng,lat} 等格式)
  - 点多边形判断 (ray casting 算法)
- [x] **$near 操作符** ✅ (2026-03-27)
  - 按距离排序结果
  - $maxDistance 过滤 (最大距离)
  - $minDistance 过滤 (最小距离)
- [x] **$geoWithin 操作符** ✅ (2026-03-27)
  - $box: 矩形区域查询
  - $Center: 圆形区域查询
  - GeoJSON Polygon: 多边形区域查询
- [x] **$geoIntersects 操作符** ✅ (2026-03-27)
  - 点与多边形相交判断
- [x] **Cursor.near() 链式 API** ✅ (2026-03-27)
  - 支持 fluent 查询风格
  - 可与其他链式方法组合 (limit, skip 等)
- [x] **测试覆盖** ✅ (2026-03-27)
  - 20 个地理空间测试全部通过
  - 总测试数：249 tests passing
- [x] **多数据库/集合管理** ✅ (2026-03-27 06:00)
  - MongoClient 类 (pymongo 兼容 API)
  - Database 类 (管理多个集合)
  - Collection 类 (封装 JSONlite 实例)
  - 42 个新增测试全部通过
  - 总测试数：291 tests passing

#### v1.1 待完成
- [x] 地理空间索引 (Geohash 或 R-tree) ✅ (2026-03-27)
  - Geohash 编码/解码 ✅
  - 自动索引维护（插入/更新/删除）✅
  - $near 查询优化 ✅
  - $geoWithin 查询优化 ✅
  - 10 个新增测试全部通过 ✅
- [x] 全文索引优化 ✅ (2026-03-27)
  - 倒排索引 (Inverted Index) ✅
  - TF-IDF 评分排序 ✅
  - 分词与停用词过滤 ✅
  - 自动索引维护（插入/更新/删除）✅
  - 24 个新增测试全部通过 ✅
- [x] 多数据库/集合管理 ✅ (2026-03-27)
  - MongoClient 类 (pymongo 兼容) ✅
  - Database 类 (多集合管理) ✅
  - Collection 类 (集合操作封装) ✅
  - 42 个新增测试全部通过 ✅
- [x] 网络模式（客户端 - 服务器）✅ (2026-03-27 07:30)
  - JSONLiteServer: TCP 服务器 ✅
  - RemoteMongoClient: 客户端代理 ✅
  - JSON 协议（请求/响应）✅
  - 可选 HMAC 认证 ✅
  - 完整 CRUD/聚合/索引支持 ✅
  - 18 个新增测试全部通过 ✅
- [x] **数据压缩** ✅ (2026-03-27 08:30)
  - Gzip 压缩支持 ✅
  - 可配置压缩级别 (1-9) ✅
  - 自动检测压缩文件 ✅
  - 与所有现有功能兼容 (索引/查询/特殊类型) ✅
  - 11 个新增测试全部通过 ✅
- [x] **加密支持** ✅ (2026-03-27 11:49)
  - AES-256-GCM 加密 ✅
  - PBKDF2-SHA256 密钥派生 (10 万次迭代) ✅
  - 自动加密检测 (ENCR 魔数) ✅
  - 与压缩兼容 (先压缩后加密) ✅
  - 支持所有功能 (索引/查询/聚合/MongoClient) ✅
  - 15 个新增测试全部通过 ✅

---

## 📅 周计划

### 第 1 周：核心查询增强 (2026-03-20 ~ 2026-03-27)
**目标**: 完善查询功能，使其更接近 MongoDB API

#### 任务列表
- [x] **排序 (sort)** - 支持单字段和多字段排序
  - `sort(key, direction)` - ASC/DESC
  - 支持多级排序
- [x] **限制与跳过 (limit/skip)** - 分页支持
  - `limit(n)` - 限制返回数量
  - `skip(n)` - 跳过前 N 条
- [x] **投影 (projection)** - 字段选择
  - `projection(fields)` - 选择/排除字段
  - 支持嵌套字段投影
- [x] **链式 API** - 支持流畅查询
  - `db.find(filter).sort("age", -1).limit(10).skip(5)`
- [x] **单元测试** - 为新增功能编写测试 (26 tests passing)

#### 交付物
- [x] 查询增强功能代码 (Cursor class)
- [x] 测试覆盖率 > 80%
- [x] 更新 README 使用示例

---

### 第 2 周：更新操作符与数组支持 (2026-03-28 ~ 2026-04-03)
**目标**: 完善更新操作，支持数组操作

#### 任务列表
- [x] **字段更新操作符**
  - `$set` - 已实现，完善边缘情况
  - `$unset` - 删除字段 ✅
  - `$inc` - 自增/自减 ✅
  - `$rename` - 重命名字段 ✅
  - `$max` / `$min` - 最大值/最小值更新 ✅
- [x] **数组操作符**
  - `$push` - 添加元素到数组 ✅
  - `$pull` - 从数组移除元素 (支持操作符条件) ✅
  - `$addToSet` - 添加唯一元素 ✅
  - `$pop` - 移除首/尾元素 ✅
  - `$pullAll` - 批量移除 ✅
- [x] **嵌套字段更新** - 支持点号语法 `address.city` ✅
- [x] **单元测试** - 覆盖所有更新场景 (52 tests passing) ✅

#### 交付物
- [x] 完整更新操作符实现 (field operators)
- [x] 数组操作测试套件 (27 个数组操作测试)
- [x] 更新操作文档 (docs: Add update operators documentation)

---

### 第 3 周：聚合与索引 (2026-04-04 ~ 2026-04-10)
**目标**: 实现高级查询功能

#### 任务列表
- [x] **聚合管道 (aggregate)** - 基础阶段 ✅ (2026-03-20)
  - `$match` - 过滤 ✅
  - `$group` - 分组聚合 (支持 $sum, $avg, $min, $max, $count, $first, $last, $push) ✅
  - `$project` - 投影 (支持 include/exclude 模式、表达式) ✅
  - `$sort` - 排序 ✅
  - `$limit` / `$skip` - 分页 ✅
  - `$count` - 计数 ✅
  - `$unwind` - 数组展开 ✅
- [x] **索引支持** - 基础索引 ✅ (2026-03-21)
  - 单字段索引 ✅
  - 复合索引 ✅
  - 唯一索引 ✅
  - 稀疏索引 ✅
  - 索引加速查询 ✅
  - 索引维护（插入/更新/删除时）✅
- [x] **基准测试** - 与 SQLite 对比 ✅ (2026-03-21)
  - 创建 benchmark.py 工具 ✅
  - 完成 6 项基准测试 ✅
  - 生成性能报告 (docs/BENCHMARK_REPORT.md) ✅
- [x] **性能优化** 🔥 已完成 (2026-03-21)
  - [x] 批量操作优化 (减少文件 I/O) ✅ insert_many 优化：262x 提升
  - [x] 查询结果缓存 (LRU cache) ✅ (2026-03-21) - 202 tests passing
    - Fixed: Handle callable keys in QueryCache hash function (2026-03-21)
  - [x] 可选 orjson/ujson 加速序列化 ✅ (2026-03-21)

#### 交付物
- [x] 聚合管道实现 (AggregationCursor class, 20 tests passing) ✅
- [x] 索引系统 (IndexManager class, 自动维护) ✅
- [x] 基准测试工具 (tools/benchmark.py) ✅
- [x] 性能基准报告 (docs/BENCHMARK_REPORT.md) ✅
- [x] 查询缓存系统 (QueryCache class, LRU eviction, 18 tests passing) ✅
- [x] 可选 orjson/ujson 序列化优化 ✅ (2026-03-21)
  - 安装 orjson 3.11.7
  - 实现 _fast_dumps/_fast_loads 包装函数
  - 优化缓存哈希计算性能
  - 202 tests passing

---

### 第 4 周：完善与发布准备 (2026-04-11 ~ 2026-04-17)
**目标**: 稳定版本发布  
**状态**: 🚀 Ready for Release (2026-03-21)

#### 任务列表
- [x] **事务支持** - 基础事务 ✅ (2026-03-21)
  - 多操作原子性 ✅
  - 回滚支持 ✅
  - 19 个事务测试全部通过 ✅
- [x] **文档完善** ✅ (2026-03-21)
  - API 参考文档 (docs/API_REFERENCE.md) ✅
  - 使用教程 (docs/TUTORIAL.md) ✅
  - 迁移指南 (docs/MIGRATION_GUIDE.md) ✅
  - 事务文档 (docs/TRANSACTIONS.md) ✅
  - 性能基准报告 (docs/BENCHMARK_REPORT.md) ✅
- [x] **PyPI 发布准备** ✅ (2026-03-21)
  - setup.py 配置完成 ✅
  - CHANGELOG.md 已更新 ✅
  - PYPI_RELEASE.md 发布清单 ✅
- [x] **CI/CD** ✅ (2026-03-21)
  - GitHub Actions 测试流水线 (.github/workflows/ci-cd.yml) ✅
  - 自动发布到 PyPI 配置 ✅
- [x] **测试通过** ✅ (2026-03-21)
  - 229 tests passing ✅
  - 测试覆盖率 > 85% ✅

#### 交付物
- [x] v1.0.0 稳定版 (待打标签发布)
- [x] 完整文档
- [x] git push origin main ✅ (2026-03-24)
- [x] v1.0.0 tag 已创建 ✅
- [x] PyPI 发布 ✅ (2026-03-26) - jsonlite 1.0.0 已上线
- [x] GitHub Release ✅ (已创建并发布)

#### 待执行操作
✅ **v1.0.0 发布已完成** (2026-03-26)
- PyPI: https://pypi.org/project/jsonlite/1.0.0/
- GitHub Release: https://github.com/simpx/jsonlite/releases/tag/v1.0.0
- 安装：`pip install jsonlite`

---

## 🎉 v1.0.0 发布总结

**发布日期**: 2026-03-26  
**PyPI 包名**: jsonlite  
**版本**: 1.0.0  
**测试**: 309+ tests passing ✅ (v1.1: +80 tests)  
**文档**: 完整 API 文档 + 使用教程 + 迁移指南 ✅  

**核心功能**:
- 完整 CRUD + 查询操作符 (pymongo 兼容)
- 更新操作符 ($set, $unset, $inc, $rename, $max, $min)
- 数组操作符 ($push, $pull, $addToSet, $pop, $pullAll)
- 聚合管道 ($match, $group, $project, $sort, $skip, $limit, $count, $unwind)
- 索引系统 (单字段/复合/唯一/稀疏索引，自动维护)
- 事务支持 (原子多操作 + 回滚)
- 查询缓存 (LRU eviction)
- 并发支持 (fcntl 文件锁)
- 可选 orjson 加速

---

## 📋 v1.1 规划建议

**候选功能** (按优先级排序):
1. 地理空间查询 ($near, $geoWithin, $geoIntersects)
2. 全文索引优化
3. 多数据库/集合管理
4. 网络模式 (客户端 - 服务器架构)
5. 数据压缩
6. 加密支持

---

## 🎯 成功指标

| 指标 | 目标 |
|------|------|
| 测试覆盖率 | > 85% |
| API 兼容性 | 90% pymongo API |
| 性能 | 10k 记录查询 < 100ms |
| 并发 | 支持 10+ 进程同时读写 |
| 文档 | 完整 API 文档 + 使用示例 |

---

## 📦 技术栈

- **语言**: Python 3.6+
- **依赖**: 零依赖（核心），可选 pymongo
- **测试**: pytest
- **打包**: setuptools, setuptools_scm
- **CI**: GitHub Actions

---

## ⚠️ 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 索引实现复杂度高 | 高 | 第 3 周优先实现基础索引，高级索引延后 |
| 聚合管道工作量大 | 中 | 先实现核心阶段，其他阶段作为后续迭代 |
| 并发边界情况 | 中 | 增加并发测试覆盖，使用文件锁确保原子性 |
| 时间不足 | 中 | 优先保证核心功能，高级功能可延后到 v1.1 |

---

## 🔄 后续迭代 (v1.1+)

- [x] 地理空间查询 ✅
- [x] 全文索引 ✅
- [x] 多数据库支持 ✅
- [x] 网络模式（客户端 - 服务器）✅
- [x] 数据压缩 ✅
- [x] 加密支持 ✅

---

**创建时间**: 2026-03-20  
**最后更新**: 2026-03-27 (v1.1.1 发布完成)

---

## 🎉 v1.1.1 发布完成 (2026-03-27)

**发布日期**: 2026-03-27  
**PyPI 包名**: jsonlite  
**版本**: 1.1.1  
**测试**: 369 tests passing ✅  
**GitHub Release**: https://github.com/simpx/jsonlite/releases/tag/v1.1.1  
**PyPI**: https://pypi.org/project/jsonlite/1.1.1/  
**安装**: `pip install --upgrade jsonlite`

**v1.1 系列核心功能**:
- 地理空间查询 ($near, $geoWithin, $geoIntersects) + Geohash 索引 ✅
- 全文搜索索引 (倒排索引 + TF-IDF 评分) ✅
- 多数据库/集合管理 (MongoClient/Database/Collection) ✅
- 网络模式 (JSONLiteServer + RemoteMongoClient) ✅
- 数据压缩 (Gzip, 压缩级别 1-9) ✅
- 数据加密 (AES-256-GCM + PBKDF2-SHA256) ✅

---

## 🚀 v1.2 开发中 (2026-03-28 ~ )

**当前重点**: 聚合管道增强 - 递归连接与高级聚合

#### 已完成 (v1.2-alpha)
- [x] **$lookup 聚合阶段** ✅ (2026-03-28)
  - 基础语法：from, localField, foreignField, as ✅
  - 管道语法：let 变量 + pipeline 阶段 ✅
  - 跨集合连接（同数据库内）✅
  - MongoClient/Database 集成支持 ✅
  - 独立 JSONlite 支持（兄弟 .json 文件连接）✅
  - 与所有聚合阶段兼容 ($match, $unwind, $project 等) ✅
  - 10 个综合测试全部通过 ✅
- [x] **$graphLookup 递归连接** ✅ (2026-03-28)
  - 递归图遍历 ✅
  - startWith, connectFromField, connectToField 语义 ✅
  - maxDepth 深度限制 ✅
  - depthField 深度字段标记 ✅
  - restrictSearchWithMatch 搜索过滤 ✅
  - 循环检测 (避免无限递归) ✅
  - 支持数组连接字段 ✅
  - MongoClient/Database 集成支持 ✅
  - 11 个综合测试全部通过 ✅
  - 总测试数：390 tests passing ✅

#### v1.2 候选功能
- [ ] $facet (多面聚合)
- [ ] $bucket / $bucketAuto (分桶聚合)
- [ ] 更多聚合表达式操作符
- [ ] 查询计划器/优化器
- [ ] 虚拟字段/计算字段

---

**创建时间**: 2026-03-20  
**最后更新**: 2026-03-28 (v1.2.0-alpha $graphLookup 完成)
