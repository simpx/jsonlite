"""
JSONLite Network Server - Client-Server Architecture

Provides TCP-based server for remote JSONLite database access.
"""
import socket
import threading
import json
import hashlib
import hmac
import os
from typing import Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import logging

from .jsonlite import JSONlite, MongoClient as LocalMongoClient, Database, Collection
from .transaction import TransactionError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Constants
# =============================================================================

PROTOCOL_VERSION = "1.0"
MAGIC_HEADER = b"JLITE"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 27017  # MongoDB-compatible port
BUFFER_SIZE = 65536


# =============================================================================
# Request/Response Types
# =============================================================================

@dataclass
class Request:
    """Network request structure."""
    method: str
    database: str
    collection: str
    params: Dict[str, Any]
    request_id: str
    
    def to_bytes(self) -> bytes:
        """Serialize request to bytes."""
        data = {
            "protocol": PROTOCOL_VERSION,
            "id": self.request_id,
            "method": self.method,
            "db": self.database,
            "coll": self.collection,
            "params": self.params
        }
        return json.dumps(data).encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Request':
        """Deserialize request from bytes."""
        obj = json.loads(data.decode('utf-8'))
        return cls(
            method=obj["method"],
            database=obj["db"],
            collection=obj["coll"],
            params=obj["params"],
            request_id=obj["id"]
        )


@dataclass
class Response:
    """Network response structure."""
    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    
    def to_bytes(self) -> bytes:
        """Serialize response to bytes."""
        data = {
            "protocol": PROTOCOL_VERSION,
            "id": self.request_id,
            "ok": 1.0 if self.success else 0.0,
        }
        if self.success:
            data["result"] = self.result
        else:
            data["errmsg"] = self.error
            data["code"] = self.error_code
        return json.dumps(data).encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Response':
        """Deserialize response from bytes."""
        obj = json.loads(data.decode('utf-8'))
        return cls(
            request_id=obj["id"],
            success=obj.get("ok", 0) == 1.0,
            result=obj.get("result"),
            error=obj.get("errmsg"),
            error_code=obj.get("code")
        )


# =============================================================================
# Authentication
# =============================================================================

class Authenticator:
    """Simple HMAC-based authentication."""
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or os.urandom(32).hex()
    
    def generate_token(self, username: str) -> str:
        """Generate authentication token for a user."""
        payload = f"{username}:{os.urandom(16).hex()}"
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{payload}:{signature}"
    
    def verify_token(self, token: str) -> Optional[str]:
        """Verify token and return username if valid."""
        try:
            parts = token.split(":")
            if len(parts) != 3:
                return None
            username, nonce, signature = parts
            expected_sig = hmac.new(
                self.secret_key.encode(),
                f"{username}:{nonce}".encode(),
                hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(signature, expected_sig):
                return username
        except Exception:
            pass
        return None


# =============================================================================
# Server Implementation
# =============================================================================

class JSONLiteServer:
    """
    JSONLite Network Server
    
    Provides TCP-based access to JSONLite databases.
    MongoDB wire protocol compatible (simplified).
    """
    
    def __init__(
        self,
        data_dir: str = "./data",
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        auth_enabled: bool = False,
        auth_secret: Optional[str] = None
    ):
        self.data_dir = data_dir
        self.host = host
        self.port = port
        self.auth_enabled = auth_enabled
        self.authenticator = Authenticator(auth_secret) if auth_enabled else None
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._clients: Dict[int, socket.socket] = {}
        self._lock = threading.Lock()
        
        # Database cache - use LocalMongoClient to manage databases
        self._client = LocalMongoClient(data_dir=data_dir)
    
    def _get_database(self, db_name: str) -> Database:
        """Get or create database instance."""
        return self._client[db_name]
    
    def _get_collection(self, db_name: str, coll_name: str) -> Collection:
        """Get collection instance."""
        db = self._get_database(db_name)
        return db[coll_name]
    
    def _handle_request(self, request: Request, client_addr: Tuple[str, int]) -> Response:
        """Process incoming request and return response."""
        try:
            coll = self._get_collection(request.database, request.collection)
            
            # Route to appropriate method
            method = request.method.lower()
            
            if method == "insert_one":
                result = coll.insert_one(request.params.get("document", {}))
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"inserted_id": result.inserted_id, "acknowledged": True}
                )
            
            elif method == "insert_many":
                result = coll.insert_many(request.params.get("documents", []))
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"inserted_ids": result.inserted_ids, "acknowledged": True}
                )
            
            elif method == "find_one":
                filter_doc = request.params.get("filter", {})
                result = coll.find_one(filter_doc)
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result=result
                )
            
            elif method == "find":
                filter_doc = request.params.get("filter", {})
                cursor = coll.find(filter_doc)
                
                # Apply optional modifiers
                if "sort" in request.params:
                    sort_spec = request.params["sort"]
                    if isinstance(sort_spec, list):
                        for field, direction in sort_spec:
                            cursor = cursor.sort(field, direction)
                    else:
                        cursor = cursor.sort(sort_spec[0], sort_spec[1])
                
                if "skip" in request.params:
                    cursor = cursor.skip(request.params["skip"])
                
                if "limit" in request.params:
                    cursor = cursor.limit(request.params["limit"])
                
                if "projection" in request.params:
                    cursor = cursor.projection(request.params["projection"])
                
                results = cursor.toArray()
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result=results
                )
            
            elif method == "update_one":
                filter_doc = request.params.get("filter", {})
                update_doc = request.params.get("update", {})
                upsert = request.params.get("upsert", False)
                result = coll.update_one(filter_doc, update_doc, upsert=upsert)
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={
                        "matched_count": result.matched_count,
                        "modified_count": result.modified_count,
                        "upserted_id": result.upserted_id,
                        "acknowledged": True
                    }
                )
            
            elif method == "update_many":
                filter_doc = request.params.get("filter", {})
                update_doc = request.params.get("update", {})
                result = coll.update_many(filter_doc, update_doc)
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={
                        "matched_count": result.matched_count,
                        "modified_count": result.modified_count,
                        "acknowledged": True
                    }
                )
            
            elif method == "delete_one":
                filter_doc = request.params.get("filter", {})
                result = coll.delete_one(filter_doc)
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"deleted_count": result.deleted_count, "acknowledged": True}
                )
            
            elif method == "delete_many":
                filter_doc = request.params.get("filter", {})
                result = coll.delete_many(filter_doc)
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"deleted_count": result.deleted_count, "acknowledged": True}
                )
            
            elif method == "count_documents":
                filter_doc = request.params.get("filter", {})
                count = coll.count_documents(filter_doc)
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"count": count}
                )
            
            elif method == "aggregate":
                pipeline = request.params.get("pipeline", [])
                cursor = coll.aggregate(pipeline)
                results = cursor.toArray()
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result=results
                )
            
            elif method == "create_index":
                field = request.params.get("field")
                unique = request.params.get("unique", False)
                index_name = coll.create_index(field, unique=unique)
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"index_name": index_name}
                )
            
            elif method == "drop_index":
                field = request.params.get("field")
                coll.drop_index(field)
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"acknowledged": True}
                )
            
            elif method == "drop":
                coll.drop()
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"acknowledged": True}
                )
            
            elif method == "ping":
                return Response(
                    request_id=request.request_id,
                    success=True,
                    result={"ok": 1.0}
                )
            
            else:
                return Response(
                    request_id=request.request_id,
                    success=False,
                    error=f"Unknown method: {method}",
                    error_code="METHOD_NOT_FOUND"
                )
        
        except TransactionError as e:
            return Response(
                request_id=request.request_id,
                success=False,
                error=str(e),
                error_code="TRANSACTION_ERROR"
            )
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            return Response(
                request_id=request.request_id,
                success=False,
                error=str(e),
                error_code="INTERNAL_ERROR"
            )
    
    def _handle_client(self, client_socket: socket.socket, client_addr: Tuple[str, int]):
        """Handle client connection."""
        client_id = id(client_socket)
        logger.info(f"Client connected: {client_addr}")
        
        with self._lock:
            self._clients[client_id] = client_socket
        
        try:
            buffer = b""
            while self._running:
                try:
                    # Receive data
                    data = client_socket.recv(BUFFER_SIZE)
                    if not data:
                        break
                    
                    buffer += data
                    
                    # Process complete messages (newline-delimited)
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if line.startswith(MAGIC_HEADER):
                            # Extract payload length
                            header = line.decode('utf-8')
                            parts = header.split(":")
                            if len(parts) >= 2:
                                payload_len = int(parts[1])
                                
                                # Wait for complete payload
                                while len(buffer) < payload_len:
                                    chunk = client_socket.recv(BUFFER_SIZE)
                                    if not chunk:
                                        break
                                    buffer += chunk
                                
                                if len(buffer) >= payload_len:
                                    payload = buffer[:payload_len]
                                    buffer = buffer[payload_len:]
                                    
                                    # Parse and handle request
                                    try:
                                        request = Request.from_bytes(payload)
                                        response = self._handle_request(request, client_addr)
                                        
                                        # Send response
                                        response_header = f"{MAGIC_HEADER.decode()}:{len(response.to_bytes())}\n".encode()
                                        client_socket.sendall(response_header + response.to_bytes())
                                    except json.JSONDecodeError as e:
                                        logger.error(f"Invalid JSON from {client_addr}: {e}")
                                        error_resp = Response(
                                            request_id="unknown",
                                            success=False,
                                            error="Invalid JSON",
                                            error_code="PARSE_ERROR"
                                        )
                                        error_header = f"{MAGIC_HEADER.decode()}:{len(error_resp.to_bytes())}\n".encode()
                                        client_socket.sendall(error_header + error_resp.to_bytes())
                
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Error handling client {client_addr}: {e}")
                    break
        
        finally:
            with self._lock:
                self._clients.pop(client_id, None)
            client_socket.close()
            logger.info(f"Client disconnected: {client_addr}")
    
    def start(self, background: bool = False):
        """Start the server."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(100)
        self._server_socket.settimeout(1.0)
        self._running = True
        
        logger.info(f"JSONLite Server started on {self.host}:{self.port}")
        logger.info(f"Data directory: {os.path.abspath(self.data_dir)}")
        
        if background:
            thread = threading.Thread(target=self._accept_loop, daemon=True)
            thread.start()
            return thread
        else:
            self._accept_loop()
    
    def _accept_loop(self):
        """Accept client connections."""
        while self._running:
            try:
                client_socket, client_addr = self._server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_addr),
                    daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Accept error: {e}")
    
    def stop(self):
        """Stop the server."""
        logger.info("Stopping server...")
        self._running = False
        
        # Close all client connections
        with self._lock:
            for client_socket in list(self._clients.values()):
                try:
                    client_socket.close()
                except Exception:
                    pass
            self._clients.clear()
        
        # Close server socket
        if self._server_socket:
            self._server_socket.close()
            self._server_socket = None
        
        # Close client connection
        try:
            self._client.close()
        except Exception:
            pass
        
        logger.info("Server stopped")
    
    def generate_auth_token(self, username: str) -> Optional[str]:
        """Generate authentication token (if auth enabled)."""
        if self.authenticator:
            return self.authenticator.generate_token(username)
        return None


# =============================================================================
# Convenience Functions
# =============================================================================

def run_server(
    data_dir: str = "./data",
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    background: bool = False
) -> JSONLiteServer:
    """
    Run a JSONLite server.
    
    Args:
        data_dir: Directory to store database files
        host: Host to bind to
        port: Port to listen on
        background: If True, run in background thread
    
    Returns:
        JSONLiteServer instance
    """
    server = JSONLiteServer(data_dir=data_dir, host=host, port=port)
    server.start(background=background)
    return server


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="JSONLite Network Server")
    parser.add_argument("--data-dir", default="./data", help="Data directory")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--auth", action="store_true", help="Enable authentication")
    
    args = parser.parse_args()
    
    server = JSONLiteServer(
        data_dir=args.data_dir,
        host=args.host,
        port=args.port,
        auth_enabled=args.auth
    )
    
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
