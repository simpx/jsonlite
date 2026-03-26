"""
Test multi-database and collection management (pymongo-compatible API).
"""
import pytest
import os
import shutil
from jsonlite import MongoClient, Database, Collection


@pytest.fixture
def client():
    """Create a test client with a temporary data directory."""
    data_dir = './test_multidb_data'
    # Clean up if exists
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
    
    client = MongoClient(data_dir)
    yield client
    
    # Clean up after test
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)


class TestMongoClient:
    """Test MongoClient basic functionality."""
    
    def test_client_init(self, client):
        """Test client initialization."""
        assert client._data_dir == './test_multidb_data'
        assert os.path.exists('./test_multidb_data')
    
    def test_client_repr(self, client):
        """Test client string representation."""
        assert "MongoClient" in repr(client)
        assert "./test_multidb_data" in repr(client)
    
    def test_server_info(self, client):
        """Test server_info method."""
        info = client.server_info()
        assert 'version' in info
        assert info['ok'] == 1.0
    
    def test_close(self, client):
        """Test close method (no-op for JSONlite)."""
        client.close()  # Should not raise
    
    def test_admin_command_ping(self, client):
        """Test admin ping command."""
        result = client.admin_command('ping')
        assert result['ok'] == 1.0
    
    def test_admin_command_buildInfo(self, client):
        """Test admin buildInfo command."""
        result = client.admin_command('buildInfo')
        assert result['ok'] == 1.0
        assert 'version' in result


class TestDatabaseOperations:
    """Test database-level operations."""
    
    def test_get_database_dict_access(self, client):
        """Test getting database with dict-style access."""
        db = client['testdb']
        assert isinstance(db, Database)
        assert db.name == 'testdb'
        assert os.path.exists(os.path.join(client._data_dir, 'testdb'))
    
    def test_get_database_attr_access(self, client):
        """Test getting database with attribute access."""
        db = client.testdb
        assert isinstance(db, Database)
        assert db.name == 'testdb'
    
    def test_get_database_method(self, client):
        """Test getting database with get_database method."""
        db = client.get_database('testdb')
        assert isinstance(db, Database)
        assert db.name == 'testdb'
    
    def test_database_repr(self, client):
        """Test database string representation."""
        db = client['testdb']
        assert "Database" in repr(db)
        assert "testdb" in repr(db)
    
    def test_list_database_names_empty(self, client):
        """Test listing databases when empty."""
        names = client.list_database_names()
        assert names == []
    
    def test_list_database_names(self, client):
        """Test listing databases after creation."""
        db1 = client['db1']
        db2 = client['db2']
        db3 = client['db3']
        
        # Create a collection in each to materialize the database
        db1['test'].insert_one({'x': 1})
        db2['test'].insert_one({'x': 1})
        db3['test'].insert_one({'x': 1})
        
        names = client.list_database_names()
        assert 'db1' in names
        assert 'db2' in names
        assert 'db3' in names
        assert len(names) == 3
    
    def test_list_databases(self, client):
        """Test listing databases with metadata."""
        db = client['testdb']
        db['test'].insert_one({'x': 1})
        
        databases = client.list_databases()
        assert len(databases) == 1
        assert databases[0]['name'] == 'testdb'
        assert 'sizeOnDisk' in databases[0]
        assert databases[0]['empty'] == False
    
    def test_drop_database_by_name(self, client):
        """Test dropping database by name."""
        db = client['testdb']
        db['test'].insert_one({'x': 1})
        
        assert os.path.exists(os.path.join(client._data_dir, 'testdb'))
        
        client.drop_database('testdb')
        
        assert not os.path.exists(os.path.join(client._data_dir, 'testdb'))
    
    def test_drop_database_by_object(self, client):
        """Test dropping database by Database object."""
        db = client['testdb']
        db['test'].insert_one({'x': 1})
        
        db_path = os.path.join(client._data_dir, 'testdb')
        assert os.path.exists(db_path)
        
        client.drop_database(db)
        
        assert not os.path.exists(db_path)
    
    def test_database_command_ping(self, client):
        """Test database ping command."""
        db = client['testdb']
        result = db.command('ping')
        assert result['ok'] == 1.0
    
    def test_database_command_serverStatus(self, client):
        """Test database serverStatus command."""
        db = client['testdb']
        db['test'].insert_one({'x': 1})
        
        result = db.command('serverStatus')
        assert result['ok'] == 1.0
        assert result['db'] == 'testdb'
        assert result['collections'] == 1


class TestCollectionOperations:
    """Test collection-level operations."""
    
    def test_get_collection_dict_access(self, client):
        """Test getting collection with dict-style access."""
        db = client['testdb']
        coll = db['users']
        assert isinstance(coll, Collection)
        assert coll.name == 'users'
    
    def test_get_collection_attr_access(self, client):
        """Test getting collection with attribute access."""
        db = client['testdb']
        coll = db.users
        assert isinstance(coll, Collection)
        assert coll.name == 'users'
    
    def test_get_collection_method(self, client):
        """Test getting collection with get_collection method."""
        db = client['testdb']
        coll = db.get_collection('users')
        assert isinstance(coll, Collection)
        assert coll.name == 'users'
    
    def test_collection_repr(self, client):
        """Test collection string representation."""
        db = client['testdb']
        coll = db['users']
        assert "Collection" in repr(coll)
        assert "users" in repr(coll)
    
    def test_collection_insert_find(self, client):
        """Test basic insert and find on collection."""
        db = client['testdb']
        coll = db['users']
        
        result = coll.insert_one({'name': 'Alice', 'age': 30})
        assert result.inserted_id == 1
        
        result = coll.insert_many([
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35}
        ])
        assert len(result.inserted_ids) == 2
        
        # Find all
        results = coll.find().toArray()
        assert len(results) == 3
        
        # Find with filter
        results = coll.find({'age': {'$gte': 30}}).toArray()
        assert len(results) == 2
        assert all(r['age'] >= 30 for r in results)
    
    def test_collection_update(self, client):
        """Test update operations on collection."""
        db = client['testdb']
        coll = db['users']
        
        coll.insert_one({'name': 'Alice', 'age': 30})
        
        result = coll.update_one({'name': 'Alice'}, {'$set': {'age': 31}})
        assert result.modified_count == 1
        
        doc = coll.find_one({'name': 'Alice'})
        assert doc['age'] == 31
    
    def test_collection_delete(self, client):
        """Test delete operations on collection."""
        db = client['testdb']
        coll = db['users']
        
        coll.insert_many([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35}
        ])
        
        result = coll.delete_one({'name': 'Bob'})
        assert result.deleted_count == 1
        
        results = coll.find().toArray()
        assert len(results) == 2
    
    def test_collection_count_documents(self, client):
        """Test count_documents on collection."""
        db = client['testdb']
        coll = db['users']
        
        coll.insert_many([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35}
        ])
        
        assert coll.count_documents({}) == 3
        assert coll.count_documents({'age': {'$gte': 30}}) == 2
    
    def test_collection_distinct(self, client):
        """Test distinct on collection."""
        db = client['testdb']
        coll = db['users']
        
        coll.insert_many([
            {'name': 'Alice', 'category': 'A'},
            {'name': 'Bob', 'category': 'B'},
            {'name': 'Charlie', 'category': 'A'}
        ])
        
        categories = coll.distinct('category')
        assert set(categories) == {'A', 'B'}
    
    def test_collection_aggregate(self, client):
        """Test aggregation on collection."""
        db = client['testdb']
        coll = db['users']
        
        coll.insert_many([
            {'name': 'Alice', 'age': 30, 'city': 'NYC'},
            {'name': 'Bob', 'age': 25, 'city': 'LA'},
            {'name': 'Charlie', 'age': 35, 'city': 'NYC'}
        ])
        
        # Group by city
        pipeline = [
            {'$group': {'_id': '$city', 'count': {'$sum': 1}}}
        ]
        results = coll.aggregate(pipeline).toArray()
        assert len(results) == 2
        
        nyc = next(r for r in results if r['_id'] == 'NYC')
        assert nyc['count'] == 2
    
    def test_collection_drop(self, client):
        """Test dropping a collection."""
        db = client['testdb']
        coll = db['users']
        
        coll.insert_one({'name': 'Alice'})
        
        coll_file = os.path.join(client._data_dir, 'testdb', 'users.json')
        assert os.path.exists(coll_file)
        
        coll.drop()
        
        assert not os.path.exists(coll_file)
    
    def test_list_collection_names(self, client):
        """Test listing collection names."""
        db = client['testdb']
        
        db['users'].insert_one({'x': 1})
        db['products'].insert_one({'x': 1})
        db['orders'].insert_one({'x': 1})
        
        names = db.list_collection_names()
        assert 'users' in names
        assert 'products' in names
        assert 'orders' in names
        assert len(names) == 3
    
    def test_list_collections(self, client):
        """Test listing collections with metadata."""
        db = client['testdb']
        db['users'].insert_many([{'x': 1}, {'x': 2}])
        
        collections = db.list_collections()
        assert len(collections) == 1
        assert collections[0]['name'] == 'users'
    
    def test_create_collection(self, client):
        """Test creating a collection explicitly."""
        db = client['testdb']
        
        coll = db.create_collection('users')
        assert isinstance(coll, Collection)
        assert coll.name == 'users'
    
    def test_drop_collection(self, client):
        """Test dropping a collection by name."""
        db = client['testdb']
        db['users'].insert_one({'x': 1})
        
        coll_file = os.path.join(client._data_dir, 'testdb', 'users.json')
        assert os.path.exists(coll_file)
        
        db.drop_collection('users')
        
        assert not os.path.exists(coll_file)
    
    def test_database_drop_database(self, client):
        """Test Database.drop_database method."""
        db = client['testdb']
        db['users'].insert_one({'x': 1})
        db['products'].insert_one({'x': 1})
        
        db_path = os.path.join(client._data_dir, 'testdb')
        assert os.path.exists(db_path)
        
        db.drop_database()
        
        assert not os.path.exists(db_path)
        assert 'testdb' not in client._databases


class TestMultiDatabaseIsolation:
    """Test that databases are isolated from each other."""
    
    def test_database_isolation(self, client):
        """Test that data in different databases is isolated."""
        db1 = client['db1']
        db2 = client['db2']
        
        db1['users'].insert_one({'name': 'Alice', 'db': 1})
        db2['users'].insert_one({'name': 'Bob', 'db': 2})
        
        db1_users = db1['users'].find().toArray()
        db2_users = db2['users'].find().toArray()
        
        assert len(db1_users) == 1
        assert len(db2_users) == 1
        assert db1_users[0]['name'] == 'Alice'
        assert db2_users[0]['name'] == 'Bob'
    
    def test_collection_isolation(self, client):
        """Test that collections within a database are isolated."""
        db = client['testdb']
        
        db['users'].insert_one({'type': 'user', 'name': 'Alice'})
        db['products'].insert_one({'type': 'product', 'name': 'Widget'})
        
        users = db['users'].find().toArray()
        products = db['products'].find().toArray()
        
        assert len(users) == 1
        assert len(products) == 1
        assert users[0]['type'] == 'user'
        assert products[0]['type'] == 'product'


class TestPymongoCompatibility:
    """Test pymongo API compatibility."""
    
    def test_fluent_api(self, client):
        """Test fluent/chainable API."""
        db = client['testdb']
        coll = db['users']
        
        coll.insert_many([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35},
            {'name': 'David', 'age': 28}
        ])
        
        results = (coll
            .find({'age': {'$gte': 25}})
            .sort('age', -1)
            .limit(2)
            .skip(1)
            .toArray())
        
        assert len(results) == 2
        assert results[0]['age'] == 30
        assert results[1]['age'] == 28
    
    def test_index_operations(self, client):
        """Test index operations on collection."""
        db = client['testdb']
        coll = db['users']
        
        coll.insert_many([
            {'name': 'Alice', 'email': 'alice@example.com'},
            {'name': 'Bob', 'email': 'bob@example.com'}
        ])
        
        # Create index
        index_name = coll.create_index('email', unique=True)
        assert index_name
        
        # List indexes
        indexes = coll.list_indexes()
        assert len(indexes) >= 1
        
        # Drop index
        coll.drop_index('email')
    
    def test_transaction_on_collection(self, client):
        """Test transaction on collection."""
        db = client['testdb']
        coll = db['users']
        
        with coll.transaction() as txn:
            coll.insert_one({'name': 'Alice', 'balance': 1000})
            coll.insert_one({'name': 'Bob', 'balance': 500})
        
        # Verify both inserts succeeded
        users = coll.find().toArray()
        assert len(users) == 2
        
        # Test transaction rollback
        with pytest.raises(Exception):
            with coll.transaction():
                coll.insert_one({'name': 'Charlie', 'balance': 200})
                raise Exception("Simulated error")
        
        # Charlie should not exist
        charlie = coll.find_one({'name': 'Charlie'})
        assert charlie is None


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_attribute_error_on_private(self, client):
        """Test that private attributes raise AttributeError."""
        db = client['testdb']
        
        with pytest.raises(AttributeError):
            db._private_attr
        
        with pytest.raises(AttributeError):
            client._private_attr
    
    def test_empty_database(self, client):
        """Test operations on empty database."""
        db = client['emptydb']
        
        assert db.list_collection_names() == []
        assert db.list_collections() == []
    
    def test_empty_collection(self, client):
        """Test operations on empty collection."""
        db = client['testdb']
        coll = db['empty']
        
        assert coll.count_documents({}) == 0
        assert coll.find().toArray() == []
        assert coll.find_one() is None
    
    def test_database_with_special_chars(self, client):
        """Test database/collection names with special characters."""
        db = client['test-db_123']
        coll = db['user_data']
        
        coll.insert_one({'x': 1})
        
        assert db.list_collection_names() == ['user_data']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
