# Changelog

All notable changes to JSONLite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-03-27

### Changed
- Updated documentation with v1.1.0 release notes in CHANGELOG
- Finalized v1.1 release polish

### Notes
- Version bump from 1.1.0 to 1.1.1 to include documentation updates in released package

---

## [1.1.0] - 2026-03-27

### Added
- **Geographic Spatial Queries** - Full MongoDB-compatible geospatial support
  - `$near` operator with `$maxDistance` and `$minDistance` filtering
  - `$geoWithin` operator with `$box`, `$center`, and GeoJSON Polygon support
  - `$geoIntersects` operator for point-polygon intersection testing
  - Haversine distance calculation for Earth sphere distances
  - Coordinate extraction (supports [lng,lat], GeoJSON Point, {lng,lat} formats)
  - Point-in-polygon判断 (ray casting algorithm)
  - `Cursor.near()` chainable API for fluent geospatial queries
- **Geospatial Indexing** - Geohash-based spatial index
  - Geohash encoding/decoding
  - Automatic index maintenance (insert/update/delete)
  - Optimized `$near` and `$geoWithin` queries
- **Full-Text Search Index** - Optimized text search
  - Inverted index implementation
  - TF-IDF scoring for result ranking
  - Tokenization and stop word filtering
  - Automatic index maintenance
- **Multi-Database/Collection Management** - pymongo-compatible API
  - `MongoClient` class for database client
  - `Database` class for managing multiple collections
  - `Collection` class wrapping JSONLite instances
- **Network Mode** - Client-server architecture
  - `JSONLiteServer` TCP server with JSON protocol
  - `RemoteMongoClient` client proxy
  - Optional HMAC authentication
  - Full CRUD/aggregation/index support over network
- **Data Compression** - Gzip compression support
  - Configurable compression level (1-9)
  - Automatic compression detection
  - Compatible with all features (indexes/queries/special types)
- **Encryption** - AES-256-GCM encryption
  - PBKDF2-SHA256 key derivation (100,000 iterations)
  - Automatic encryption detection (ENCR magic number)
  - Compatible with compression (compress-then-encrypt)
  - Full feature compatibility (indexes/queries/aggregation/MongoClient)

### Changed
- Test suite expanded from 309 to 369 tests (+60 tests)
- All v1.1 features include comprehensive test coverage

### Security
- AES-256-GCM encryption for sensitive data
- HMAC authentication for network mode
- PBKDF2-SHA256 with 100k iterations for key derivation

---

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
| 1.1.0 | 2026-03-27 | Geospatial Queries, Full-Text Index, Multi-DB, Network Mode, Compression, Encryption |
| 1.0.0 | 2026-03-21 | Transactions, Query Cache, Indexes, Aggregation, PyPI Release |
| 0.1.0 | 2026-03-20 | Initial Release, Basic CRUD, Query Operators |

---

## Upcoming (v1.2.0)

**Planned Features:**
- Advanced aggregation stages ($lookup, $facet, $bucket)
- Change streams / real-time notifications
- Schema validation
- GridFS-like large file storage
- Performance optimizations for large datasets
- MongoDB 5.0+ feature parity

---
