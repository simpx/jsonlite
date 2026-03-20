# Transaction Support

JSONLite provides atomic transaction support for multi-operation workflows. Transactions ensure that a group of operations either all succeed together or all fail together (atomicity).

## Overview

Transactions in JSONLite provide:

- **Atomicity**: All operations in a transaction succeed or all are rolled back
- **Rollback Support**: Automatic state restoration on errors
- **Context Manager API**: Pythonic `with` statement support
- **Explicit API**: Manual begin/commit/rollback control
- **Index Maintenance**: Indexes are properly restored on rollback

## Basic Usage

### Context Manager (Recommended)

The simplest way to use transactions is with the context manager:

```python
from jsonlite import JSONlite

db = JSONlite("mydb.json")

# All operations succeed - changes are committed
with db.transaction() as txn:
    db.insert_one({"name": "Alice", "balance": 1000})
    db.insert_one({"name": "Bob", "balance": 500})
    # Transaction commits automatically here

# If any operation fails - all changes are rolled back
try:
    with db.transaction():
        db.insert_one({"name": "Alice", "balance": 1000})
        db.update_one({"name": "Bob"}, {"$set": {"balance": 0}})
        raise ValueError("Something went wrong!")
        # Transaction rolls back automatically, no changes persist
except ValueError:
    print("Transaction rolled back")
```

### Explicit API

For more control, use the explicit begin/commit/rollback methods:

```python
txn = db.begin_transaction()
try:
    db.insert_one({"name": "Alice", "balance": 1000})
    db.insert_one({"name": "Bob", "balance": 500})
    db.commit_transaction()
    print("Transaction committed successfully")
except Exception as e:
    db.rollback_transaction()
    print(f"Transaction rolled back: {e}")
```

## Real-World Example: Money Transfer

```python
def transfer(db, from_name, to_name, amount):
    """Transfer money between accounts atomically."""
    with db.transaction():
        # Get current balances
        from_acc = db.find_one({"name": from_name})
        to_acc = db.find_one({"name": to_name})
        
        # Check sufficient funds
        if from_acc["balance"] < amount:
            raise ValueError("Insufficient funds")
        
        # Update both accounts
        db.update_one(
            {"name": from_name},
            {"$set": {"balance": from_acc["balance"] - amount}}
        )
        db.update_one(
            {"name": to_name},
            {"$set": {"balance": to_acc["balance"] + amount}}
        )
        
        # Transaction commits automatically if no exception

# Usage
transfer(db, "Alice", "Bob", 100)
```

## Transaction Methods

### `db.transaction()`

Context manager for atomic operations.

**Returns**: TransactionContext object

**Example**:
```python
with db.transaction() as txn:
    # Operations here are atomic
    pass
```

### `db.begin_transaction()`

Explicitly begin a transaction.

**Returns**: TransactionContext object

**Example**:
```python
txn = db.begin_transaction()
# ... operations ...
db.commit_transaction()  # or db.rollback_transaction()
```

### `db.commit_transaction()`

Commit the current transaction, persisting all changes.

**Raises**: `TransactionError` if no active transaction

### `db.rollback_transaction()`

Rollback the current transaction, restoring the previous state.

**Raises**: `TransactionError` if no active transaction

### `db.in_transaction()`

Check if currently inside a transaction.

**Returns**: `bool`

**Example**:
```python
print(db.in_transaction())  # False
with db.transaction():
    print(db.in_transaction())  # True
print(db.in_transaction())  # False
```

## TransactionError

Exception raised for transaction-related errors.

**Common scenarios**:
- Nested transactions attempted
- Commit/rollback called without active transaction

```python
from jsonlite import TransactionError

try:
    with db.transaction():
        with db.transaction():  # Raises TransactionError
            pass
except TransactionError as e:
    print(f"Transaction error: {e}")
```

## Limitations

### No Nested Transactions

JSONLite does not support nested transactions. Attempting to start a transaction within another transaction raises `TransactionError`.

```python
with db.transaction():
    with db.transaction():  # ❌ Raises TransactionError
        pass
```

### Single Database Scope

Transactions operate on a single database file. Cross-database transactions are not supported.

### Memory-Based Rollback

Rollback restores from an in-memory backup created at transaction start. For very large databases, this may consume significant memory.

## Performance Considerations

- **Backup Overhead**: Transaction start creates a deep copy of the database state
- **No Disk I/O During Transaction**: Changes are held in memory until commit
- **Atomic Commit**: Commit writes all changes to disk atomically
- **Best For**: Short-lived transactions with moderate data sizes

## Best Practices

1. **Keep Transactions Short**: Minimize the time spent in a transaction
2. **Handle Exceptions**: Always use try/except or context managers
3. **Validate Early**: Check preconditions before making changes
4. **Use Context Managers**: Prefer `with db.transaction()` for automatic cleanup
5. **Test Rollback Scenarios**: Ensure your code handles rollback correctly

## Testing

JSONLite includes comprehensive transaction tests:

```bash
pytest tests/test_transaction.py -v
```

**Test coverage**:
- Context manager commit/rollback
- Explicit API commit/rollback
- Nested transaction errors
- Update/delete operations
- Index maintenance
- Atomic transfer scenarios
- Data persistence

## Implementation Details

### How It Works

1. **Begin**: Create deep copy of database state (data + indexes)
2. **Operations**: Modify in-memory state (no disk I/O)
3. **Commit**: Write in-memory state to disk atomically
4. **Rollback**: Restore from backup copy, write to disk

### Thread Safety

Transactions use the same file locking mechanism as regular operations. Only one write operation can occur at a time.

### Error Handling

When an exception occurs within a transaction:
1. Exception is caught by the context manager
2. Rollback restores previous state
3. Exception is re-raised for caller handling

## Examples

### Batch Insert with Rollback

```python
def batch_insert(db, records):
    """Insert multiple records atomically."""
    with db.transaction():
        for record in records:
            db.insert_one(record)
        # All or nothing
```

### Conditional Update

```python
def update_if_exists(db, filter, update):
    """Update only if document exists, rollback if not."""
    with db.transaction():
        doc = db.find_one(filter)
        if doc is None:
            raise ValueError("Document not found")
        db.update_one(filter, update)
```

### Multi-Step Workflow

```python
def create_order(db, customer_id, items):
    """Create order with inventory check."""
    with db.transaction():
        # Check inventory
        for item in items:
            product = db.find_one({"_id": item["product_id"]})
            if product["stock"] < item["quantity"]:
                raise ValueError(f"Insufficient stock for {product['name']}")
        
        # Deduct inventory
        for item in items:
            db.update_one(
                {"_id": item["product_id"]},
                {"$inc": {"stock": -item["quantity"]}}
            )
        
        # Create order
        order = {
            "customer_id": customer_id,
            "items": items,
            "status": "created"
        }
        db.insert_one(order)
```

---

**Added**: 2026-03-21  
**Version**: v1.0.0
