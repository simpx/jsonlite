# Changelog

All notable changes to JSONLite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-21

### Added
- Transaction support with atomic multi-operation rollback
- Optional orjson acceleration for JSON serialization
- Query result caching with LRU eviction
- Index support (single-field, compound, unique, sparse) with automatic maintenance
- Aggregation pipeline support ($match, $group, $project, $sort, $skip, $limit, $count, $unwind)
- Array update operators ($push, $pull, $addToSet, $pop, $pullAll)
- Field update operators ($unset, $inc, $rename, $max, $min)
- Chainable Cursor API with sort, limit, skip, projection
- Full-text search support
- Upsert support
- Atomic operations: find_one_and_delete, find_one_and_replace, find_one_and_update
- Special type serialization: datetime, decimal, binary
- pymongo compatibility patch

### Changed
- Optimized batch insert performance (262x improvement)
- Improved query cache hash function to handle callable keys

### Fixed
- Document replacement behavior when no operators present

---

## [0.1.0] - 2026-03-20

### Added
- Initial release
- Basic CRUD operations (insert/find/update/delete)
- Query operators: $gt, $lt, $gte, $lte, $eq, $regex, $in, $all, $ne, $exists, $not
- Logical operators: $or, $and, $nor
- Concurrent access support (fcntl file locking)
- Zero dependency core

---

## Version History Summary

| Version | Date | Key Features |
|---------|------|--------------|
| Unreleased | 2026-03-21 | Transactions, Query Cache, Indexes, Aggregation |
| 0.1.0 | 2026-03-20 | Initial Release, Basic CRUD, Query Operators |

---

## Upcoming (v1.0.0)

- Complete API reference documentation
- Usage tutorials
- MongoDB → JSONLite migration guide
- Expanded example code library
- PyPI release
- GitHub Actions CI/CD pipeline
- Test coverage > 85%
