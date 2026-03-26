"""
Geospatial query tests for JSONLite.

Tests for $near, $geoWithin, $geoIntersects operators and Cursor.near() method.
"""

import pytest
import os
import tempfile
from jsonlite import JSONlite


@pytest.fixture
def db():
    """Create a temporary database with geospatial data."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    
    database = JSONlite(path)
    
    # Insert test data with various location formats
    database.insert_many([
        {"name": "Beijing Office", "location": [116.4074, 39.9042]},  # [lng, lat]
        {"name": "Shanghai Office", "location": [121.4737, 31.2304]},
        {"name": "Guangzhou Office", "location": [113.2644, 23.1291]},
        {"name": "Shenzhen Office", "location": [114.0579, 22.5431]},
        {"name": "Chengdu Office", "location": [104.0668, 30.5728]},
        # GeoJSON Point format
        {"name": "Hangzhou Office", "location": {"type": "Point", "coordinates": [120.1551, 30.2741]}},
        # Custom format
        {"name": "Nanjing Office", "location": {"lng": 118.7969, "lat": 32.0603}},
        # No location
        {"name": "Remote Worker", "status": "remote"},
    ])
    
    yield database
    
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


class TestGeoDistance:
    """Test geospatial distance calculations."""
    
    def test_haversine_distance_beijing_shanghai(self):
        """Test distance calculation between Beijing and Shanghai."""
        from jsonlite.jsonlite import _haversine_distance
        
        beijing = (116.4074, 39.9042)
        shanghai = (121.4737, 31.2304)
        
        distance = _haversine_distance(beijing, shanghai)
        
        # Expected: ~1068 km
        assert 1000000 < distance < 1150000  # meters
    
    def test_haversine_distance_same_point(self):
        """Test distance to same point is zero."""
        from jsonlite.jsonlite import _haversine_distance
        
        point = (116.4074, 39.9042)
        distance = _haversine_distance(point, point)
        
        assert distance < 0.01  # Should be essentially zero


class TestCoordinateExtraction:
    """Test coordinate extraction from various formats."""
    
    def test_extract_array_format(self):
        """Test extraction from [lng, lat] array."""
        from jsonlite.jsonlite import _extract_coordinates
        
        coords = _extract_coordinates([116.4, 39.9])
        assert coords == (116.4, 39.9)
    
    def test_extract_geojson_point(self):
        """Test extraction from GeoJSON Point."""
        from jsonlite.jsonlite import _extract_coordinates
        
        coords = _extract_coordinates({
            "type": "Point",
            "coordinates": [116.4, 39.9]
        })
        assert coords == (116.4, 39.9)
    
    def test_extract_custom_format(self):
        """Test extraction from custom {lng, lat} format."""
        from jsonlite.jsonlite import _extract_coordinates
        
        coords = _extract_coordinates({"lng": 116.4, "lat": 39.9})
        assert coords == (116.4, 39.9)
    
    def test_extract_lon_lat_format(self):
        """Test extraction from {lon, lat} format."""
        from jsonlite.jsonlite import _extract_coordinates
        
        coords = _extract_coordinates({"lon": 116.4, "lat": 39.9})
        assert coords == (116.4, 39.9)
    
    def test_extract_invalid_format(self):
        """Test extraction from invalid format returns None."""
        from jsonlite.jsonlite import _extract_coordinates
        
        assert _extract_coordinates(None) is None
        assert _extract_coordinates("invalid") is None
        assert _extract_coordinates({"x": 1, "y": 2}) is None


class TestNearOperator:
    """Test $near operator."""
    
    def test_near_sorts_by_distance(self, db):
        """Test that $near sorts results by distance."""
        # Query near Beijing
        results = db.find({
            "location": {
                "$near": [116.4074, 39.9042]
            }
        })
        
        assert len(results) > 0
        # First result should be Beijing (closest to itself)
        assert results[0]["name"] == "Beijing Office"
    
    def test_near_with_max_distance(self, db):
        """Test $near with maxDistance filter."""
        # Query within 50km of Beijing (only Beijing itself)
        results = db.find({
            "location": {
                "$near": [116.4074, 39.9042],
                "$maxDistance": 50000  # 50km
            }
        })
        
        # Should only include Beijing (other cities are much farther)
        assert len(results) == 1
        assert results[0]["name"] == "Beijing Office"
    
    def test_near_with_larger_max_distance(self, db):
        """Test $near with larger maxDistance."""
        # Query within 1200km of Beijing (should include Shanghai)
        results = db.find({
            "location": {
                "$near": [116.4074, 39.9042],
                "$maxDistance": 1200000  # 1200km
            }
        })
        
        # Should include Beijing and Shanghai
        names = [r["name"] for r in results]
        assert "Beijing Office" in names
        assert "Shanghai Office" in names
    
    def test_near_excludes_no_location(self, db):
        """Test that $near excludes documents without location."""
        results = db.find({
            "location": {
                "$near": [116.4074, 39.9042]
            }
        })
        
        names = [r["name"] for r in results]
        assert "Remote Worker" not in names
    
    def test_near_with_geojson_point(self, db):
        """Test $near with GeoJSON Point format in database."""
        # Query near Hangzhou (stored as GeoJSON Point)
        results = db.find({
            "location": {
                "$near": [120.1551, 30.2741]
            }
        })
        
        assert len(results) > 0
        # Hangzhou should be first or second (very close to query point)
        names = [r["name"] for r in results[:2]]
        assert "Hangzhou Office" in names


class TestCursorNear:
    """Test Cursor.near() method."""
    
    def test_cursor_near_sorts_by_distance(self, db):
        """Test Cursor.near() sorts by distance."""
        results = db.find({}).near("location", [116.4074, 39.9042]).all()
        
        assert len(results) > 0
        assert results[0]["name"] == "Beijing Office"
    
    def test_cursor_near_with_max_distance(self, db):
        """Test Cursor.near() with max_distance filter."""
        results = db.find({}).near("location", [116.4074, 39.9042], max_distance=50000).all()
        
        assert len(results) == 1
        assert results[0]["name"] == "Beijing Office"
    
    def test_cursor_near_with_min_distance(self, db):
        """Test Cursor.near() with min_distance filter."""
        # Exclude anything within 100m of Beijing
        results = db.find({}).near("location", [116.4074, 39.9042], min_distance=100).all()
        
        # Beijing Office should be excluded (it's at the exact point)
        names = [r["name"] for r in results]
        assert "Beijing Office" not in names
    
    def test_cursor_near_chained_with_limit(self, db):
        """Test Cursor.near() can be chained with limit."""
        results = db.find({}).near("location", [116.4074, 39.9042]).limit(3).all()
        
        assert len(results) == 3
        assert results[0]["name"] == "Beijing Office"


class TestGeoWithin:
    """Test $geoWithin operator."""
    
    def test_geoWithin_box(self, db):
        """Test $geoWithin with box geometry."""
        # Box covering Beijing area
        results = db.find({
            "location": {
                "$geoWithin": {
                    "$box": [
                        [116.0, 39.5],  # min [lng, lat]
                        [117.0, 40.5]   # max [lng, lat]
                    ]
                }
            }
        })
        
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "Beijing Office" in names
    
    def test_geoWithin_circle(self, db):
        """Test $geoWithin with circle geometry."""
        # Circle centered on Beijing with 100km radius
        results = db.find({
            "location": {
                "$geoWithin": {
                    "$center": [116.4074, 39.9042],
                    "$radius": 100000  # 100km
                }
            }
        })
        
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "Beijing Office" in names
    
    def test_geoWithin_polygon(self, db):
        """Test $geoWithin with GeoJSON Polygon."""
        # Rough polygon around Beijing area
        results = db.find({
            "location": {
                "$geoWithin": {
                    "type": "Polygon",
                    "coordinates": [[
                        [116.0, 39.5],
                        [117.0, 39.5],
                        [117.0, 40.5],
                        [116.0, 40.5],
                        [116.0, 39.5]  # Close polygon
                    ]]
                }
            }
        })
        
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "Beijing Office" in names


class TestGeoIntersects:
    """Test $geoIntersects operator."""
    
    def test_geoIntersects_point_in_polygon(self, db):
        """Test $geoIntersects with point in polygon."""
        # Beijing point should intersect with Beijing polygon
        results = db.find({
            "location": {
                "$geoIntersects": {
                    "type": "Polygon",
                    "coordinates": [[
                        [116.0, 39.5],
                        [117.0, 39.5],
                        [117.0, 40.5],
                        [116.0, 40.5],
                        [116.0, 39.5]
                    ]]
                }
            }
        })
        
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "Beijing Office" in names


class TestGeospatialIndex:
    """Test geospatial indexing with Geohash."""
    
    def test_create_geospatial_index(self, db):
        """Test creating a geospatial index."""
        index_name = db.create_geospatial_index("location")
        
        assert index_name == "location_geohash"
        
        indexes = db.list_indexes()
        geo_indexes = [i for i in indexes if i.get('type') == 'geospatial']
        
        assert len(geo_indexes) == 1
        assert geo_indexes[0]['field'] == "location"
        assert geo_indexes[0]['precision'] == 12
    
    def test_create_geospatial_index_custom_precision(self, db):
        """Test creating a geospatial index with custom precision."""
        index_name = db.create_geospatial_index("location", precision=8)
        
        assert index_name == "location_geohash"
        
        indexes = db.list_indexes()
        geo_indexes = [i for i in indexes if i.get('type') == 'geospatial']
        
        assert len(geo_indexes) == 1
        assert geo_indexes[0]['precision'] == 8
    
    def test_create_geospatial_index_custom_name(self, db):
        """Test creating a geospatial index with custom name."""
        index_name = db.create_geospatial_index("location", name="my_geo_index")
        
        assert index_name == "my_geo_index"
        
        indexes = db.list_indexes()
        geo_index_names = [i['name'] for i in indexes if i.get('type') == 'geospatial']
        
        assert "my_geo_index" in geo_index_names
    
    def test_geospatial_index_auto_populated(self, db):
        """Test that existing documents are indexed when creating geospatial index."""
        # Create index after inserting documents
        db.create_geospatial_index("location", precision=8)
        
        # Query should use the index
        results = db.find({
            "location": {
                "$near": [116.4074, 39.9042],
                "$maxDistance": 50000  # 50km
            }
        })
        
        assert len(results) > 0
        assert results[0]["name"] == "Beijing Office"
    
    def test_geospatial_index_updated_on_insert(self, db):
        """Test that new documents are added to geospatial index."""
        db.create_geospatial_index("location", precision=8)
        
        # Insert new document
        db.insert_one({
            "name": "Tianjin Office",
            "location": [117.2008, 39.0842]
        })
        
        # Query should find the new document
        results = db.find({
            "location": {
                "$near": [117.2008, 39.0842],
                "$maxDistance": 10000  # 10km
            }
        })
        
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "Tianjin Office" in names
    
    def test_geospatial_index_updated_on_update(self, db):
        """Test that updated documents are re-indexed."""
        db.create_geospatial_index("location", precision=8)
        
        # Update document's location
        db.update_one(
            {"name": "Beijing Office"},
            {"$set": {"location": [117.2008, 39.0842]}}  # Move to Tianjin
        )
        
        # Query for Beijing location should not find it
        results = db.find({
            "location": {
                "$near": [116.4074, 39.9042],
                "$maxDistance": 10000  # 10km
            }
        })
        
        names = [r["name"] for r in results]
        assert "Beijing Office" not in names
    
    def test_geospatial_index_updated_on_delete(self, db):
        """Test that deleted documents are removed from geospatial index."""
        db.create_geospatial_index("location", precision=8)
        
        # Delete document
        db.delete_one({"name": "Beijing Office"})
        
        # Query should not find deleted document
        results = db.find({
            "location": {
                "$near": [116.4074, 39.9042],
                "$maxDistance": 10000
            }
        })
        
        names = [r["name"] for r in results]
        assert "Beijing Office" not in names
    
    def test_geospatial_index_with_geoWithin(self, db):
        """Test geospatial index optimization for $geoWithin queries."""
        db.create_geospatial_index("location", precision=8)
        
        # Query with box
        results = db.find({
            "location": {
                "$geoWithin": {
                    "$box": [
                        [116.0, 39.5],
                        [117.0, 40.5]
                    ]
                }
            }
        })
        
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "Beijing Office" in names
    
    def test_geohash_encoding_decoding(self):
        """Test Geohash encoding and decoding."""
        from jsonlite.jsonlite import _encode_geohash, _decode_geohash
        
        # Encode Beijing coordinates
        geohash = _encode_geohash(116.4074, 39.9042, precision=12)
        assert len(geohash) == 12
        
        # Decode should give bounding box containing original point
        bbox = _decode_geohash(geohash)
        min_coord, max_coord = bbox
        
        assert min_coord[0] <= 116.4074 <= max_coord[0]
        assert min_coord[1] <= 39.9042 <= max_coord[1]
    
    def test_geohash_neighbors(self):
        """Test Geohash neighbor calculation."""
        from jsonlite.jsonlite import _encode_geohash, _geohash_neighbors
        
        geohash = _encode_geohash(116.4074, 39.9042, precision=8)
        neighbors = _geohash_neighbors(geohash)
        
        # Should have 8 neighbors
        assert len(neighbors) == 8
        
        # Neighbors should be different from original
        assert geohash not in neighbors
        
        # All neighbors should be same length
        assert all(len(n) == 8 for n in neighbors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
