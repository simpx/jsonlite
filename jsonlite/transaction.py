"""
Transaction support for JSONLite.

Provides atomic multi-operation transactions with rollback support.
"""

import copy
import sys
from typing import Dict, List, Any, Optional, Callable
from contextlib import contextmanager


class TransactionError(Exception):
    """Exception raised for transaction-related errors."""
    pass


class TransactionState:
    """Transaction state enumeration."""
    NONE = "none"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


class TransactionContext:
    """
    Transaction context manager for atomic multi-operation support.
    
    Usage:
        with db.transaction() as txn:
            db.insert_one({"name": "Alice"})
            db.update_one({"name": "Bob"}, {"$set": {"status": "active"}})
            # If any operation fails, all changes are rolled back
    """
    
    def __init__(self, db_instance: 'JSONlite'):
        self.db = db_instance
        self.state = TransactionState.NONE
        self.backup_data: Optional[Dict] = None
        self.backup_indexes: Optional[Dict] = None
        self.operations: List[Dict] = []
        
    def __enter__(self) -> 'TransactionContext':
        """Start a transaction."""
        if self.state != TransactionState.NONE:
            raise TransactionError("Transaction already in progress")
        
        # Create a deep copy of the database state for rollback
        self.backup_data = copy.deepcopy(self.db._data)
        self.backup_indexes = copy.deepcopy(self.db._indexes) if hasattr(self.db, '_indexes') else None
        self.state = TransactionState.ACTIVE
        self.operations = []
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """End transaction - commit on success, rollback on exception."""
        if self.state != TransactionState.ACTIVE:
            return False
        
        if exc_type is not None:
            # Exception occurred - rollback
            self._rollback()
            self.state = TransactionState.ROLLED_BACK
            return False  # Re-raise exception
        else:
            # Success - commit
            self._commit()
            self.state = TransactionState.COMMITTED
            return False
    
    def _commit(self) -> None:
        """Commit the transaction - persist changes."""
        # Force save to disk
        self.db._save()
        self.operations = []
    
    def _rollback(self) -> None:
        """Rollback the transaction - restore previous state."""
        if self.backup_data is not None:
            restored_data = copy.deepcopy(self.backup_data)
            self.db._data = restored_data
            # Also update _database["data"] since _save_database uses _database
            self.db._database["data"] = restored_data
        if self.backup_indexes is not None:
            restored_indexes = copy.deepcopy(self.backup_indexes)
            self.db._indexes = restored_indexes
            self.db._database["_indexes"] = restored_indexes
        
        # Force save to restore previous state
        self.db._save()
        self.operations = []
    
    def record_operation(self, op_type: str, details: Dict) -> None:
        """Record an operation for potential rollback."""
        if self.state != TransactionState.ACTIVE:
            raise TransactionError("No active transaction")
        self.operations.append({
            "type": op_type,
            "details": details
        })
    
    def is_active(self) -> bool:
        """Check if transaction is currently active."""
        return self.state == TransactionState.ACTIVE


class TransactionManager:
    """
    Manages transactions for a JSONLite database instance.
    """
    
    def __init__(self, db_instance: 'JSONlite'):
        self.db = db_instance
        self.current_transaction: Optional[TransactionContext] = None
        self._lock = False
    
    @contextmanager
    def transaction(self):
        """
        Create a transaction context for atomic operations.
        
        Usage:
            with db.transaction_manager.transaction():
                db.insert_one({...})
                db.update_one({...})
        """
        if self.current_transaction is not None:
            raise TransactionError("Nested transactions not supported")
        
        txn = TransactionContext(self.db)
        self.current_transaction = txn
        
        try:
            txn.__enter__()
            yield txn
        except:
            txn.__exit__(type(sys.exc_info()[1]), sys.exc_info()[1], sys.exc_info()[2])
            raise
        else:
            txn.__exit__(None, None, None)
        finally:
            self.current_transaction = None
    
    def begin(self) -> TransactionContext:
        """Explicitly begin a transaction."""
        if self.current_transaction is not None:
            raise TransactionError("Transaction already in progress")
        
        self.current_transaction = TransactionContext(self.db)
        self.current_transaction.__enter__()
        return self.current_transaction
    
    def commit(self) -> None:
        """Commit the current transaction."""
        if self.current_transaction is None:
            raise TransactionError("No active transaction to commit")
        
        self.current_transaction._commit()
        self.current_transaction = None
    
    def rollback(self) -> None:
        """Rollback the current transaction."""
        if self.current_transaction is None:
            raise TransactionError("No active transaction to rollback")
        
        self.current_transaction._rollback()
        self.current_transaction = None
    
    def is_active(self) -> bool:
        """Check if a transaction is currently active."""
        return self.current_transaction is not None and self.current_transaction.is_active()
