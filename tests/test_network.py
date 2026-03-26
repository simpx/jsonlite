"""
Test network server and client functionality.
"""
import pytest
import os
import shutil
import time
import threading
from jsonlite import JSONLiteServer, RemoteMongoClient, run_server


@pytest.fixture
def server_data_dir():
    """Create a temporary data directory for server tests."""
    data_dir = './test_server_data'
    # Clean up if exists
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
    os.makedirs(data_dir)
    yield data_dir
    # Clean up after test
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)


@pytest.fixture
def running_server(server_data_dir):
    """Start a test server in background thread."""
    server = JSONLiteServer(
        data_dir=server_data_dir,
        host="127.0.0.1",
        port=27018,  # Use non-standard port to avoid conflicts
        auth_enabled=False
    )
    
    # Start server in background
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    
    # Wait for server to start
    time.sleep(0.5)
    
    yield server
    
    # Stop server
    server.stop()
    thread.join(timeout=2.0)


class TestJSONLiteServer:
    """Test JSONLiteServer basic functionality."""
    
    def test_server_init(self, server_data_dir):
        """Test server initialization."""
        server = JSONLiteServer(
            data_dir=server_data_dir,
            host="127.0.0.1",
            port=27019
        )
        assert server.data_dir == server_data_dir
        assert server.host == "127.0.0.1"
        assert server.port == 27019
        assert server.auth_enabled == False
    
    def test_server_init_with_auth(self, server_data_dir):
        """Test server initialization with authentication."""
        server = JSONLiteServer(
            data_dir=server_data_dir,
            host="127.0.0.1",
            port=27019,
            auth_enabled=True,
            auth_secret="test_secret"
        )
        assert server.auth_enabled == True
        assert server.authenticator is not None
    
    def test_server_generate_token(self, server_data_dir):
        """Test token generation."""
        server = JSONLiteServer(
            data_dir=server_data_dir,
            auth_enabled=True,
            auth_secret="test_secret"
        )
        token = server.generate_auth_token("testuser")
        assert token is not None
        assert ":" in token
        
        # Verify token
        username = server.authenticator.verify_token(token)
        assert username == "testuser"


class TestRemoteClient:
    """Test remote client functionality."""
    
    def test_client_init(self):
        """Test client initialization."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        assert client.host == "127.0.0.1"
        assert client.port == 27018
    
    def test_client_repr(self):
        """Test client string representation."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        assert "MongoClient" in repr(client)
        assert "127.0.0.1:27018" in repr(client)
    
    def test_client_context_manager(self):
        """Test client as context manager."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        with client:
            pass
        # Should not raise


class TestClientServerIntegration:
    """Test client-server integration."""
    
    def test_connect_and_ping(self, running_server):
        """Test basic connection and ping."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        info = client.server_info()
        assert info['ok'] == 1.0
        assert 'version' in info
        client.close()
    
    def test_remote_insert_find(self, running_server):
        """Test remote insert and find operations."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        db = client['testdb']
        coll = db['users']
        
        # Insert one
        result = coll.insert_one({'name': 'Alice', 'age': 30})
        assert result.acknowledged == True
        assert result.inserted_id == 1
        
        # Find one
        doc = coll.find_one({'name': 'Alice'})
        assert doc is not None
        assert doc['name'] == 'Alice'
        assert doc['age'] == 30
        
        # Insert many
        result = coll.insert_many([
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35}
        ])
        assert len(result.inserted_ids) == 2
        
        # Find all
        cursor = coll.find()
        results = cursor.toArray()
        assert len(results) == 3
        
        # Find with filter
        cursor = coll.find({'age': {'$gte': 30}})
        results = cursor.toArray()
        assert len(results) == 2
        
        client.close()
    
    def test_remote_update(self, running_server):
        """Test remote update operations."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        db = client['testdb']
        coll = db['users']
        
        # Insert
        coll.insert_one({'name': 'Alice', 'age': 30})
        
        # Update one
        result = coll.update_one(
            {'name': 'Alice'},
            {'$set': {'age': 31}}
        )
        assert result.matched_count == 1
        assert result.modified_count == 1
        
        # Verify update
        doc = coll.find_one({'name': 'Alice'})
        assert doc['age'] == 31
        
        client.close()
    
    def test_remote_delete(self, running_server):
        """Test remote delete operations."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        db = client['testdb']
        coll = db['users']
        
        # Insert
        coll.insert_many([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35}
        ])
        
        # Delete one
        result = coll.delete_one({'name': 'Bob'})
        assert result.deleted_count == 1
        
        # Verify
        results = coll.find().toArray()
        assert len(results) == 2
        
        # Delete many
        result = coll.delete_many({'age': {'$gte': 30}})
        assert result.deleted_count == 2
        
        client.close()
    
    def test_remote_count(self, running_server):
        """Test remote count operations."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        db = client['testdb']
        coll = db['users']
        
        coll.insert_many([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35}
        ])
        
        assert coll.count_documents({}) == 3
        assert coll.count_documents({'age': {'$gte': 30}}) == 2
        
        client.close()
    
    def test_remote_aggregate(self, running_server):
        """Test remote aggregation."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
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
        cursor = coll.aggregate(pipeline)
        results = cursor.toArray()
        assert len(results) == 2
        
        nyc = next(r for r in results if r['_id'] == 'NYC')
        assert nyc['count'] == 2
        
        client.close()
    
    def test_remote_index(self, running_server):
        """Test remote index operations."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        db = client['testdb']
        coll = db['users']
        
        coll.insert_one({'name': 'Alice', 'email': 'alice@example.com'})
        
        # Create index
        index_name = coll.create_index('email', unique=True)
        assert index_name is not None
        
        # Drop index
        coll.drop_index('email')
        
        client.close()
    
    def test_remote_drop_collection(self, running_server):
        """Test dropping collection remotely."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        db = client['testdb']
        coll = db['users']
        
        coll.insert_one({'name': 'Alice'})
        
        # Verify exists
        doc = coll.find_one({'name': 'Alice'})
        assert doc is not None
        
        # Drop
        coll.drop()
        
        # Verify by inserting into fresh collection (drop removes the file)
        # Re-insert to verify collection can be recreated
        coll2 = db['users']
        result = coll2.insert_one({'name': 'Bob'})
        assert result.inserted_id == 1  # Fresh collection, ID starts at 1
        
        client.close()
    
    def test_multiple_databases(self, running_server):
        """Test multiple databases isolation."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        
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
        
        client.close()
    
    def test_client_reconnect(self, running_server):
        """Test client reconnection."""
        client1 = RemoteMongoClient(host="127.0.0.1", port=27018)
        db = client1['testdb']
        coll = db['users']
        coll.insert_one({'name': 'Alice'})
        client1.close()
        
        # New client should see same data
        client2 = RemoteMongoClient(host="127.0.0.1", port=27018)
        db2 = client2['testdb']
        coll2 = db2['users']
        doc = coll2.find_one({'name': 'Alice'})
        assert doc is not None
        assert doc['name'] == 'Alice'
        client2.close()


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_invalid_method(self, running_server):
        """Test handling of invalid method."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        # This should raise an exception from the server
        with pytest.raises(Exception):
            # Try to call non-existent method via low-level API
            response = client._send_request("nonexistent_method", "testdb", "users", {})
            if not response.success:
                raise Exception(response.error)
        client.close()
    
    def test_empty_database(self, running_server):
        """Test operations on empty database."""
        client = RemoteMongoClient(host="127.0.0.1", port=27018)
        db = client['emptydb']
        coll = db['users']
        
        assert coll.count_documents({}) == 0
        assert coll.find().toArray() == []
        assert coll.find_one() is None
        
        client.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
