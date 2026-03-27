"""Tests for $graphLookup aggregation stage."""

import pytest
import os
import shutil
from jsonlite import JSONlite, MongoClient


class TestGraphLookupBasic:
    """Test basic $graphLookup functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test databases."""
        self.test_dir = tmp_path / "graph_lookup_test"
        self.test_dir.mkdir()
        
        # Create employees collection with hierarchical data
        self.employees_path = str(self.test_dir / "employees.json")
        self.employees = JSONlite(self.employees_path)
        # Use employee_id instead of _id for custom IDs
        result = self.employees.insert_many([
            {"employee_id": 1, "name": "Alice", "reports_to": None, "level": "CEO"},
            {"employee_id": 2, "name": "Bob", "reports_to": 1, "level": "VP"},
            {"employee_id": 3, "name": "Charlie", "reports_to": 1, "level": "VP"},
            {"employee_id": 4, "name": "Diana", "reports_to": 2, "level": "Manager"},
            {"employee_id": 5, "name": "Eve", "reports_to": 2, "level": "Manager"},
            {"employee_id": 6, "name": "Frank", "reports_to": 3, "level": "Manager"},
            {"employee_id": 7, "name": "Grace", "reports_to": 4, "level": "Developer"},
            {"employee_id": 8, "name": "Henry", "reports_to": 4, "level": "Developer"},
            {"employee_id": 9, "name": "Ivy", "reports_to": 5, "level": "Developer"},
        ])
        self.inserted_ids = result.inserted_ids
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_graph_lookup_recursive_hierarchy(self):
        """Test $graphLookup for recursive hierarchy traversal (finding managers)."""
        # To find managers (who you report TO):
        # - Start with your reports_to value
        # - Find docs where employee_id == that value
        # - Those are your managers
        result = self.employees.aggregate([
            {
                "$graphLookup": {
                    "from": "employees",
                    "startWith": "$reports_to",
                    "connectFromField": "reports_to",
                    "connectToField": "employee_id",
                    "as": "managers"
                }
            }
        ]).all()
        
        # Find Alice (CEO, reports_to=None, no managers above)
        alice = next(r for r in result if r["name"] == "Alice")
        assert alice["managers"] == []
        
        # Find Diana (reports to Bob (2), who reports to Alice (1))
        diana = next(r for r in result if r["name"] == "Diana")
        assert len(diana["managers"]) == 2
        manager_names = [m["name"] for m in diana["managers"]]
        assert "Bob" in manager_names
        assert "Alice" in manager_names
    
    def test_graph_lookup_with_max_depth(self):
        """Test $graphLookup with maxDepth restriction."""
        result = self.employees.aggregate([
            {
                "$graphLookup": {
                    "from": "employees",
                    "startWith": "$reports_to",
                    "connectFromField": "reports_to",
                    "connectToField": "employee_id",
                    "as": "managers",
                    "maxDepth": 1
                }
            }
        ]).all()
        
        # Find Grace (reports to Diana (4), who reports to Bob (2), who reports to Alice (1))
        grace = next(r for r in result if r["name"] == "Grace")
        # With maxDepth=1, we get depth 0 (Diana) and depth 1 (Bob)
        # MongoDB semantics: maxDepth=1 means traverse up to depth 1
        assert len(grace["managers"]) == 2
        manager_names = [m["name"] for m in grace["managers"]]
        assert "Diana" in manager_names  # depth 0
        assert "Bob" in manager_names    # depth 1
    
    def test_graph_lookup_with_depth_field(self):
        """Test $graphLookup with depthField to track recursion depth."""
        result = self.employees.aggregate([
            {
                "$graphLookup": {
                    "from": "employees",
                    "startWith": "$reports_to",
                    "connectFromField": "reports_to",
                    "connectToField": "employee_id",
                    "as": "managers",
                    "depthField": "level_depth"
                }
            }
        ]).all()
        
        # Find Henry (reports to Diana (4) -> Bob (2) -> Alice (1))
        henry = next(r for r in result if r["name"] == "Henry")
        assert len(henry["managers"]) == 3
        
        # Check depth values
        depths = {m["name"]: m["level_depth"] for m in henry["managers"]}
        assert depths["Diana"] == 0  # Direct manager (depth 0)
        assert depths["Bob"] == 1    # One level up (depth 1)
        assert depths["Alice"] == 2  # Two levels up (depth 2)
    
    def test_graph_lookup_downward_traversal(self):
        """Test $graphLookup traversing downward (finding subordinates)."""
        # To find subordinates (who reports TO you):
        # - Start with your employee_id
        # - Find docs where reports_to == your employee_id
        # - Those are your direct reports
        # - Continue recursively
        result = self.employees.aggregate([
            {
                "$graphLookup": {
                    "from": "employees",
                    "startWith": "$employee_id",
                    "connectFromField": "employee_id",
                    "connectToField": "reports_to",
                    "as": "subordinates"
                }
            }
        ]).all()
        
        # Find Alice (CEO, employee_id=1, should have all other employees as subordinates)
        alice = next(r for r in result if r["name"] == "Alice")
        assert len(alice["subordinates"]) == 8  # Everyone else (Bob, Charlie, Diana, Eve, Frank, Grace, Henry, Ivy)
        
        # Find Bob (VP, employee_id=2, should have Diana, Eve, and their reports)
        bob = next(r for r in result if r["name"] == "Bob")
        assert len(bob["subordinates"]) == 5  # Diana, Eve, Grace, Henry, Ivy
        subordinate_names = [s["name"] for s in bob["subordinates"]]
        assert "Diana" in subordinate_names
        assert "Eve" in subordinate_names
        assert "Grace" in subordinate_names
        assert "Henry" in subordinate_names
        assert "Ivy" in subordinate_names
        
        # Find Grace (Developer, employee_id=7, no subordinates)
        grace = next(r for r in result if r["name"] == "Grace")
        assert grace["subordinates"] == []


class TestGraphLookupAdvanced:
    """Test advanced $graphLookup scenarios."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test databases."""
        self.test_dir = tmp_path / "graph_lookup_adv_test"
        self.test_dir.mkdir()
        
        # Create social network (followers/following)
        self.users_path = str(self.test_dir / "users.json")
        self.users = JSONlite(self.users_path)
        self.users.insert_many([
            {"user_num": 1, "name": "Alice", "following": [2, 3]},
            {"user_num": 2, "name": "Bob", "following": [1, 3, 4]},
            {"user_num": 3, "name": "Charlie", "following": [1]},
            {"user_num": 4, "name": "Diana", "following": [2]},
            {"user_num": 5, "name": "Eve", "following": []},
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_graph_lookup_array_connections(self):
        """Test $graphLookup with array fields for connections."""
        result = self.users.aggregate([
            {
                "$graphLookup": {
                    "from": "users",
                    "startWith": "$user_num",
                    "connectFromField": "following",
                    "connectToField": "user_num",
                    "as": "network",
                    "maxDepth": 2
                }
            }
        ]).all()
        
        # Find Alice's network
        alice = next(r for r in result if r["name"] == "Alice")
        # Alice follows Bob(2) and Charlie(3)
        # Bob follows Alice(1), Charlie(3), Diana(4)
        # Charlie follows Alice(1)
        # At depth 2, should reach Diana through Bob
        network_nums = [u["user_num"] for u in alice["network"]]
        assert 2 in network_nums  # Bob
        assert 3 in network_nums  # Charlie
        assert 4 in network_nums  # Diana (through Bob)
    
    def test_graph_lookup_with_restrict_search(self):
        """Test $graphLookup with restrictSearchWithMatch filter."""
        result = self.users.aggregate([
            {
                "$graphLookup": {
                    "from": "users",
                    "startWith": "$user_num",
                    "connectFromField": "following",
                    "connectToField": "user_num",
                    "as": "network",
                    "restrictSearchWithMatch": {"name": {"$ne": "Eve"}}
                }
            }
        ]).all()
        
        # Eve should not appear in any network
        for user in result:
            network_names = [u["name"] for u in user["network"]]
            assert "Eve" not in network_names
    
    def test_graph_lookup_cycle_detection(self):
        """Test that $graphLookup handles cycles correctly (no infinite loops)."""
        # Create a cycle: A -> B -> C -> A
        # Following "next" field: A(1) -> B(2) -> C(3) -> A(1) [cycle]
        cycle_path = str(self.test_dir / "cycle.json")
        cycle_db = JSONlite(cycle_path)
        cycle_db.insert_many([
            {"node_id": 1, "name": "A", "next": 2},
            {"node_id": 2, "name": "B", "next": 3},
            {"node_id": 3, "name": "C", "next": 1},  # Cycle back to A
        ])
        
        # Traverse following the "next" pointers
        result = cycle_db.aggregate([
            {
                "$graphLookup": {
                    "from": "cycle",
                    "startWith": "$next",  # Start with who this node points to
                    "connectFromField": "next",
                    "connectToField": "node_id",
                    "as": "chain"
                }
            }
        ]).all()
        
        # Should not hang, and should detect cycle
        node_a = next(r for r in result if r["name"] == "A")
        # A's next is 2 (B), B's next is 3 (C), C's next is 1 (A)
        # A is already in the result set, so it won't be added again
        # Chain should be [B, C] (A is excluded because it's the starting doc's value)
        # Actually with our implementation, we traverse: start with 2, find B, then 3, find C, then 1, find A
        # A gets added because it's a different document than the starting one
        assert len(node_a["chain"]) == 3  # B, C, A (cycle detected but A is still added once)
        chain_names = [n["name"] for n in node_a["chain"]]
        assert "B" in chain_names
        assert "C" in chain_names
        assert "A" in chain_names


class TestGraphLookupMongoClient:
    """Test $graphLookup with MongoClient multi-database API."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database with MongoClient."""
        self.test_dir = tmp_path / "mongo_client_test"
        self.test_dir.mkdir()
        
        self.client = MongoClient(str(self.test_dir))
        self.db = self.client["company"]
        
        # Create departments collection
        self.departments = self.db["departments"]
        self.departments.insert_many([
            {"dept_id": "eng", "name": "Engineering", "parent": None},
            {"dept_id": "backend", "name": "Backend", "parent": "eng"},
            {"dept_id": "frontend", "name": "Frontend", "parent": "eng"},
            {"dept_id": "devops", "name": "DevOps", "parent": "backend"},
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_graph_lookup_mongo_client_api(self):
        """Test $graphLookup through MongoClient/Database API (finding parent departments)."""
        # To find ancestors (parent departments):
        # - Start with your parent dept_id
        # - Find docs where dept_id == that value
        # - Those are your parent departments
        result = self.departments.aggregate([
            {
                "$graphLookup": {
                    "from": "departments",
                    "startWith": "$parent",
                    "connectFromField": "parent",
                    "connectToField": "dept_id",
                    "as": "ancestors",
                    "depthField": "depth"
                }
            }
        ]).all()
        
        # Find DevOps (parent="backend", which has parent="eng")
        devops = next(r for r in result if r["name"] == "DevOps")
        assert len(devops["ancestors"]) == 2
        
        ancestor_names = [a["name"] for a in devops["ancestors"]]
        assert "Backend" in ancestor_names
        assert "Engineering" in ancestor_names
        
        # Check depths
        ancestor_map = {a["name"]: a["depth"] for a in devops["ancestors"]}
        assert ancestor_map["Backend"] == 0  # Direct parent
        assert ancestor_map["Engineering"] == 1  # Grandparent


class TestGraphLookupEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.test_dir = tmp_path / "edge_cases_test"
        self.test_dir.mkdir()
        
        self.db = JSONlite(str(self.test_dir / "test.json"))
        self.db.insert_many([
            {"item_id": 1, "name": "Root", "parent": None},
            {"item_id": 2, "name": "Child", "parent": 1},
            {"item_id": 3, "name": "Orphan", "parent": 999},  # Non-existent parent
        ])
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_graph_lookup_non_existent_collection(self):
        """Test $graphLookup with non-existent collection."""
        result = self.db.aggregate([
            {
                "$graphLookup": {
                    "from": "non_existent",
                    "startWith": "$item_id",
                    "connectFromField": "parent",
                    "connectToField": "item_id",
                    "as": "results"
                }
            }
        ]).all()
        
        # Should return empty arrays, not error
        for doc in result:
            assert doc["results"] == []
    
    def test_graph_lookup_no_matches(self):
        """Test $graphLookup when no matches exist."""
        result = self.db.aggregate([
            {
                "$graphLookup": {
                    "from": "test",
                    "startWith": 999,  # Non-existent ID
                    "connectFromField": "parent",
                    "connectToField": "item_id",
                    "as": "results"
                }
            }
        ]).all()
        
        # Should return empty arrays
        for doc in result:
            assert doc["results"] == []
    
    def test_graph_lookup_orphan_nodes(self):
        """Test $graphLookup with orphan nodes (references to non-existent docs)."""
        result = self.db.aggregate([
            {
                "$graphLookup": {
                    "from": "test",
                    "startWith": "$parent",
                    "connectFromField": "parent",
                    "connectToField": "item_id",
                    "as": "ancestors"
                }
            }
        ]).all()
        
        orphan = next(r for r in result if r["name"] == "Orphan")
        # Orphan has parent=999 which doesn't exist, so no ancestors
        assert len(orphan["ancestors"]) == 0
