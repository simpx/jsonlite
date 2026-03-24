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
- [ ] v1.1+ 迭代功能 (地理空间查询、全文索引、网络模式等)

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
- [ ] PyPI 发布 (待执行：git push + git tag)
- [ ] GitHub Release (待执行)

#### 待执行操作
```bash
# 1. 推送本地提交到 GitHub
git push origin main

# 2. 创建并推送 v1.0.0 标签
git tag -a v1.0.0 -m "Release v1.0.0 - Stable release with full MongoDB compatibility"
git push origin v1.0.0

# 3. CI/CD 将自动：
#    - 运行所有测试 (Python 3.6-3.12)
#    - 构建 package (sdist + wheel)
#    - 上传到 PyPI
```

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

- [ ] 地理空间查询
- [ ] 全文索引
- [ ] 多数据库支持
- [ ] 网络模式（客户端 - 服务器）
- [ ] 数据压缩
- [ ] 加密支持

---

**创建时间**: 2026-03-20  
**最后更新**: 2026-03-21
