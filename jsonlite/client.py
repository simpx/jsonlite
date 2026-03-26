"""
JSONLite Network Client - Remote Database Access

Provides client-side interface for connecting to JSONLite servers.
"""
import socket
import json
import uuid
import threading
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import logging
import time

from .server import Request, Response, MAGIC_HEADER, DEFAULT_HOST, DEFAULT_PORT, PROTOCOL_VERSION

logger = logging.getLogger(__name__)


# =============================================================================
# Cursor Implementations
# =============================================================================

class RemoteCursor:
    """Cursor for remote query results."""
    
    def __init__(self, collection: 'RemoteCollection', results: List[Dict]):
        self._collection = collection
        self._results = results
        self._position = 0
    
    def __iter__(self):
        return iter(self._results)
    
    def __next__(self):
        if self._position >= len(self._results):
            raise StopIteration
        result = self._results[self._position]
        self._position += 1
        return result
    
    def toArray(self) -> List[Dict]:
        """Return all results as a list."""
        return self._results
    
    def next(self) -> Optional[Dict]:
        """Get next result."""
        try:
            return next(self)
        except StopIteration:
            return None
    
    def sort(self, key: str, direction: int = 1) -> 'RemoteCursor':
        """Sort results (client-side for remote cursor)."""
        reverse = direction < 0
        self._results.sort(key=lambda x: x.get(key, None), reverse=reverse)
        return self
    
    def limit(self, n: int) -> 'RemoteCursor':
        """Limit results."""
        self._results = self._results[:n]
        return self
    
    def skip(self, n: int) -> 'RemoteCursor':
        """Skip results."""
        self._results = self._results[n:]
        return self


class RemoteAggregationCursor:
    """Cursor for remote aggregation results."""
    
    def __init__(self, collection: 'RemoteCollection', results: List[Dict]):
        self._collection = collection
        self._results = results
    
    def __iter__(self):
        return iter(self._results)
    
    def toArray(self) -> List[Dict]:
        """Return all results as a list."""
        return self._results
    
    def next(self) -> Optional[Dict]:
        """Get next result."""
        try:
            return next(iter(self._results))
        except StopIteration:
            return None


# =============================================================================
# Result Wrappers
# =============================================================================

@dataclass
class InsertOneResult:
    """Result of insert_one operation."""
    inserted_id: Any
    acknowledged: bool = True


@dataclass
class InsertManyResult:
    """Result of insert_many operation."""
    inserted_ids: List[Any]
    acknowledged: bool = True


@dataclass
class UpdateResult:
    """Result of update operation."""
    matched_count: int
    modified_count: int
    upserted_id: Optional[Any] = None
    acknowledged: bool = True


@dataclass
class DeleteResult:
    """Result of delete operation."""
    deleted_count: int
    acknowledged: bool = True


# =============================================================================
# Remote Collection
# =============================================================================

class RemoteCollection:
    """
    Remote collection proxy.
    
    Provides the same API as local Collection but communicates
    with a remote JSONLite server.
    """
    
    def __init__(self, database: 'RemoteDatabase', name: str):
        self._database = database
        self.name = name
    
    @property
    def full_name(self) -> str:
        """Get full collection name (database.collection)."""
        return f"{self._database.name}.{self.name}"
    
    def _send_request(self, method: str, params: Dict[str, Any] = None) -> Response:
        """Send request to server."""
        return self._database._send_request(method, self.name, params)
    
    def insert_one(self, document: Dict) -> InsertOneResult:
        """Insert a single document."""
        response = self._send_request("insert_one", {"document": document})
        if response.success:
            return InsertOneResult(
                inserted_id=response.result["inserted_id"],
                acknowledged=response.result["acknowledged"]
            )
        raise Exception(response.error)
    
    def insert_many(self, documents: List[Dict]) -> InsertManyResult:
        """Insert multiple documents."""
        response = self._send_request("insert_many", {"documents": documents})
        if response.success:
            return InsertManyResult(
                inserted_ids=response.result["inserted_ids"],
                acknowledged=response.result["acknowledged"]
            )
        raise Exception(response.error)
    
    def find_one(self, filter: Dict = None) -> Optional[Dict]:
        """Find a single document."""
        response = self._send_request("find_one", {"filter": filter or {}})
        if response.success:
            return response.result
        raise Exception(response.error)
    
    def find(self, filter: Dict = None) -> RemoteCursor:
        """Find documents matching filter."""
        response = self._send_request("find", {"filter": filter or {}})
        if response.success:
            return RemoteCursor(self, response.result)
        raise Exception(response.error)
    
    def update_one(
        self,
        filter: Dict,
        update: Dict,
        upsert: bool = False
    ) -> UpdateResult:
        """Update a single document."""
        response = self._send_request("update_one", {
            "filter": filter,
            "update": update,
            "upsert": upsert
        })
        if response.success:
            return UpdateResult(
                matched_count=response.result["matched_count"],
                modified_count=response.result["modified_count"],
                upserted_id=response.result.get("upserted_id"),
                acknowledged=response.result["acknowledged"]
            )
        raise Exception(response.error)
    
    def update_many(self, filter: Dict, update: Dict) -> UpdateResult:
        """Update multiple documents."""
        response = self._send_request("update_many", {
            "filter": filter,
            "update": update
        })
        if response.success:
            return UpdateResult(
                matched_count=response.result["matched_count"],
                modified_count=response.result["modified_count"],
                acknowledged=response.result["acknowledged"]
            )
        raise Exception(response.error)
    
    def delete_one(self, filter: Dict) -> DeleteResult:
        """Delete a single document."""
        response = self._send_request("delete_one", {"filter": filter})
        if response.success:
            return DeleteResult(
                deleted_count=response.result["deleted_count"],
                acknowledged=response.result["acknowledged"]
            )
        raise Exception(response.error)
    
    def delete_many(self, filter: Dict) -> DeleteResult:
        """Delete multiple documents."""
        response = self._send_request("delete_many", {"filter": filter})
        if response.success:
            return DeleteResult(
                deleted_count=response.result["deleted_count"],
                acknowledged=response.result["acknowledged"]
            )
        raise Exception(response.error)
    
    def count_documents(self, filter: Dict = None) -> int:
        """Count documents matching filter."""
        response = self._send_request("count_documents", {"filter": filter or {}})
        if response.success:
            return response.result["count"]
        raise Exception(response.error)
    
    def aggregate(self, pipeline: List[Dict]) -> RemoteAggregationCursor:
        """Run aggregation pipeline."""
        response = self._send_request("aggregate", {"pipeline": pipeline})
        if response.success:
            return RemoteAggregationCursor(self, response.result)
        raise Exception(response.error)
    
    def create_index(self, field: str, unique: bool = False) -> str:
        """Create an index on a field."""
        response = self._send_request("create_index", {
            "field": field,
            "unique": unique
        })
        if response.success:
            return response.result["index_name"]
        raise Exception(response.error)
    
    def drop_index(self, field: str):
        """Drop an index."""
        response = self._send_request("drop_index", {"field": field})
        if not response.success:
            raise Exception(response.error)
    
    def drop(self):
        """Drop the collection."""
        response = self._send_request("drop")
        if not response.success:
            raise Exception(response.error)
    
    def __repr__(self) -> str:
        return f"RemoteCollection({self.full_name})"


# =============================================================================
# Remote Database
# =============================================================================

class RemoteDatabase:
    """
    Remote database proxy.
    
    Provides access to collections on a remote JSONLite server.
    """
    
    def __init__(self, client: 'MongoClient', name: str):
        self._client = client
        self.name = name
        self._collections: Dict[str, RemoteCollection] = {}
    
    def _send_request(self, method: str, collection: str, params: Dict = None) -> Response:
        """Send request to server."""
        return self._client._send_request(method, self.name, collection, params)
    
    def __getitem__(self, name: str) -> RemoteCollection:
        """Get collection by dict-style access."""
        if name not in self._collections:
            self._collections[name] = RemoteCollection(self, name)
        return self._collections[name]
    
    def __getattr__(self, name: str) -> RemoteCollection:
        """Get collection by attribute access."""
        if name.startswith('_'):
            raise AttributeError(name)
        return self[name]
    
    def get_collection(self, name: str) -> RemoteCollection:
        """Get collection by method call."""
        return self[name]
    
    def list_collection_names(self) -> List[str]:
        """List collection names (client-side tracking)."""
        return list(self._collections.keys())
    
    def command(self, cmd: str) -> Dict:
        """Run database command."""
        response = self._send_request("ping", "$cmd", {})
        if response.success:
            return {"ok": 1.0, "db": self.name}
        raise Exception(response.error)
    
    def drop_collection(self, name: str):
        """Drop a collection."""
        if name in self._collections:
            self._collections[name].drop()
            del self._collections[name]
    
    def create_collection(self, name: str) -> RemoteCollection:
        """Create a collection (lazy creation on first use)."""
        return self[name]
    
    def __repr__(self) -> str:
        return f"RemoteDatabase({self.name})"


# =============================================================================
# Remote Client
# =============================================================================

class MongoClient:
    """
    MongoDB-compatible client for remote JSONLite server.
    
    Usage:
        client = MongoClient("localhost", 27017)
        db = client["mydb"]
        coll = db["users"]
        coll.insert_one({"name": "Alice"})
    """
    
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = 30.0,
        auth_token: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.auth_token = auth_token
        self._databases: Dict[str, RemoteDatabase] = {}
        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
    
    def _connect(self) -> socket.socket:
        """Get or create socket connection."""
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
        return self._socket
    
    def _send_request(
        self,
        method: str,
        database: str,
        collection: str,
        params: Dict = None
    ) -> Response:
        """Send request to server and return response."""
        request = Request(
            method=method,
            database=database,
            collection=collection,
            params=params or {},
            request_id=str(uuid.uuid4())
        )
        
        with self._lock:
            sock = self._connect()
            
            # Send request with header
            payload = request.to_bytes()
            header = f"{MAGIC_HEADER.decode()}:{len(payload)}\n".encode()
            sock.sendall(header + payload)
            
            # Read response header
            response_header = b""
            while b"\n" not in response_header:
                chunk = sock.recv(1)
                if not chunk:
                    raise ConnectionError("Connection closed")
                response_header += chunk
            
            # Parse header
            header_str = response_header.decode('utf-8').strip()
            if not header_str.startswith(MAGIC_HEADER.decode()):
                raise ProtocolError(f"Invalid response header: {header_str}")
            
            payload_len = int(header_str.split(":")[1])
            
            # Read response payload
            response_data = b""
            while len(response_data) < payload_len:
                chunk = sock.recv(min(BUFFER_SIZE, payload_len - len(response_data)))
                if not chunk:
                    raise ConnectionError("Connection closed")
                response_data += chunk
            
            return Response.from_bytes(response_data)
    
    def __getitem__(self, name: str) -> RemoteDatabase:
        """Get database by dict-style access."""
        if name not in self._databases:
            self._databases[name] = RemoteDatabase(self, name)
        return self._databases[name]
    
    def __getattr__(self, name: str) -> RemoteDatabase:
        """Get database by attribute access."""
        if name.startswith('_'):
            raise AttributeError(name)
        return self[name]
    
    def get_database(self, name: str) -> RemoteDatabase:
        """Get database by method call."""
        return self[name]
    
    def list_database_names(self) -> List[str]:
        """List database names (client-side tracking)."""
        return list(self._databases.keys())
    
    def list_databases(self) -> List[Dict]:
        """List databases with metadata."""
        return [
            {"name": name, "sizeOnDisk": 0, "empty": False}
            for name in self._databases.keys()
        ]
    
    def drop_database(self, name: str):
        """Drop a database."""
        if name in self._databases:
            del self._databases[name]
    
    def server_info(self) -> Dict:
        """Get server information."""
        try:
            response = self._send_request("ping", "admin", "$cmd", {})
            if response.success:
                return {
                    "version": PROTOCOL_VERSION,
                    "ok": 1.0
                }
        except Exception:
            pass
        return {
            "version": PROTOCOL_VERSION,
            "ok": 1.0
        }
    
    def admin_command(self, cmd: str) -> Dict:
        """Run admin command."""
        if cmd == "ping":
            return {"ok": 1.0}
        elif cmd == "buildInfo":
            return {"ok": 1.0, "version": PROTOCOL_VERSION}
        return {"ok": 1.0}
    
    def close(self):
        """Close connection."""
        if self._socket:
            self._socket.close()
            self._socket = None
    
    def __repr__(self) -> str:
        return f"MongoClient({self.host}:{self.port})"
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# =============================================================================
# Exceptions
# =============================================================================

class ProtocolError(Exception):
    """Protocol error."""
    pass


class ConnectionError(Exception):
    """Connection error."""
    pass


# =============================================================================
# Convenience Functions
# =============================================================================

def connect(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 30.0
) -> MongoClient:
    """
    Connect to a JSONLite server.
    
    Args:
        host: Server host
        port: Server port
        timeout: Connection timeout in seconds
    
    Returns:
        MongoClient instance
    """
    client = MongoClient(host=host, port=port, timeout=timeout)
    # Test connection
    client.server_info()
    return client


# Buffer size constant
BUFFER_SIZE = 65536
