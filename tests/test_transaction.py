"""
Test suite for JSONLite transaction support.
"""

import pytest
import os
import tempfile
from jsonlite import JSONlite, TransactionError


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    db = JSONlite(path)
    yield db
    os.unlink(path)


class TestTransactionContextManager:
    """Test transaction context manager functionality."""
    
    def test_transaction_commit(self, db):
        """Test successful transaction commit."""
        with db.transaction() as txn:
            assert txn.is_active()
            db.insert_one({"name": "Alice", "balance": 1000})
            db.insert_one({"name": "Bob", "balance": 500})
        
        # After commit, data should persist
        assert db.count_documents({}) == 2
        alice = db.find_one({"name": "Alice"})
        assert alice["balance"] == 1000
    
    def test_transaction_rollback_on_exception(self, db):
        """Test transaction rollback when exception occurs."""
        initial_count = db.count_documents({})
        
        with pytest.raises(ValueError):
            with db.transaction():
                db.insert_one({"name": "Alice", "balance": 1000})
                raise ValueError("Simulated error")
        
        # After rollback, count should be unchanged
        assert db.count_documents({}) == initial_count
        assert db.find_one({"name": "Alice"}) is None
    
    def test_transaction_rollback_partial_insert(self, db):
        """Test rollback restores state even after multiple operations."""
        # Start with some data
        db.insert_one({"name": "Original", "value": 1})
        initial_count = db.count_documents({})
        
        with pytest.raises(Exception):
            with db.transaction():
                db.insert_one({"name": "New1", "value": 2})
                db.insert_one({"name": "New2", "value": 3})
                db.update_one({"name": "Original"}, {"$set": {"value": 999}})
                raise Exception("Rollback trigger")
        
        # Should rollback to original state
        assert db.count_documents({}) == initial_count
        original = db.find_one({"name": "Original"})
        assert original["value"] == 1  # Not 999
        assert db.find_one({"name": "New1"}) is None
        assert db.find_one({"name": "New2"}) is None
    
    def test_nested_transaction_error(self, db):
        """Test that nested transactions raise an error."""
        with pytest.raises(TransactionError):
            with db.transaction():
                with db.transaction():  # Should raise
                    db.insert_one({"name": "Test"})
    
    def test_transaction_outside_context(self, db):
        """Test that transaction methods outside context raise errors."""
        with pytest.raises(TransactionError):
            db.commit_transaction()
        
        with pytest.raises(TransactionError):
            db.rollback_transaction()


class TestTransactionOperations:
    """Test various operations within transactions."""
    
    def test_transaction_with_update(self, db):
        """Test update operations in transaction."""
        db.insert_one({"name": "Account", "balance": 1000})
        
        with db.transaction():
            db.update_one({"name": "Account"}, {"$set": {"balance": 500}})
        
        account = db.find_one({"name": "Account"})
        assert account["balance"] == 500
    
    def test_transaction_with_delete(self, db):
        """Test delete operations in transaction."""
        db.insert_one({"name": "ToDelete", "value": 1})
        db.insert_one({"name": "ToKeep", "value": 2})
        
        with db.transaction():
            db.delete_one({"name": "ToDelete"})
        
        assert db.count_documents({}) == 1
        assert db.find_one({"name": "ToDelete"}) is None
        assert db.find_one({"name": "ToKeep"}) is not None
    
    def test_transaction_rollback_update(self, db):
        """Test rollback restores updated values."""
        db.insert_one({"name": "Account", "balance": 1000})
        
        with pytest.raises(Exception):
            with db.transaction():
                db.update_one({"name": "Account"}, {"$set": {"balance": 0}})
                raise Exception("Rollback")
        
        account = db.find_one({"name": "Account"})
        assert account["balance"] == 1000  # Restored
    
    def test_transaction_rollback_delete(self, db):
        """Test rollback restores deleted documents."""
        db.insert_one({"name": "Important", "value": 1})
        
        with pytest.raises(Exception):
            with db.transaction():
                db.delete_many({})
                raise Exception("Rollback")
        
        # All documents should be restored
        assert db.count_documents({}) == 1
        assert db.find_one({"name": "Important"}) is not None


class TestExplicitTransactionAPI:
    """Test explicit begin/commit/rollback API."""
    
    def test_explicit_commit(self, db):
        """Test explicit transaction commit."""
        txn = db.begin_transaction()
        try:
            db.insert_one({"name": "Explicit", "value": 1})
            db.commit_transaction()
        except:
            db.rollback_transaction()
        
        assert db.count_documents({}) == 1
    
    def test_explicit_rollback(self, db):
        """Test explicit transaction rollback."""
        db.insert_one({"name": "Original", "value": 1})
        initial_count = db.count_documents({})
        
        txn = db.begin_transaction()
        try:
            db.insert_one({"name": "New", "value": 2})
            db.rollback_transaction()
        except:
            pass
        
        assert db.count_documents({}) == initial_count
        assert db.find_one({"name": "New"}) is None
    
    def test_in_transaction_check(self, db):
        """Test in_transaction() method."""
        assert db.in_transaction() is False
        
        with db.transaction():
            assert db.in_transaction() is True
        
        assert db.in_transaction() is False


class TestTransactionWithIndexes:
    """Test transactions work correctly with indexes."""
    
    def test_transaction_with_index_maintenance(self, db):
        """Test indexes are maintained correctly after transaction."""
        db.create_index("name")
        
        with db.transaction():
            db.insert_one({"name": "Alice", "value": 1})
            db.insert_one({"name": "Bob", "value": 2})
        
        # Query using index should work
        alice = db.find_one({"name": "Alice"})
        assert alice is not None
        assert alice["value"] == 1
    
    def test_transaction_rollback_with_index(self, db):
        """Test index state is restored on rollback."""
        db.create_index("name")
        db.insert_one({"name": "Original", "value": 1})
        
        with pytest.raises(Exception):
            with db.transaction():
                db.insert_one({"name": "New", "value": 2})
                raise Exception("Rollback")
        
        # Index query should only find original
        assert db.count_documents({"name": "Original"}) == 1
        assert db.count_documents({"name": "New"}) == 0


class TestTransactionEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_transaction(self, db):
        """Test transaction with no operations."""
        with db.transaction():
            pass  # No operations
        # Should commit successfully
        assert db.count_documents({}) == 0
    
    def test_transaction_multiple_commits_attempt(self, db):
        """Test that commit can only be called once per transaction."""
        with db.transaction():
            db.insert_one({"name": "Test"})
        # After context exits, transaction is committed
        # Trying to commit again should fail
        with pytest.raises(TransactionError):
            db.commit_transaction()
    
    def test_transaction_data_persistence(self, db):
        """Test that committed transactions persist to disk."""
        with db.transaction():
            db.insert_one({"name": "Persistent", "value": 42})
        
        # Create new instance to verify disk persistence
        db2 = JSONlite(db._filename)
        record = db2.find_one({"name": "Persistent"})
        assert record is not None
        assert record["value"] == 42


class TestTransactionAtomicity:
    """Test atomicity guarantees."""
    
    def test_atomic_transfer(self, db):
        """Test atomic money transfer between accounts."""
        # Setup
        db.insert_one({"name": "Alice", "balance": 1000})
        db.insert_one({"name": "Bob", "balance": 500})
        
        def transfer(from_name, to_name, amount):
            with db.transaction():
                from_acc = db.find_one({"name": from_name})
                to_acc = db.find_one({"name": to_name})
                
                if from_acc["balance"] < amount:
                    raise ValueError("Insufficient funds")
                
                db.update_one({"name": from_name}, {"$set": {"balance": from_acc["balance"] - amount}})
                db.update_one({"name": to_name}, {"$set": {"balance": to_acc["balance"] + amount}})
        
        # Successful transfer
        transfer("Alice", "Bob", 300)
        
        alice = db.find_one({"name": "Alice"})
        bob = db.find_one({"name": "Bob"})
        
        assert alice["balance"] == 700
        assert bob["balance"] == 800
        # Total should be conserved
        assert alice["balance"] + bob["balance"] == 1500
    
    def test_atomic_transfer_rollback(self, db):
        """Test transfer rolls back on insufficient funds."""
        db.insert_one({"name": "Alice", "balance": 100})
        db.insert_one({"name": "Bob", "balance": 500})
        
        with pytest.raises(ValueError):
            # Try to transfer more than available
            with db.transaction():
                from_acc = db.find_one({"name": "Alice"})
                to_acc = db.find_one({"name": "Bob"})
                
                if from_acc["balance"] < 500:
                    raise ValueError("Insufficient funds")
                
                db.update_one({"name": "Alice"}, {"$set": {"balance": from_acc["balance"] - 500}})
                db.update_one({"name": "Bob"}, {"$set": {"balance": to_acc["balance"] + 500}})
        
        # Balances should be unchanged
        alice = db.find_one({"name": "Alice"})
        bob = db.find_one({"name": "Bob"})
        
        assert alice["balance"] == 100
        assert bob["balance"] == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
