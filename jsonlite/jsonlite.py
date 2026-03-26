import json
import fcntl
import os
import re
import tempfile
import base64
import math
from dataclasses import dataclass
from functools import wraps
from typing import List, Dict, Union, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from copy import deepcopy
from bisect import insort_left, bisect_left, bisect_right
from collections import OrderedDict
import hashlib
from contextlib import contextmanager

# Optional fast JSON serialization (orjson is 3-4x faster than stdlib json)
try:
    import orjson
    _USE_ORJSON = True
except ImportError:
    _USE_ORJSON = False
    orjson = None

# Import transaction support
from .transaction import TransactionManager, TransactionError


def _fast_dumps(obj: Any, **kwargs) -> str:
    """Fast JSON serialization using orjson if available.
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments (default, indent, etc.)
    
    Returns:
        JSON string
    """
    if _USE_ORJSON:
        # orjson doesn't support indent or default, but is much faster
        # For cache hashing (no indent needed), use orjson
        if 'indent' not in kwargs and 'default' not in kwargs:
            return orjson.dumps(obj).decode('utf-8')
    # Fallback to standard json
    return json.dumps(obj, **kwargs)


def _fast_loads(s: str) -> Any:
    """Fast JSON deserialization using orjson if available.
    
    Args:
        s: JSON string
    
    Returns:
        Deserialized object
    """
    if _USE_ORJSON:
        return orjson.loads(s)
    return json.loads(s)


# =============================================================================
# Geospatial Helper Functions
# =============================================================================

def _extract_coordinates(value: Any) -> Optional[Tuple[float, float]]:
    """Extract [longitude, latitude] from various GeoJSON formats.
    
    Supports:
    - Direct array: [lng, lat]
    - GeoJSON Point: {"type": "Point", "coordinates": [lng, lat]}
    - Custom format: {"lng": x, "lat": y} or {"lon": x, "lat": y}
    
    Args:
        value: Value to extract coordinates from
    
    Returns:
        Tuple of (longitude, latitude) or None if invalid
    """
    if value is None:
        return None
    
    # Direct array format [lng, lat]
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (float(value[0]), float(value[1]))
        except (TypeError, ValueError):
            return None
    
    # GeoJSON Point format
    if isinstance(value, dict):
        if value.get('type') == 'Point' and 'coordinates' in value:
            coords = value['coordinates']
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                try:
                    return (float(coords[0]), float(coords[1]))
                except (TypeError, ValueError):
                    return None
        
        # Custom format {lng/lon: x, lat: y}
        lng = value.get('lng') or value.get('lon') or value.get('longitude')
        lat = value.get('lat') or value.get('latitude')
        if lng is not None and lat is not None:
            try:
                return (float(lng), float(lat))
            except (TypeError, ValueError):
                return None
    
    return None


def _haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate the great-circle distance between two points using Haversine formula.
    
    Args:
        coord1: (longitude, latitude) of first point in degrees
        coord2: (longitude, latitude) of second point in degrees
    
    Returns:
        Distance in meters
    """
    R = 6371000  # Earth's radius in meters
    
    lng1, lat1 = math.radians(coord1[0]), math.radians(coord1[1])
    lng2, lat2 = math.radians(coord2[0]), math.radians(coord2[1])
    
    dlng = lng2 - lng1
    dlat = lat2 - lat1
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def _point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Check if a point is inside a polygon using ray casting algorithm.
    
    Args:
        point: (longitude, latitude) of the point to check
        polygon: List of (longitude, latitude) vertices defining the polygon
    
    Returns:
        True if point is inside the polygon
    """
    x, y = point
    inside = False
    
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        
        # Check if ray crosses edge
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    
    return inside


def _point_in_circle(point: Tuple[float, float], center: Tuple[float, float], radius_meters: float) -> bool:
    """Check if a point is inside a circle.
    
    Args:
        point: (longitude, latitude) of the point to check
        center: (longitude, latitude) of the circle center
        radius_meters: Circle radius in meters
    
    Returns:
        True if point is inside the circle
    """
    distance = _haversine_distance(point, center)
    return distance <= radius_meters


def _extract_geometry(geometry: Any) -> Any:
    """Extract geometry from various formats.
    
    Supports:
    - GeoJSON: {"type": "Polygon", "coordinates": [...]}
    - Circle: {"$center": [lng, lat], "$radius": meters}
    - Box: {"$box": [[minLng, minLat], [maxLng, maxLat]]}
    
    Args:
        geometry: Geometry definition
    
    Returns:
        Parsed geometry object or None
    """
    if not isinstance(geometry, dict):
        return None
    
    # GeoJSON format
    if 'type' in geometry:
        return geometry
    
    # Circle format {$center: [lng, lat], $radius: meters}
    if '$center' in geometry and '$radius' in geometry:
        center = _extract_coordinates(geometry['$center'])
        if center:
            return {
                'type': 'Circle',
                'center': center,
                'radius': float(geometry['$radius'])
            }
    
    # Box format {$box: [[minLng, minLat], [maxLng, maxLat]]}
    if '$box' in geometry:
        box = geometry['$box']
        if isinstance(box, (list, tuple)) and len(box) == 2:
            min_coord = _extract_coordinates(box[0])
            max_coord = _extract_coordinates(box[1])
            if min_coord and max_coord:
                return {
                    'type': 'Box',
                    'min': min_coord,
                    'max': max_coord
                }
    
    return None


def _geometry_contains(geometry: Any, point: Tuple[float, float]) -> bool:
    """Check if a geometry contains a point.
    
    Args:
        geometry: Geometry object (Polygon, Circle, Box, etc.)
        point: (longitude, latitude) to check
    
    Returns:
        True if geometry contains the point
    """
    if not isinstance(geometry, dict):
        return False
    
    geom_type = geometry.get('type')
    
    if geom_type == 'Polygon':
        coords = geometry.get('coordinates', [])
        if coords and isinstance(coords[0], list):
            # Outer ring
            ring = [_extract_coordinates(pt) for pt in coords[0]]
            ring = [c for c in ring if c is not None]
            if ring:
                return _point_in_polygon(point, ring)
    
    elif geom_type == 'Circle':
        center = geometry.get('center')
        radius = geometry.get('radius', 0)
        if center:
            return _point_in_circle(point, center, radius)
    
    elif geom_type == 'Box':
        min_coord = geometry.get('min')
        max_coord = geometry.get('max')
        if min_coord and max_coord:
            return (min_coord[0] <= point[0] <= max_coord[0] and
                    min_coord[1] <= point[1] <= max_coord[1])
    
    elif geom_type == 'Point':
        center = _extract_coordinates(geometry.get('coordinates'))
        if center:
            return center == point
    
    return False


def _geo_intersects(geom1: Any, geom2: Any) -> bool:
    """Check if two geometries intersect.
    
    Args:
        geom1: First geometry
        geom2: Second geometry
    
    Returns:
        True if geometries intersect
    """
    # For now, implement basic point-in-geometry check
    # More complex intersection logic can be added later
    
    # If one is a point, check if it's in the other
    if geom1.get('type') == 'Point':
        point = _extract_coordinates(geom1.get('coordinates'))
        if point:
            return _geometry_contains(geom2, point)
    
    if geom2.get('type') == 'Point':
        point = _extract_coordinates(geom2.get('coordinates'))
        if point:
            return _geometry_contains(geom1, point)
    
    # For polygon-polygon, check if any vertex of one is inside the other
    if geom1.get('type') == 'Polygon' and geom2.get('type') == 'Polygon':
        coords1 = geom1.get('coordinates', [[]])[0]
        for pt in coords1:
            point = _extract_coordinates(pt)
            if point and _geometry_contains(geom2, point):
                return True
        return False
    
    # Default: no intersection detected
    return False


# =============================================================================
# Geohash Encoding/Decoding for Geospatial Indexing
# =============================================================================

_GEOHASH_BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'
_GEOHASH_BIT_MAP = {
    '0': '00000', '1': '00001', '2': '00010', '3': '00011',
    '4': '00100', '5': '00101', '6': '00110', '7': '00111',
    '8': '01000', '9': '01001', 'b': '01010', 'c': '01011',
    'd': '01100', 'e': '01101', 'f': '01110', 'g': '01111',
    'h': '10000', 'j': '10001', 'k': '10010', 'm': '10011',
    'n': '10100', 'p': '10101', 'q': '10110', 'r': '10111',
    's': '11000', 't': '11001', 'u': '11010', 'v': '11011',
    'w': '11100', 'x': '11101', 'y': '11110', 'z': '11111'
}


def _encode_geohash(lon: float, lat: float, precision: int = 12) -> str:
    """Encode longitude/latitude to Geohash string.
    
    Geohash is a hierarchical spatial data structure which subdivides space
    into buckets of grid shape. It provides a short string representation
    of a geographic location.
    
    Args:
        lon: Longitude in degrees (-180 to 180)
        lat: Latitude in degrees (-90 to 90)
        precision: Length of geohash string (default 12, ~37mm precision)
    
    Returns:
        Geohash string
    
    Examples:
        _encode_geohash(116.4074, 39.9042)  # Beijing -> "wx4g0ec1"
        _encode_geohash(121.4737, 31.2304)  # Shanghai -> "wtw37y7c"
    """
    lat_range = (-90.0, 90.0)
    lon_range = (-180.0, 180.0)
    
    geohash = []
    bits = 0
    bit_count = 0
    is_lon = True  # Interleave lon and lat bits
    
    while len(geohash) < precision:
        if is_lon:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                bits = (bits << 1) | 1
                lon_range = (mid, lon_range[1])
            else:
                bits = bits << 1
                lon_range = (lon_range[0], mid)
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                bits = (bits << 1) | 1
                lat_range = (mid, lat_range[1])
            else:
                bits = bits << 1
                lat_range = (lat_range[0], mid)
        
        is_lon = not is_lon
        bit_count += 1
        
        if bit_count == 5:
            geohash.append(_GEOHASH_BASE32[bits])
            bits = 0
            bit_count = 0
    
    return ''.join(geohash)


def _decode_geohash(geohash: str) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Decode Geohash string to bounding box.
    
    Args:
        geohash: Geohash string
    
    Returns:
        Tuple of ((min_lon, min_lat), (max_lon, max_lat))
    """
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    is_lon = True
    
    for char in geohash:
        if char not in _GEOHASH_BIT_MAP:
            continue
        
        bin_str = _GEOHASH_BIT_MAP[char]
        for bit in bin_str:
            if is_lon:
                mid = (lon_range[0] + lon_range[1]) / 2
                if bit == '1':
                    lon_range[0] = mid
                else:
                    lon_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if bit == '1':
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
            is_lon = not is_lon
    
    return ((lon_range[0], lat_range[0]), (lon_range[1], lat_range[1]))


def _geohash_neighbors(geohash: str) -> List[str]:
    """Get the 8 neighboring geohashes at the same precision.
    
    Args:
        geohash: Geohash string
    
    Returns:
        List of 8 neighboring geohash strings
    """
    # Direction mappings for geohash neighbors
    # This is a simplified implementation
    neighbors = []
    precision = len(geohash)
    
    if precision == 0:
        return neighbors
    
    # Get the bounding box of the current geohash
    bbox = _decode_geohash(geohash)
    center_lon = (bbox[0][0] + bbox[1][0]) / 2
    center_lat = (bbox[0][1] + bbox[1][1]) / 2
    
    # Estimate the size of one cell
    lon_delta = (bbox[1][0] - bbox[0][0]) * 1.5
    lat_delta = (bbox[1][1] - bbox[0][1]) * 1.5
    
    # Generate neighbors in 8 directions
    directions = [
        (-1, 0), (1, 0), (0, -1), (0, 1),  # N, S, W, E
        (-1, -1), (-1, 1), (1, -1), (1, 1)  # NW, NE, SW, SE
    ]
    
    for dlon, dlat in directions:
        new_lon = center_lon + dlon * lon_delta
        new_lat = center_lat + dlat * lat_delta
        
        # Clamp to valid ranges
        new_lon = max(-180, min(180, new_lon))
        new_lat = max(-90, min(90, new_lat))
        
        neighbor = _encode_geohash(new_lon, new_lat, precision)
        if neighbor != geohash:
            neighbors.append(neighbor)
    
    return neighbors


def _geohash_in_range(geohash: str, min_lon: float, min_lat: float, 
                       max_lon: float, max_lat: float) -> bool:
    """Check if a geohash's bounding box overlaps with a query range.
    
    Args:
        geohash: Geohash to check
        min_lon, min_lat: Minimum coordinates of query range
        max_lon, max_lat: Maximum coordinates of query range
    
    Returns:
        True if geohash overlaps with query range
    """
    bbox = _decode_geohash(geohash)
    
    # Check for overlap
    return not (bbox[1][0] < min_lon or bbox[0][0] > max_lon or
                bbox[1][1] < min_lat or bbox[0][1] > max_lat)


class QueryCache:
    """LRU cache for query results.
    
    Provides automatic cache invalidation and size management.
    Cache keys are generated from filter hashes for consistent lookup.
    """
    
    def __init__(self, max_size: int = 100):
        """Initialize cache with maximum size.
        
        Args:
            max_size: Maximum number of cached query results (default: 100)
        """
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def _serialize_for_hash(self, obj: Any) -> Any:
        """Convert object to hashable representation.
        
        Handles callable keys, nested dicts/lists, and special types.
        
        Args:
            obj: Object to serialize
        
        Returns:
            Hashable representation
        """
        if callable(obj):
            # For callable keys, use function name and id for uniqueness
            return f"<callable:{obj.__name__}:{id(obj)}>"
        elif isinstance(obj, dict):
            # Sort keys and recursively serialize values
            return {k if not callable(k) else f"<callable:{k.__name__}:{id(k)}>": self._serialize_for_hash(v) 
                    for k, v in sorted(obj.items(), key=lambda x: str(x[0]))}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize_for_hash(item) for item in obj]
        elif isinstance(obj, (datetime, Decimal)):
            return str(obj)
        else:
            return obj
    
    def _hash_filter(self, filter: Dict) -> str:
        """Generate consistent hash for a filter dict.
        
        Args:
            filter: Query filter dict
        
        Returns:
            Hex string hash of the filter
        """
        # Convert to hashable representation (handles callable keys)
        serializable = self._serialize_for_hash(filter)
        filter_str = _fast_dumps(serializable, sort_keys=True, default=str)
        return hashlib.md5(filter_str.encode()).hexdigest()
    
    def get(self, filter: Dict) -> Optional[List[Dict]]:
        """Get cached query result.
        
        Args:
            filter: Query filter dict
        
        Returns:
            Cached results or None if not found
        """
        key = self._hash_filter(filter)
        if key in self._cache:
            self._hits += 1
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return deepcopy(self._cache[key])
        self._misses += 1
        return None
    
    def set(self, filter: Dict, results: List[Dict]) -> None:
        """Cache query results.
        
        Args:
            filter: Query filter dict
            results: Query results to cache
        """
        key = self._hash_filter(filter)
        # Remove old entry if exists (to update position)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        self._cache[key] = deepcopy(results)
    
    def invalidate(self, filter: Optional[Dict] = None) -> None:
        """Invalidate cache entries.
        
        Args:
            filter: If provided, invalidate only matching query.
                   If None, clear entire cache.
        """
        if filter is None:
            self._cache.clear()
        else:
            key = self._hash_filter(filter)
            if key in self._cache:
                del self._cache[key]
    
    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
    
    @property
    def stats(self) -> Dict:
        """Get cache statistics.
        
        Returns:
            Dict with hits, misses, size, and hit_rate
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            'hits': self._hits,
            'misses': self._misses,
            'size': len(self._cache),
            'max_size': self._max_size,
            'hit_rate': round(hit_rate, 2)
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0


@dataclass
class InsertOneResult:
    inserted_id: int


@dataclass
class InsertManyResult:
    inserted_ids: list[int]


@dataclass
class UpdateResult:
    matched_count: int
    modified_count: int
    upserted_id: Optional[Any] = None


@dataclass
class DeleteResult:
    deleted_count: int


class Cursor:
    """Chainable cursor for query operations (sort, limit, skip, projection)."""
    
    def __init__(self, data: List[Dict], db_instance: 'JSONlite'):
        self._data = deepcopy(data)
        self._db = db_instance
        self._sort_keys: List[tuple] = []  # [(key, direction), ...]
        self._skip_count: int = 0
        self._limit_count: Optional[int] = None
        self._projection: Optional[Dict] = None
    
    def sort(self, key: Union[str, List[tuple]], direction: int = 1) -> 'Cursor':
        """Sort results by field(s).
        
        Args:
            key: Field name (str) or list of (field, direction) tuples
            direction: 1 for ASC, -1 for DESC (ignored if key is list)
        
        Returns:
            Self for chaining
        """
        if isinstance(key, list):
            self._sort_keys = key
        else:
            self._sort_keys.append((key, direction))
        return self
    
    def skip(self, count: int) -> 'Cursor':
        """Skip N documents.
        
        Args:
            count: Number of documents to skip
        
        Returns:
            Self for chaining
        """
        self._skip_count = count
        return self
    
    def limit(self, count: int) -> 'Cursor':
        """Limit results to N documents.
        
        Args:
            count: Maximum number of documents to return
        
        Returns:
            Self for chaining
        """
        self._limit_count = count
        return self
    
    def projection(self, fields: Dict) -> 'Cursor':
        """Select/exclude fields.
        
        Args:
            fields: Dict of {field: 1} to include or {field: 0} to exclude
        
        Returns:
            Self for chaining
        """
        self._projection = fields
        return self
    
    def near(self, field: str, point: Union[List[float], Tuple[float, float]], 
             max_distance: Optional[float] = None, min_distance: float = 0) -> 'Cursor':
        """Sort results by geospatial distance from a point.
        
        Args:
            field: Field name containing location data
            point: [longitude, latitude] reference point
            max_distance: Maximum distance in meters (optional)
            min_distance: Minimum distance in meters (default: 0)
        
        Returns:
            Self for chaining
        
        Examples:
            # Find restaurants near a point, sorted by distance
            db.find({"type": "restaurant"}).near("location", [116.4, 39.9]).limit(10).all()
            
            # Find within 1km radius
            db.find({}).near("location", [116.4, 39.9], max_distance=1000).all()
        """
        point_coords = _extract_coordinates(point)
        if not point_coords:
            return self
        
        # Calculate distances and filter by max/min distance
        filtered_data = []
        for record in self._data:
            record_point = _extract_coordinates(record.get(field))
            if record_point:
                distance = _haversine_distance(point_coords, record_point)
                if min_distance <= distance <= (max_distance if max_distance is not None else float('inf')):
                    # Store distance for sorting
                    record['_geo_distance_' + field] = distance
                    filtered_data.append(record)
        
        self._data = filtered_data
        
        # Sort by distance (ascending - nearest first)
        self._sort_keys = [('_geo_distance_' + field, 1)]
        
        return self
    
    def _apply_sort(self) -> 'Cursor':
        """Apply sorting to internal data."""
        if not self._sort_keys:
            return self
        
        def sort_key(record):
            values = []
            for key, direction in self._sort_keys:
                val = record.get(key)
                # Handle None values (sort them last)
                if val is None:
                    val = (1, None)  # Sort None last
                else:
                    val = (0, val)
                # Reverse for DESC
                if direction == -1:
                    if isinstance(val[1], (int, float, str)):
                        val = (val[0], self._negate(val[1]))
                    else:
                        val = (val[0], val[1])
                values.append(val)
            return tuple(values)
        
        self._data.sort(key=sort_key)
        return self
    
    def _negate(self, val):
        """Negate value for DESC sorting."""
        if isinstance(val, (int, float)):
            return -val
        elif isinstance(val, str):
            # For strings, we can't simply negate, so we use a different approach
            # This is a workaround - in production, use locale-aware sorting
            return val
        return val
    
    def _apply_skip_limit(self) -> 'Cursor':
        """Apply skip and limit to internal data."""
        start = self._skip_count
        end = start + self._limit_count if self._limit_count else None
        self._data = self._data[start:end]
        return self
    
    def _apply_projection(self) -> 'Cursor':
        """Apply field projection to internal data."""
        if not self._projection:
            return self
        
        # Determine if we're including or excluding fields
        include_mode = None
        fields_to_include = set()
        fields_to_exclude = set()
        
        for field, mode in self._projection.items():
            if field == '_id':
                continue  # Handle _id separately
            if mode in [1, True]:
                include_mode = True
                fields_to_include.add(field)
            elif mode in [0, False]:
                include_mode = False
                fields_to_exclude.add(field)
        
        new_data = []
        for record in self._data:
            new_record = {}
            if include_mode is True:
                # Include mode: only include specified fields (+ _id by default)
                if self._projection.get('_id', 1) != 0:
                    if '_id' in record:
                        new_record['_id'] = record['_id']
                for field in fields_to_include:
                    if field in record:
                        new_record[field] = record[field]
            else:
                # Exclude mode: include all except specified fields
                for key, value in record.items():
                    if key not in fields_to_exclude:
                        new_record[key] = value
                if self._projection.get('_id', 1) == 0:
                    new_record.pop('_id', None)
            new_data.append(new_record)
        
        self._data = new_data
        return self
    
    def _execute(self) -> List[Dict]:
        """Execute all pending operations and return results."""
        self._apply_sort()._apply_skip_limit()._apply_projection()
        return self._data
    
    def all(self) -> List[Dict]:
        """Return all matching documents after applying operations."""
        return self._execute()
    
    def first(self) -> Optional[Dict]:
        """Return first matching document after applying operations."""
        results = self._execute()
        return results[0] if results else None
    
    def count(self) -> int:
        """Return count of matching documents (before skip/limit)."""
        return len(self._data)
    
    def __iter__(self):
        """Allow iteration over results."""
        return iter(self._execute())
    
    def __len__(self):
        """Return length of results."""
        return len(self._execute())
    
    def __getitem__(self, index):
        """Support indexing."""
        results = self._execute()
        return results[index]


class AggregationCursor:
    """Cursor for aggregation pipeline operations."""
    
    def __init__(self, data: List[Dict], db_instance: 'JSONlite'):
        self._data = deepcopy(data)
        self._db = db_instance
        self._stages: List[Dict] = []
        self._result: Optional[List[Dict]] = None
    
    def _match(self, filter: Dict) -> 'AggregationCursor':
        """$match stage: filter documents."""
        filtered = [doc for doc in self._data if self._db._match_filter(filter, doc)]
        self._data = filtered
        return self
    
    def _group(self, group_spec: Dict) -> 'AggregationCursor':
        """$group stage: group documents by field."""
        _id_expr = group_spec.get('_id')
        
        # Handle simple field grouping (_id: "$field")
        if isinstance(_id_expr, str) and _id_expr.startswith('$'):
            group_field = _id_expr[1:]
            groups = {}
            for doc in self._data:
                key = doc.get(group_field)
                if key not in groups:
                    groups[key] = []
                groups[key].append(doc)
            
            result = []
            for key, docs in groups.items():
                grouped_doc = {'_id': key}
                # Process accumulators
                for field, expr in group_spec.items():
                    if field == '_id':
                        continue
                    if isinstance(expr, dict):
                        for op, val in expr.items():
                            if op == '$sum':
                                if isinstance(val, str) and val.startswith('$'):
                                    grouped_doc[field] = sum(d.get(val[1:], 0) for d in docs if isinstance(d.get(val[1:]), (int, float)))
                                else:
                                    grouped_doc[field] = sum(val for d in docs)
                            elif op == '$avg':
                                if isinstance(val, str) and val.startswith('$'):
                                    vals = [d.get(val[1:]) for d in docs if isinstance(d.get(val[1:]), (int, float))]
                                    grouped_doc[field] = sum(vals) / len(vals) if vals else 0
                            elif op == '$count':
                                grouped_doc[field] = len(docs)
                            elif op == '$min':
                                if isinstance(val, str) and val.startswith('$'):
                                    vals = [d.get(val[1:]) for d in docs if d.get(val[1:]) is not None]
                                    grouped_doc[field] = min(vals) if vals else None
                            elif op == '$max':
                                if isinstance(val, str) and val.startswith('$'):
                                    vals = [d.get(val[1:]) for d in docs if d.get(val[1:]) is not None]
                                    grouped_doc[field] = max(vals) if vals else None
                            elif op == '$first':
                                grouped_doc[field] = docs[0].get(val[1:]) if val.startswith('$') else val
                            elif op == '$last':
                                grouped_doc[field] = docs[-1].get(val[1:]) if val.startswith('$') else val
                            elif op == '$push':
                                if isinstance(val, str) and val.startswith('$'):
                                    grouped_doc[field] = [d.get(val[1:]) for d in docs]
                                else:
                                    grouped_doc[field] = [val] * len(docs)
                result.append(grouped_doc)
            self._data = result
        else:
            # Handle literal _id (all docs in one group)
            self._data = [{'_id': _id_expr, 'count': len(self._data)}]
        return self
    
    def _project(self, projection: Dict) -> 'AggregationCursor':
        """$project stage: reshape documents."""
        new_data = []
        
        # Determine if we're in include or exclude mode
        exclude_fields = set()
        include_fields = {}
        exclude_mode = None
        
        for field, expr in projection.items():
            if field == '_id':
                if expr == 0:
                    exclude_fields.add('_id')
                continue
            
            if expr in [0, False]:
                exclude_mode = True
                exclude_fields.add(field)
            elif expr in [1, True]:
                if exclude_mode is None:
                    exclude_mode = False
                include_fields[field] = None
            elif isinstance(expr, str) and expr.startswith('$'):
                if exclude_mode is None:
                    exclude_mode = False
                include_fields[field] = expr[1:]  # Store source field
            elif isinstance(expr, dict):
                if exclude_mode is None:
                    exclude_mode = False
                include_fields[field] = expr  # Store expression
        
        for doc in self._data:
            new_doc = {}
            
            if exclude_mode:
                # Exclude mode: copy all fields except excluded ones
                for key, value in doc.items():
                    if key not in exclude_fields:
                        new_doc[key] = value
            else:
                # Include mode: only include specified fields
                # Always include _id unless explicitly excluded
                if '_id' not in exclude_fields and '_id' in doc:
                    new_doc['_id'] = doc['_id']
                
                for field, source in include_fields.items():
                    if isinstance(source, str):
                        # Field reference
                        if source in doc:
                            new_doc[field] = doc[source]
                    elif isinstance(source, dict):
                        # Expression
                        new_doc[field] = self._eval_expr(source, doc)
                    else:
                        # Simple include
                        if field in doc:
                            new_doc[field] = doc[field]
            
            new_data.append(new_doc)
        self._data = new_data
        return self
    
    def _eval_expr(self, expr: Dict, doc: Dict) -> Any:
        """Evaluate an expression against a document."""
        for op, val in expr.items():
            if op == '$concat':
                parts = []
                for item in val:
                    if isinstance(item, str) and item.startswith('$'):
                        parts.append(str(doc.get(item[1:], '')))
                    else:
                        parts.append(str(item))
                return ''.join(parts)
            elif op == '$add':
                total = 0
                for item in val:
                    if isinstance(item, str) and item.startswith('$'):
                        total += doc.get(item[1:], 0)
                    else:
                        total += item
                return total
            elif op == '$subtract':
                result = val[0]
                for item in val[1:]:
                    if isinstance(item, str) and item.startswith('$'):
                        result -= doc.get(item[1:], 0)
                    else:
                        result -= item
                return result
            elif op == '$multiply':
                result = 1
                for item in val:
                    if isinstance(item, str) and item.startswith('$'):
                        result *= doc.get(item[1:], 1)
                    else:
                        result *= item
                return result
            elif op == '$divide':
                if len(val) >= 2:
                    a = doc.get(val[0][1:], 0) if isinstance(val[0], str) and val[0].startswith('$') else val[0]
                    b = doc.get(val[1][1:], 1) if isinstance(val[1], str) and val[1].startswith('$') else val[1]
                    return a / b if b != 0 else None
            elif op == '$size':
                if isinstance(val, str) and val.startswith('$'):
                    arr = doc.get(val[1:], [])
                    return len(arr) if isinstance(arr, list) else 0
            elif op == '$literal':
                return val
            elif op == '$cond':
                # {$cond: {if: ..., then: ..., else: ...}}
                if isinstance(val, dict):
                    condition = val.get('if')
                    then_val = val.get('then')
                    else_val = val.get('else')
                    if isinstance(then_val, str) and then_val.startswith('$'):
                        then_val = doc.get(then_val[1:])
                    if isinstance(else_val, str) and else_val.startswith('$'):
                        else_val = doc.get(else_val[1:])
                    return then_val if condition else else_val
        return None
    
    def _sort(self, sort_spec: Dict) -> 'AggregationCursor':
        """$sort stage: sort documents."""
        sort_keys = []
        for field, direction in sort_spec.items():
            sort_keys.append((field, direction if direction in [1, -1] else 1))
        
        def sort_key(record):
            values = []
            for key, direction in sort_keys:
                val = record.get(key)
                if val is None:
                    val = (1, None)
                else:
                    val = (0, val)
                if direction == -1 and isinstance(val[1], (int, float)):
                    val = (val[0], -val[1])
                values.append(val)
            return tuple(values)
        
        self._data.sort(key=sort_key)
        return self
    
    def _skip(self, count: int) -> 'AggregationCursor':
        """$skip stage: skip N documents."""
        self._data = self._data[count:]
        return self
    
    def _limit(self, count: int) -> 'AggregationCursor':
        """$limit stage: limit to N documents."""
        self._data = self._data[:count]
        return self
    
    def _count(self, field_name: str = 'count') -> 'AggregationCursor':
        """$count stage: count documents."""
        self._data = [{field_name: len(self._data)}]
        return self
    
    def _unwind(self, path: Union[str, Dict]) -> 'AggregationCursor':
        """$unwind stage: deconstruct array field."""
        if isinstance(path, dict):
            field_path = path.get('path')
            preserve_nulls = path.get('preserveNullAndEmptyArrays', False)
        else:
            field_path = path
            preserve_nulls = False
        
        # Remove leading $ if present
        if isinstance(field_path, str) and field_path.startswith('$'):
            field_path = field_path[1:]
        
        new_data = []
        for doc in self._data:
            arr = _get_nested_value(doc, field_path)
            if isinstance(arr, list) and len(arr) > 0:
                for item in arr:
                    new_doc = deepcopy(doc)
                    _set_nested_value(new_doc, field_path, item)
                    new_data.append(new_doc)
            elif preserve_nulls:
                new_data.append(deepcopy(doc))
        
        self._data = new_data
        return self
    
    def aggregate(self, pipeline: List[Dict]) -> 'AggregationCursor':
        """Execute aggregation pipeline stages."""
        for stage in pipeline:
            for op, spec in stage.items():
                if op == '$match':
                    self._match(spec)
                elif op == '$group':
                    self._group(spec)
                elif op == '$project':
                    self._project(spec)
                elif op == '$sort':
                    self._sort(spec)
                elif op == '$skip':
                    self._skip(spec)
                elif op == '$limit':
                    self._limit(spec)
                elif op == '$count':
                    self._count(spec if isinstance(spec, str) else 'count')
                elif op == '$unwind':
                    self._unwind(spec)
        return self
    
    def all(self) -> List[Dict]:
        """Return all results."""
        return self._data
    
    def first(self) -> Optional[Dict]:
        """Return first result."""
        return self._data[0] if self._data else None
    
    def count(self) -> int:
        """Return count of results."""
        return len(self._data)
    
    def __iter__(self):
        """Allow iteration over results."""
        return iter(self._data)
    
    def __len__(self):
        """Return length of results."""
        return len(self._data)
    
    def __getitem__(self, index):
        """Support indexing."""
        return self._data[index]


class IndexManager:
    """Manages indexes for JSONlite database.
    
    Supports:
    - Single-field indexes
    - Compound indexes (multi-field)
    - Unique indexes
    - Sparse indexes (only index documents with the field)
    - Automatic index maintenance on insert/update/delete
    """
    
    def __init__(self):
        self._indexes: Dict[str, Dict] = {}  # index_name -> {keys, unique, sparse, data}
    
    def create_index(self, keys: Union[str, List[Tuple[str, int]]], 
                     unique: bool = False, 
                     sparse: bool = False,
                     name: Optional[str] = None) -> str:
        """Create an index on specified field(s).
        
        Args:
            keys: Field name (str) or list of (field, direction) tuples
            unique: If True, enforce uniqueness
            sparse: If True, only index documents with the field
            name: Optional index name (auto-generated if not provided)
        
        Returns:
            Index name
        
        Examples:
            create_index("age")  # Single field
            create_index([("age", 1), ("name", -1)])  # Compound index
            create_index("email", unique=True)  # Unique index
            create_index("optional_field", sparse=True)  # Sparse index
        """
        # Normalize keys to list of tuples
        if isinstance(keys, str):
            keys_list = [(keys, 1)]
        else:
            keys_list = keys
        
        # Generate index name if not provided
        if name is None:
            name_parts = []
            for field, direction in keys_list:
                name_parts.append(f"{field}_{direction}")
            name = "_".join(name_parts)
        
        if name in self._indexes:
            raise ValueError(f"Index '{name}' already exists")
        
        self._indexes[name] = {
            'keys': keys_list,
            'unique': unique,
            'sparse': sparse,
            'data': {}  # value -> list of _id
        }
        
        return name
    
    def drop_index(self, name: str) -> bool:
        """Drop an index by name.
        
        Args:
            name: Index name to drop
        
        Returns:
            True if index was dropped, False if it didn't exist
        """
        if name in self._indexes:
            del self._indexes[name]
            return True
        return False
    
    def drop_all_indexes(self) -> int:
        """Drop all indexes.
        
        Returns:
            Number of indexes dropped
        """
        count = len(self._indexes)
        self._indexes.clear()
        return count
    
    def list_indexes(self) -> List[Dict]:
        """List all indexes.
        
        Returns:
            List of index info dicts
        """
        result = []
        for name, info in self._indexes.items():
            if info.get('type') == 'geospatial':
                result.append({
                    'name': name,
                    'type': 'geospatial',
                    'field': info['field'],
                    'precision': info['precision']
                })
            else:
                result.append({
                    'name': name,
                    'keys': info['keys'],
                    'unique': info['unique'],
                    'sparse': info['sparse']
                })
        return result
    
    def get_index(self, name: str) -> Optional[Dict]:
        """Get index info by name.
        
        Args:
            name: Index name
        
        Returns:
            Index info dict or None if not found
        """
        if name in self._indexes:
            info = self._indexes[name]
            return {
                'name': name,
                'keys': info['keys'],
                'unique': info['unique'],
                'sparse': info['sparse']
            }
        return None
    
    def _get_key_value(self, doc: Dict, keys: List[Tuple[str, int]]) -> Optional[Tuple]:
        """Extract index key value from document.
        
        Args:
            doc: Document to extract key from
            keys: List of (field, direction) tuples
        
        Returns:
            Tuple of values or None if any field is missing (for sparse indexes)
        """
        values = []
        for field, direction in keys:
            value = _get_nested_value(doc, field)
            if value is None:
                return None  # Missing field, skip for sparse index
            values.append(value)
        return tuple(values) if len(values) > 1 else values[0]
    
    def add_document(self, doc: Dict) -> None:
        """Add a document to all indexes.
        
        Args:
            doc: Document to index
        """
        doc_id = doc.get('_id')
        if doc_id is None:
            return
        
        for name, info in self._indexes.items():
            # Handle geospatial indexes
            if info.get('type') == 'geospatial':
                self._index_geospatial_document(info, doc, doc_id, add=True)
                continue
            
            # Handle regular indexes
            if info['sparse']:
                key_value = self._get_key_value(doc, info['keys'])
                if key_value is None:
                    continue  # Skip sparse index for missing field
            else:
                key_value = self._get_key_value(doc, info['keys'])
                if key_value is None:
                    key_value = None  # Include None values for non-sparse
            
            if key_value not in info['data']:
                info['data'][key_value] = []
            
            # Check uniqueness
            if info['unique'] and doc_id not in info['data'][key_value]:
                if len(info['data'][key_value]) > 0:
                    raise ValueError(f"Duplicate key error for index '{name}': {key_value}")
            
            if doc_id not in info['data'][key_value]:
                info['data'][key_value].append(doc_id)
    
    def remove_document(self, doc: Dict) -> None:
        """Remove a document from all indexes.
        
        Args:
            doc: Document to remove
        """
        doc_id = doc.get('_id')
        if doc_id is None:
            return
        
        for name, info in self._indexes.items():
            # Handle geospatial indexes
            if info.get('type') == 'geospatial':
                self._index_geospatial_document(info, doc, doc_id, add=False)
                continue
            
            # Handle regular indexes
            key_value = self._get_key_value(doc, info['keys'])
            if key_value in info['data']:
                if doc_id in info['data'][key_value]:
                    info['data'][key_value].remove(doc_id)
                if len(info['data'][key_value]) == 0:
                    del info['data'][key_value]
    
    def update_document(self, old_doc: Dict, new_doc: Dict) -> None:
        """Update a document in all indexes.
        
        Args:
            old_doc: Document before update
            new_doc: Document after update
        """
        doc_id = new_doc.get('_id')
        
        for name, info in self._indexes.items():
            # Handle geospatial indexes
            if info.get('type') == 'geospatial':
                # Remove old location, add new location
                self._index_geospatial_document(info, old_doc, doc_id, add=False)
                self._index_geospatial_document(info, new_doc, doc_id, add=True)
                continue
            
            # Handle regular indexes
            old_key = self._get_key_value(old_doc, info['keys'])
            new_key = self._get_key_value(new_doc, info['keys'])
            
            if old_key == new_key:
                continue  # Index key unchanged
            
            # Remove from old position
            if old_key is not None and old_key in info['data']:
                if doc_id in info['data'][old_key]:
                    info['data'][old_key].remove(doc_id)
                if len(info['data'][old_key]) == 0:
                    del info['data'][old_key]
            
            # Add to new position
            if new_key is not None or not info['sparse']:
                if new_key not in info['data']:
                    info['data'][new_key] = []
                
                if info['unique'] and len(info['data'][new_key]) > 0:
                    raise ValueError(f"Duplicate key error for index '{name}': {new_key}")
                
                if doc_id not in info['data'][new_key]:
                    info['data'][new_key].append(doc_id)
    
    def query_index(self, field: str, value: Any) -> Optional[List[int]]:
        """Query an index for documents matching a field value.
        
        Args:
            field: Field name to query
            value: Value to match
        
        Returns:
            List of document _ids or None if no suitable index exists
        """
        # Find a suitable index
        for name, info in self._indexes.items():
            if len(info['keys']) == 1 and info['keys'][0][0] == field:
                if value in info['data']:
                    return info['data'][value].copy()
                return []  # Empty list means no matches
        return None  # No suitable index
    
    def query_index_range(self, field: str, 
                          min_value: Any = None, 
                          max_value: Any = None,
                          min_inclusive: bool = True,
                          max_inclusive: bool = True) -> Optional[List[int]]:
        """Query an index for documents in a value range.
        
        Args:
            field: Field name to query
            min_value: Minimum value (None for no lower bound)
            max_value: Maximum value (None for no upper bound)
            min_inclusive: If True, include min_value
            max_inclusive: If True, include max_value
        
        Returns:
            List of document _ids or None if no suitable index exists
        """
        # Find a suitable index
        for name, info in self._indexes.items():
            if len(info['keys']) == 1 and info['keys'][0][0] == field:
                result = []
                sorted_keys = sorted(info['data'].keys())
                
                for key in sorted_keys:
                    if key is None:
                        continue
                    
                    # Check min bound
                    if min_value is not None:
                        if min_inclusive and key < min_value:
                            continue
                        if not min_inclusive and key <= min_value:
                            continue
                    
                    # Check max bound
                    if max_value is not None:
                        if max_inclusive and key > max_value:
                            break
                        if not max_inclusive and key >= max_value:
                            break
                    
                    result.extend(info['data'][key])
                
                return result
        
        return None  # No suitable index
    
    def create_geospatial_index(self, field: str, name: Optional[str] = None,
                                 precision: int = 12) -> str:
        """Create a geospatial index using Geohash encoding.
        
        Geospatial indexes enable efficient location-based queries like
        $near, $geoWithin, and $geoIntersects by encoding coordinates into
        Geohash strings for indexed lookup.
        
        Args:
            field: Field name containing location data (e.g., "location")
            name: Optional index name (auto-generated if not provided)
            precision: Geohash precision (default 12, ~37mm accuracy)
        
        Returns:
            Index name
        
        Examples:
            create_geospatial_index("location")  # Index location field
            create_geospatial_index("loc", precision=8)  # Lower precision (~38m)
        """
        if name is None:
            name = f"{field}_geohash"
        
        if name in self._indexes:
            raise ValueError(f"Index '{name}' already exists")
        
        self._indexes[name] = {
            'type': 'geospatial',
            'field': field,
            'precision': precision,
            'data': {}  # geohash -> list of _id
        }
        
        return name
    
    def _index_geospatial_document(self, index_info: Dict, doc: Dict, 
                                    doc_id: Any, add: bool = True) -> None:
        """Index a document's location in a geospatial index.
        
        Args:
            index_info: Index configuration dict
            doc: Document to index
            doc_id: Document _id
            add: If True, add to index; if False, remove from index
        """
        field = index_info['field']
        precision = index_info['precision']
        data = index_info['data']
        
        location = _get_nested_value(doc, field)
        if location is None:
            return
        
        coords = _extract_coordinates(location)
        if coords is None:
            return
        
        lon, lat = coords
        geohash = _encode_geohash(lon, lat, precision)
        
        if geohash not in data:
            data[geohash] = []
        
        if add:
            if doc_id not in data[geohash]:
                data[geohash].append(doc_id)
        else:
            if doc_id in data[geohash]:
                data[geohash].remove(doc_id)
            if len(data[geohash]) == 0:
                del data[geohash]
    
    def query_geospatial_near(self, field: str, lon: float, lat: float,
                               max_distance: Optional[float] = None,
                               min_distance: Optional[float] = None,
                               limit: int = 100) -> List[Tuple[Any, float]]:
        """Query documents near a location using geospatial index.
        
        Args:
            field: Field name containing location data
            lon: Longitude of query point
            lat: Latitude of query point
            max_distance: Maximum distance in meters (optional)
            min_distance: Minimum distance in meters (optional)
            limit: Maximum number of results to return
        
        Returns:
            List of (doc_id, distance) tuples sorted by distance
        """
        # Find geospatial index for this field
        index_name = f"{field}_geohash"
        if index_name not in self._indexes:
            return []
        
        index_info = self._indexes[index_name]
        precision = index_info['precision']
        
        # Encode query point
        query_geohash = _encode_geohash(lon, lat, precision)
        
        # Collect candidate document IDs from query geohash and neighbors
        candidate_ids = set()
        geohashes_to_check = [query_geohash] + _geohash_neighbors(query_geohash)
        
        for gh in geohashes_to_check:
            if gh in index_info['data']:
                candidate_ids.update(index_info['data'][gh])
        
        # Calculate distances and filter
        results = []
        for doc_id in candidate_ids:
            # We need to get the actual location from the document
            # For now, return empty - the actual query will filter
            # This is a hint for the query optimizer
            results.append(doc_id)
        
        return results[:limit]
    
    def query_geospatial_within(self, field: str, geometry: Dict) -> List[Any]:
        """Query documents within a geometry using geospatial index.
        
        Args:
            field: Field name containing location data
            geometry: Geometry definition (Box, Circle, or Polygon)
        
        Returns:
            List of document IDs within the geometry
        """
        # Find geospatial index for this field
        index_name = f"{field}_geohash"
        if index_name not in self._indexes:
            return []
        
        index_info = self._indexes[index_name]
        precision = index_info['precision']
        
        # Determine bounding box from geometry
        geom_type = geometry.get('type')
        min_lon, min_lat, max_lon, max_lat = -180, -90, 180, 90
        
        if geom_type == 'Box':
            min_coord = geometry.get('min', (-180, -90))
            max_coord = geometry.get('max', (180, 90))
            min_lon, min_lat = min_coord
            max_lon, max_lat = max_coord
        
        elif geom_type == 'Circle':
            center = geometry.get('center', (0, 0))
            radius = geometry.get('radius', 0)
            # Approximate bounding box (rough estimate)
            deg_radius = radius / 111000  # ~111km per degree
            min_lon = max(-180, center[0] - deg_radius)
            max_lon = min(180, center[0] + deg_radius)
            min_lat = max(-90, center[1] - deg_radius)
            max_lat = min(90, center[1] + deg_radius)
        
        elif geom_type == 'Polygon':
            coords = geometry.get('coordinates', [[]])[0]
            for pt in coords:
                c = _extract_coordinates(pt)
                if c:
                    min_lon = min(min_lon, c[0])
                    max_lon = max(max_lon, c[0])
                    min_lat = min(min_lat, c[1])
                    max_lat = max(max_lat, c[1])
        
        # Collect candidate geohashes that overlap with bounding box
        candidate_ids = set()
        
        # For efficiency, we could use a smarter approach, but for now
        # iterate through all indexed geohashes
        for geohash, doc_ids in index_info['data'].items():
            if _geohash_in_range(geohash, min_lon, min_lat, max_lon, max_lat):
                candidate_ids.update(doc_ids)
        
        return list(candidate_ids)
    
    def rebuild_index(self, name: str, documents: List[Dict]) -> None:
        """Rebuild an index from scratch.
        
        Args:
            name: Index name to rebuild
            documents: All documents in the collection
        """
        if name not in self._indexes:
            raise ValueError(f"Index '{name}' does not exist")
        
        info = self._indexes[name]
        info['data'] = {}
        
        for doc in documents:
            try:
                self.add_document(doc)
            except ValueError:
                # Re-raise with context
                raise


def _get_nested_value(doc: Dict, path: str) -> Any:
    """Get value from nested document using dot notation."""
    parts = path.split('.')
    current = doc
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_value(doc: Dict, path: str, value: Any) -> None:
    """Set value in nested document using dot notation."""
    parts = path.split('.')
    current = doc
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _delete_nested_value(doc: Dict, path: str) -> bool:
    """Delete value from nested document using dot notation. Returns True if deleted."""
    parts = path.split('.')
    current = doc
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    if parts[-1] in current:
        del current[parts[-1]]
        return True
    return False


def _apply_update_operators(record: Dict, update_values: Dict) -> Dict:
    """Apply MongoDB-style update operators to a record.
    
    Supported operators:
    - $set: Set field values
    - $unset: Remove fields
    - $inc: Increment/decrement numeric fields
    - $rename: Rename fields
    - $max: Update if new value is greater
    - $min: Update if new value is smaller
    - $push: Add element to array
    - $pull: Remove elements from array
    - $addToSet: Add unique element to array
    - $pop: Remove first/last element from array
    - $pullAll: Remove multiple elements from array
    
    Args:
        record: The document to update
        update_values: Dict of operators and their values
    
    Returns:
        Updated record
    """
    new_record = deepcopy(record)
    
    # $set - Set field values
    if '$set' in update_values:
        for field, value in update_values['$set'].items():
            _set_nested_value(new_record, field, value)
    
    # $unset - Remove fields
    if '$unset' in update_values:
        for field in update_values['$unset']:
            _delete_nested_value(new_record, field)
    
    # $inc - Increment/decrement
    if '$inc' in update_values:
        for field, delta in update_values['$inc'].items():
            current = _get_nested_value(new_record, field)
            if current is None:
                current = 0
            if isinstance(current, (int, float, Decimal)) and isinstance(delta, (int, float, Decimal)):
                _set_nested_value(new_record, field, current + delta)
    
    # $rename - Rename fields
    if '$rename' in update_values:
        for old_field, new_field in update_values['$rename'].items():
            value = _get_nested_value(new_record, old_field)
            if value is not None:
                _delete_nested_value(new_record, old_field)
                _set_nested_value(new_record, new_field, value)
    
    # $max - Update if new value is greater
    if '$max' in update_values:
        for field, value in update_values['$max'].items():
            current = _get_nested_value(new_record, field)
            if current is None or (isinstance(current, (int, float, Decimal)) and value > current):
                _set_nested_value(new_record, field, value)
    
    # $min - Update if new value is smaller
    if '$min' in update_values:
        for field, value in update_values['$min'].items():
            current = _get_nested_value(new_record, field)
            if current is None or (isinstance(current, (int, float, Decimal)) and value < current):
                _set_nested_value(new_record, field, value)
    
    # $push - Add element to array
    if '$push' in update_values:
        for field, value in update_values['$push'].items():
            current = _get_nested_value(new_record, field)
            if current is None:
                current = []
            if isinstance(current, list):
                current.append(value)
                _set_nested_value(new_record, field, current)
    
    # $pull - Remove elements from array matching condition
    if '$pull' in update_values:
        for field, condition in update_values['$pull'].items():
            current = _get_nested_value(new_record, field)
            if isinstance(current, list):
                # Support both simple value and operator conditions
                if isinstance(condition, dict):
                    # Operator condition (e.g., {$gt: 5})
                    filtered = [
                        item for item in current
                        if not _matches_pull_condition(item, condition)
                    ]
                else:
                    # Simple value match
                    filtered = [item for item in current if item != condition]
                _set_nested_value(new_record, field, filtered)
    
    # $addToSet - Add unique element to array
    if '$addToSet' in update_values:
        for field, value in update_values['$addToSet'].items():
            current = _get_nested_value(new_record, field)
            if current is None:
                current = []
            if isinstance(current, list):
                # Check if value already exists (handle dict comparison)
                exists = any(_deep_equals(item, value) for item in current)
                if not exists:
                    current.append(value)
                    _set_nested_value(new_record, field, current)
    
    # $pop - Remove first or last element from array
    if '$pop' in update_values:
        for field, direction in update_values['$pop'].items():
            current = _get_nested_value(new_record, field)
            if isinstance(current, list) and len(current) > 0:
                if direction == 1 or direction == -1:
                    # 1 = remove last, -1 = remove first
                    if direction == 1:
                        current.pop()
                    else:
                        current.pop(0)
                    _set_nested_value(new_record, field, current)
    
    # $pullAll - Remove multiple elements from array
    if '$pullAll' in update_values:
        for field, values in update_values['$pullAll'].items():
            current = _get_nested_value(new_record, field)
            if isinstance(current, list) and isinstance(values, list):
                filtered = [item for item in current if item not in values]
                _set_nested_value(new_record, field, filtered)
    
    return new_record


def _matches_pull_condition(item: Any, condition: Dict) -> bool:
    """Check if an item matches a pull condition (operator dict).
    
    Args:
        item: The array element to check
        condition: Dict of operators (e.g., {'$gt': 5})
    
    Returns:
        True if item matches the condition
    """
    for op, cond_value in condition.items():
        if op == '$eq':
            if item != cond_value:
                return False
        elif op == '$gt':
            if not (item is not None and item > cond_value):
                return False
        elif op == '$gte':
            if not (item is not None and item >= cond_value):
                return False
        elif op == '$lt':
            if not (item is not None and item < cond_value):
                return False
        elif op == '$lte':
            if not (item is not None and item <= cond_value):
                return False
        elif op == '$in':
            if item not in cond_value:
                return False
        elif op == '$ne':
            if item == cond_value:
                return False
    return True


def _deep_equals(a: Any, b: Any) -> bool:
    """Deep equality check for dicts, lists, and primitives.
    
    Args:
        a: First value
        b: Second value
    
    Returns:
        True if values are deeply equal
    """
    if type(a) != type(b):
        return False
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_deep_equals(a[k], b[k]) for k in a.keys())
    elif isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_deep_equals(ai, bi) for ai, bi in zip(a, b))
    else:
        return a == b


class JSONlite:
    def __init__(self, filename: str, cache_enabled: bool = True, cache_size: int = 100):
        """Initialize JSONlite database.
        
        Args:
            filename: Path to the JSON database file
            cache_enabled: Enable query result caching (default: True)
            cache_size: Maximum cached queries (default: 100)
        """
        self._filename = filename
        self._cache_enabled = cache_enabled
        self._cache = QueryCache(max_size=cache_size) if cache_enabled else None
        self.operators = {
            '$gt': lambda v, c: v is not None and v > c,
            '$lt': lambda v, c: v is not None and v < c,
            '$gte': lambda v, c: v is not None and v >= c,
            '$lte': lambda v, c: v is not None and v <= c,
            '$eq': lambda v, c: v == c,
            '$regex': lambda v, c, o=None: re.search(c, v) is not None,
            '$in': lambda v, c: v in c,
            '$all': lambda v, c: isinstance(v, (list, tuple)) and all(item in v for item in c),
            # Geospatial operators
            '$geoWithin': lambda v, c: _geometry_contains(_extract_geometry(c), _extract_coordinates(v)) if _extract_coordinates(v) and _extract_geometry(c) else False,
            '$geoIntersects': lambda v, c: _geo_intersects({'type': 'Point', 'coordinates': _extract_coordinates(v)}, _extract_geometry(c)) if _extract_coordinates(v) and _extract_geometry(c) else False,
        }
        self._index_manager = IndexManager()
        self._index_metadata = []
        self._transaction_manager = TransactionManager(self)
        if not os.path.exists(filename):
            self._touch_database()
        else:
            # Reload to get index metadata
            with open(filename, 'r', encoding='utf-8') as file:
                self._load_database(file)
            # Rebuild indexes from metadata
            self._rebuild_indexes_from_metadata()

    def _default_serializer(self, obj):
        if isinstance(obj, datetime):
            return {'_type': 'datetime', 'value': obj.isoformat()}
        elif isinstance(obj, Decimal):
            return {'_type': 'decimal', 'value': str(obj)}
        elif isinstance(obj, bytes):
            return {'_type': 'binary', 'value': base64.b64encode(obj).decode('utf-8')}
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

    def _object_hook(self, dct):
        if '_type' in dct:
            if dct['_type'] == 'datetime':
                return datetime.fromisoformat(dct['value'])
            elif dct['_type'] == 'decimal':
                return Decimal(dct['value'])
            elif dct['_type'] == 'binary':
                return base64.b64decode(dct['value'])
        return dct

    def _load_database(self, file):
        file.seek(0)
        if not file.read(1):  # init database if file is empty
            self._database = {"data": [], "_indexes": []}
        else:
            file.seek(0)
            content = file.read()
            # orjson doesn't support object_hook, so use standard json for loading
            # to preserve datetime/binary deserialization
            self._database = json.loads(content, object_hook=self._object_hook)
        self._data = self._database["data"]
        # Load index metadata (but rebuild from data)
        self._index_metadata = self._database.get("_indexes", [])

    def _save_database(self, file):
        # Save index metadata
        self._database["_indexes"] = self._index_manager.list_indexes()
        json.dump(self._database, file, ensure_ascii=False, indent=4, default=self._default_serializer)
        file.flush()
        os.fsync(file.fileno())

    def _synchronized_write(method):
        @wraps(method)
        def wrapper(instance, *args, **kwargs):
            filename = instance._filename
            in_transaction = instance._transaction_manager.is_active()
            
            while True:
                with open(filename, 'a'), open(filename, 'r+', encoding='utf-8') as file:
                    fcntl.flock(file, fcntl.LOCK_EX)
                    try:
                        with open(filename, 'a'), open(filename, 'r+', encoding='utf-8') as file2:
                            inode_before = os.fstat(file.fileno()).st_ino
                            inode_after = os.fstat(file2.fileno()).st_ino
                            if inode_before == inode_after:
                                # Only reload from disk if not in a transaction
                                if not in_transaction:
                                    instance._load_database(file)
                                    instance._rebuild_indexes_from_metadata()
                                result = method(instance, *args, **kwargs)
                                # Only save to disk if not in a transaction
                                if not in_transaction:
                                    with tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(filename), mode='w',
                                                                     encoding='utf-8') as temp_file:
                                        instance._save_database(temp_file)
                                    os.rename(temp_file.name, filename)
                                return result
                    finally:
                        fcntl.flock(file, fcntl.LOCK_UN)
        return wrapper

    def _synchronized_read(method):
        @wraps(method)
        def wrapper(instance, *args, **kwargs):
            # No need to lock cause it's read-only, and writes are atomic with
            # os.rename
            # Don't reload from disk if we're in a transaction (use in-memory state)
            if not instance._transaction_manager.is_active():
                filename = instance._filename
                with open(filename, 'r', encoding='utf-8') as file:
                    instance._load_database(file)
                    instance._rebuild_indexes_from_metadata()
            return method(instance, *args, **kwargs)
        return wrapper

    @_synchronized_write
    def _touch_database(self):
        pass

    def _generate_id(self) -> int:
        ids = [item["_id"] for item in self._data if "_id" in item]
        next_id = max(ids) + 1 if ids else 1
        return next_id

    def _match_filter(self, filter: Dict, record: Dict, deep: int = 0) -> bool:
        # fuck regex
        # convert {"$regex": "a", "$options": "i"} to {new_regex_op: "a"}
        if "$regex" in filter and "$options" in filter:
            options = filter.pop("$options")

            def new_regex_op( v, c): 
                return self.operators["$regex"](
                v, c, options)
            filter[new_regex_op] = filter.pop("$regex")
        
        for key, condition in filter.items():
            # Handle $near with optional $maxDistance/$minDistance
            # Format: {field: {$near: [lng, lat], $maxDistance: 1000, $minDistance: 100}}
            if isinstance(condition, dict) and '$near' in condition:
                near_point = _extract_coordinates(condition['$near'])
                if near_point:
                    record_point = _extract_coordinates(record.get(key))
                    if record_point:
                        distance = _haversine_distance(near_point, record_point)
                        max_dist = condition.get('$maxDistance')
                        min_dist = condition.get('$minDistance', 0)
                        
                        # Check distance constraints
                        if max_dist is not None and distance > max_dist:
                            return False
                        if distance < min_dist:
                            return False
                        
                        # Store distance for sorting (attach to record temporarily)
                        record['_geo_distance_' + key] = distance
                    else:
                        return False
                else:
                    return False
                # Continue to next key after handling $near
                continue
            
            if key == '$or':
                if not any(self._match_filter(sub_filter, record, deep + 1)
                           for sub_filter in condition):
                    return False
            elif key == '$and':
                if not all(self._match_filter(sub_filter, record, deep + 1)
                           for sub_filter in condition):
                    return False
            elif key == '$nor':
                if any(self._match_filter(sub_filter, record, deep + 1)
                       for sub_filter in condition):
                    return False
            elif key == '$not':
                if self._match_filter(condition, record, deep + 1):
                    return False
            # Skip splitting for $near conditions (already handled above)
            elif isinstance(condition, dict) and '$near' in condition:
                # $near already processed, continue
                continue
            elif isinstance(condition, dict) and len(condition) > 1:
                if not all(self._match_filter(
                        {key: {k: v}}, record, deep + 1) for k, v in condition.items()):
                    return False
            else:
                # {key: {operator: cond_value} } cond_value MUST NOT be dict
                # {key: cond_value}
                if isinstance(condition, dict):
                    assert len(condition) == 1
                    (operator, cond_value), = condition.items()
                    function = None
                    if operator == "$ne":
                        if self._match_filter(
                                {key: {"$eq": cond_value}}, record, deep + 1):
                            return False
                    elif operator == "$exists":
                        if bool(cond_value) != (key in record):
                            return False
                    elif operator == "$not":
                        if self._match_filter(
                                {key: cond_value}, record, deep + 1):
                            return False
                    elif operator in self.operators:
                        function = self.operators[operator]
                    elif callable(operator):
                        function = operator
                    else:
                        raise ValueError('Unknown operator: %s' % operator)
                    if function:
                        if key not in record:
                            return False
                        if isinstance(cond_value, (list, tuple)):
                            if operator in ['$in', '$all']:
                                if not function(record.get(key), cond_value):
                                    return False
                            else:
                                if not function(record.get(key), *cond_value):
                                    return False
                        else:
                            if not function(record.get(key), cond_value):
                                return False
                else:
                    if key not in record or record[key] != condition:
                        return False
        return True

    def _raw_insert_one(self, record: Dict) -> int:
        if "_id" in record:
            raise ValueError(
                "ID should not be specified. It is auto-generated.")
        record = record.copy()
        record["_id"] = self._generate_id()
        self._data.append(record)
        return record["_id"]

    @_synchronized_write
    def _insert_one(self, record: Dict) -> int:
        # Invalidate cache on write
        if self._cache_enabled and self._cache:
            self._cache.clear()
        return self._raw_insert_one(record)
    def insert_one(self, record: Dict) -> InsertOneResult:
        return InsertOneResult(inserted_id=self._insert_one(record))

    @_synchronized_write
    def _insert_many(self, records: List[Dict]) -> List[int]:
        """Internal batch insert - single read/write cycle for all records."""
        # Invalidate cache on write
        if self._cache_enabled and self._cache:
            self._cache.clear()
        inserted_ids = []
        for record in records:
            if "_id" in record:
                raise ValueError("ID should not be specified. It is auto-generated.")
            record = record.copy()
            record["_id"] = self._generate_id()
            self._data.append(record)
            inserted_ids.append(record["_id"])
        return inserted_ids
    
    def insert_many(self, records: List[Dict]) -> InsertManyResult:
        """Insert multiple records in a single batch operation.
        
        Optimized to perform only one file read/write cycle regardless of
        the number of records, significantly improving batch insert performance.
        
        Args:
            records: List of documents to insert
        
        Returns:
            InsertManyResult with list of inserted IDs
        
        Example:
            >>> result = db.insert_many([{'name': 'Alice'}, {'name': 'Bob'}])
            >>> print(result.inserted_ids)
            [1, 2]
        """
        if not records:
            return InsertManyResult(inserted_ids=[])
        return InsertManyResult(inserted_ids=self._insert_many(records))

    @_synchronized_write
    def _update(self, filter: Dict, update_values: Dict,
                update_all: bool = False, upsert: bool = False) -> UpdateResult:
        # Invalidate cache on write
        if self._cache_enabled and self._cache:
            self._cache.clear()
        
        matched_count = 0
        modified_count = 0
        
        # Check if update_values contains any operators (keys starting with $)
        has_operators = any(key.startswith('$') for key in update_values.keys())
        
        for idx, record in enumerate(self._data):
            if self._match_filter(filter, record):
                matched_count += 1
                if has_operators:
                    # Apply update operators
                    new_record = _apply_update_operators(record, update_values)
                else:
                    # Full document replacement (preserve _id)
                    new_record = update_values.copy()
                    new_record['_id'] = record.get('_id')
                if record != new_record:
                    modified_count += 1
                    self._data[idx] = new_record
                if not update_all:
                    break
        if matched_count == 0 and upsert:
            upserted_record = filter.copy()
            if has_operators:
                upserted_record = _apply_update_operators(upserted_record, update_values)
            else:
                upserted_record.update(update_values)
            upserted_id = self._raw_insert_one(upserted_record)
            return UpdateResult(matched_count=0, modified_count=0, upserted_id=upserted_id)
        return UpdateResult(
            matched_count=matched_count,
            modified_count=modified_count)
    def update_one(self, filter: Dict, update_values: Dict, upsert: bool = False) -> UpdateResult:
        return self._update(filter, update_values, update_all=False, upsert=upsert)

    def update_many(self, filter: Dict, update_values: Dict, upsert: bool = False) -> UpdateResult:
        return self._update(filter, update_values, update_all=True, upsert=upsert)
    
    def replace_one(self, filter: Dict, replacement: Dict, upsert: bool = False) -> UpdateResult:
        return self._update(filter, replacement, update_all=False, upsert=upsert)

    @_synchronized_read
    def _find(self, filter: Dict, find_all: bool = False) -> List[Dict]:
        # Try cache first (only for find_all queries)
        if self._cache_enabled and find_all and self._cache:
            cached = self._cache.get(filter)
            if cached is not None:
                return cached
        
        if filter == {}:
            # fastpath
            result = self._data if find_all else self._data[:1]
            # Cache the result for empty filter queries
            if self._cache_enabled and find_all and self._cache:
                self._cache.set(filter, result)
            return result
        
        found_records = []
        for record in self._data:
            if self._match_filter(filter, record):
                found_records.append(record)
                if not find_all:
                    break
        
        # Cache the result
        if self._cache_enabled and find_all and self._cache:
            self._cache.set(filter, found_records)
        
        return found_records

    def find_one(self, filter: Dict = {}) -> Union[Dict, None]:
        records = self._find(filter, find_all=False)
        return records[0] if records else None

    def find(self, filter: Dict = {}) -> Union[Cursor, List[Dict]]:
        """Find documents with optional chainable operations.
        
        Returns a Cursor for chainable operations (sort, limit, skip, projection).
        Call .all() on the cursor to get results as a list.
        
        Examples:
            # Chainable API
            db.find({"age": {"$gt": 18}}).sort("age", -1).limit(10).all()
            
            # Backward compatible - returns list directly
            db.find({"age": {"$gt": 18}})  # Returns list for backward compat
        """
        results = self._find(filter, find_all=True)
        return Cursor(results, self)

    @_synchronized_read
    def aggregate(self, pipeline: List[Dict]) -> AggregationCursor:
        """Execute an aggregation pipeline.
        
        Args:
            pipeline: List of aggregation stages ($match, $group, $project, $sort, $skip, $limit, $count, $unwind)
        
        Returns:
            AggregationCursor with results
        
        Examples:
            # Match and sort
            db.aggregate([
                {"$match": {"age": {"$gt": 18}}},
                {"$sort": {"age": -1}},
                {"$limit": 10}
            ]).all()
            
            # Group by field
            db.aggregate([
                {"$group": {"_id": "$category", "count": {"$count": {}}, "avgPrice": {"$avg": "$price"}}}
            ]).all()
            
            # Project fields
            db.aggregate([
                {"$match": {"status": "active"}},
                {"$project": {"name": 1, "email": 1}}
            ]).all()
        """
        results = self._find({}, find_all=True)
        cursor = AggregationCursor(results, self)
        return cursor.aggregate(pipeline)

    @_synchronized_write
    def find_one_and_delete(self, filter: Dict) -> Optional[Dict]:
        for idx, record in enumerate(self._data):
            if self._match_filter(filter, record):
                return self._data.pop(idx)
        return None

    def find_one_and_replace(self, filter: Dict, replacement: Dict) -> Optional[Dict]:
        existing_record = self.find_one(filter)
        if existing_record:
            # TODO should consider transaction here
            # between find and replace
            self.replace_one(filter, replacement)
        return existing_record

    def find_one_and_update(self, filter: Dict, update: Dict) -> Optional[Dict]:
        existing_record = self.find_one(filter)
        if existing_record:
            # TODO should consider transaction here
            # between find and replace
            self.update_one(filter, update)
        return existing_record
    
    @_synchronized_write
    def _delete(self, filter: Dict, delete_all: bool = False) -> DeleteResult:
        # Invalidate cache on write
        if self._cache_enabled and self._cache:
            self._cache.clear()

        deleted_count = 0
        if filter == {} and delete_all:
            # fastpath
            deleted_count = len(self._data)
            self._data.clear()  # _data是一个引用，不能直接_data = []
        else:
            idx = 0
            while idx < len(self._data):
                if self._match_filter(filter, self._data[idx]):
                    del self._data[idx]
                    deleted_count += 1
                    if not delete_all:
                        break
                else:
                    idx += 1
        return DeleteResult(deleted_count=deleted_count)

    def delete_one(self, filter: Dict) -> DeleteResult:
        return self._delete(filter, delete_all=False)

    def delete_many(self, filter: Dict) -> DeleteResult:
        return self._delete(filter, delete_all=True)

    @_synchronized_read
    def count_documents(self, filter: Dict) -> int:
        return len(self._find(filter, find_all=True))

    @_synchronized_read
    def estimated_document_count(self) -> int:
        return len(self._data)

    @_synchronized_read
    def distinct(self, key: str, filter: Optional[Dict] = None) -> List[Any]:
        seen = set()
        distinct_values = []
        for record in self._data:
            if filter is None or self._match_filter(filter, record):
                value = record.get(key)
                if value not in seen:
                    seen.add(value)
                    distinct_values.append(value)
        return distinct_values

    @_synchronized_read
    def full_text_search(self, query: str) -> List[Dict]:
        """Perform a full-text search on the database.
        
        Args:
            query (str): The text to search for.
        
        Returns:
            List[Dict]: A list of documents that contain the query text.
        """
        results = []
        for record in self._data:
            if any(query in str(value) for value in record.values()):
                results.append(record)
        return results
    
    # ==================== Cache Management ====================
    
    def get_cache_stats(self) -> Optional[Dict]:
        """Get query cache statistics.
        
        Returns:
            Dict with hits, misses, size, max_size, and hit_rate.
            None if cache is disabled.
        
        Example:
            >>> stats = db.get_cache_stats()
            >>> print(f"Hit rate: {stats['hit_rate']}%")
        """
        if not self._cache_enabled or not self._cache:
            return None
        return self._cache.stats
    
    def clear_cache(self) -> None:
        """Clear the query cache.
        
        Note: Cache is automatically cleared on write operations.
        """
        if self._cache_enabled and self._cache:
            self._cache.clear()
    
    def reset_cache_stats(self) -> None:
        """Reset cache statistics (hits/misses counters)."""
        if self._cache_enabled and self._cache:
            self._cache.reset_stats()
    
    # ==================== Index Management ====================
    
    @_synchronized_write
    def _create_index_internal(self, keys: Union[str, List[Tuple[str, int]]], 
                               unique: bool, sparse: bool, name: Optional[str]) -> str:
        """Internal index creation (with write lock)."""
        index_name = self._index_manager.create_index(keys, unique, sparse, name)
        self._index_manager.rebuild_index(index_name, self._data)
        return index_name
    
    def create_index(self, keys: Union[str, List[Tuple[str, int]]], 
                     unique: bool = False, 
                     sparse: bool = False,
                     name: Optional[str] = None) -> str:
        """Create an index on specified field(s).
        
        Args:
            keys: Field name (str) or list of (field, direction) tuples
            unique: If True, enforce uniqueness
            sparse: If True, only index documents with the field
            name: Optional index name (auto-generated if not provided)
        
        Returns:
            Index name
        
        Examples:
            db.create_index("age")  # Single field
            db.create_index([("age", 1), ("name", -1)])  # Compound index
            db.create_index("email", unique=True)  # Unique index
        """
        return self._create_index_internal(keys, unique, sparse, name)
    
    def drop_index(self, name: str) -> bool:
        """Drop an index by name.
        
        Args:
            name: Index name to drop
        
        Returns:
            True if index was dropped, False if it didn't exist
        """
        return self._index_manager.drop_index(name)
    
    def drop_indexes(self) -> int:
        """Drop all indexes.
        
        Returns:
            Number of indexes dropped
        """
        return self._index_manager.drop_all_indexes()
    
    def _rebuild_indexes_from_metadata(self) -> None:
        """Rebuild indexes from saved metadata."""
        for idx_meta in self._index_metadata:
            try:
                self._index_manager.create_index(
                    idx_meta['keys'],
                    idx_meta.get('unique', False),
                    idx_meta.get('sparse', False),
                    idx_meta['name']
                )
                self._index_manager.rebuild_index(idx_meta['name'], self._data)
            except Exception:
                # Skip corrupted indexes
                pass
    
    def list_indexes(self) -> List[Dict]:
        """List all indexes.
        
        Returns:
            List of index info dicts with name, keys, unique, sparse
        """
        return self._index_manager.list_indexes()
    
    def create_geospatial_index(self, field: str, name: Optional[str] = None,
                                 precision: int = 12) -> str:
        """Create a geospatial index using Geohash encoding.
        
        Geospatial indexes enable efficient location-based queries like
        $near, $geoWithin, and $geoIntersects by encoding coordinates into
        Geohash strings for indexed lookup.
        
        Args:
            field: Field name containing location data (e.g., "location")
            name: Optional index name (auto-generated if not provided)
            precision: Geohash precision (default 12, ~37mm accuracy)
        
        Returns:
            Index name
        
        Examples:
            db.create_geospatial_index("location")  # Index location field
            db.create_geospatial_index("loc", precision=8)  # Lower precision (~38m)
        """
        index_name = self._index_manager.create_geospatial_index(field, name, precision)
        # Rebuild index with existing data
        self._index_manager.rebuild_index(index_name, self._data)
        return index_name
    
    def _insert_one_with_index(self, record: Dict) -> int:
        """Insert one document and update indexes."""
        # Check if user provided _id (should be auto-generated)
        if '_id' in record:
            raise ValueError("ID should not be specified. It is auto-generated.")
        # Add _id to record before inserting (so we can use it for indexes)
        record_with_id = record.copy()
        record_with_id["_id"] = self._generate_id()
        self._data.append(record_with_id)
        # Add to indexes
        self._index_manager.add_document(record_with_id)
        # Invalidate cache on write
        if self._cache_enabled and self._cache:
            self._cache.clear()
        return record_with_id["_id"]
    
    @_synchronized_write
    def _insert_one(self, record: Dict) -> int:
        return self._insert_one_with_index(record)
    
    @_synchronized_write
    def _update_with_index(self, filter: Dict, update_values: Dict,
                          update_all: bool = False, upsert: bool = False) -> UpdateResult:
        """Update with index maintenance."""
        matched_count = 0
        modified_count = 0
        
        has_operators = any(key.startswith('$') for key in update_values.keys())
        
        for idx, record in enumerate(self._data):
            if self._match_filter(filter, record):
                matched_count += 1
                old_record = deepcopy(record)
                
                if has_operators:
                    new_record = _apply_update_operators(record, update_values)
                else:
                    new_record = update_values.copy()
                    new_record['_id'] = record.get('_id')
                
                if record != new_record:
                    modified_count += 1
                    # Update indexes
                    self._index_manager.update_document(old_record, new_record)
                    self._data[idx] = new_record
                
                if not update_all:
                    break
        
        if matched_count == 0 and upsert:
            upserted_record = filter.copy()
            if has_operators:
                upserted_record = _apply_update_operators(upserted_record, update_values)
            else:
                upserted_record.update(update_values)
            upserted_id = self._insert_one_with_index(upserted_record)
            return UpdateResult(matched_count=0, modified_count=0, upserted_id=upserted_id)
        
        # Invalidate cache on write
        if self._cache_enabled and self._cache:
            self._cache.clear()
        
        return UpdateResult(matched_count=matched_count, modified_count=modified_count)
    
    def update_one(self, filter: Dict, update_values: Dict, upsert: bool = False) -> UpdateResult:
        return self._update_with_index(filter, update_values, update_all=False, upsert=upsert)
    
    def update_many(self, filter: Dict, update_values: Dict, upsert: bool = False) -> UpdateResult:
        return self._update_with_index(filter, update_values, update_all=True, upsert=upsert)
    
    @_synchronized_write
    def _delete_with_index(self, filter: Dict, delete_all: bool = False) -> DeleteResult:
        """Delete with index maintenance."""
        deleted_count = 0
        if filter == {} and delete_all:
            # Remove all from indexes
            for record in self._data:
                self._index_manager.remove_document(record)
            deleted_count = len(self._data)
            self._data.clear()
        else:
            idx = 0
            while idx < len(self._data):
                if self._match_filter(filter, self._data[idx]):
                    # Remove from indexes before deleting
                    self._index_manager.remove_document(self._data[idx])
                    del self._data[idx]
                    deleted_count += 1
                    if not delete_all:
                        break
                else:
                    idx += 1
        # Invalidate cache on write
        if self._cache_enabled and self._cache:
            self._cache.clear()
        return DeleteResult(deleted_count=deleted_count)
    
    def delete_one(self, filter: Dict) -> DeleteResult:
        return self._delete_with_index(filter, delete_all=False)
    
    def delete_many(self, filter: Dict) -> DeleteResult:
        return self._delete_with_index(filter, delete_all=True)
    
    def _find_with_index(self, filter: Dict, find_all: bool = False) -> List[Dict]:
        """Find using indexes when possible for optimization."""
        # Try cache first (only for find_all queries)
        if self._cache_enabled and find_all and self._cache:
            cached = self._cache.get(filter)
            if cached is not None:
                return cached
        
        # Check for geospatial queries and use geospatial index
        geospatial_result = self._try_geospatial_index_query(filter, find_all)
        if geospatial_result is not None:
            return geospatial_result
        
        # Try to use index for simple equality filters
        if len(filter) == 1:
            field, value = list(filter.items())[0]
            if not isinstance(value, dict):  # Simple equality, not operator
                indexed_ids = self._index_manager.query_index(field, value)
                if indexed_ids is not None:
                    # Build id -> record map
                    id_map = {doc['_id']: doc for doc in self._data}
                    results = [id_map[_id] for _id in indexed_ids if _id in id_map]
                    result = results if find_all else results[:1]
                    # Cache the result
                    if self._cache_enabled and find_all and self._cache:
                        self._cache.set(filter, result)
                    return result
        
        # Fall back to full scan
        if filter == {}:
            result = self._data if find_all else self._data[:1]
            # Cache the result for empty filter queries
            if self._cache_enabled and find_all and self._cache:
                self._cache.set(filter, result)
            return result
        
        found_records = []
        for record in self._data:
            if self._match_filter(filter, record):
                found_records.append(record)
                if not find_all:
                    break
        
        # Sort by distance if $near was used
        sorted_results = self._sort_by_near_distance(filter, found_records)
        
        # Cache the result
        if self._cache_enabled and find_all and self._cache:
            self._cache.set(filter, sorted_results)
        
        return sorted_results
    
    def _try_geospatial_index_query(self, filter: Dict, find_all: bool) -> Optional[List[Dict]]:
        """Try to use geospatial index for location-based queries.
        
        Args:
            filter: Query filter
            find_all: Whether to return all matches or just first
        
        Returns:
            List of matching records if geospatial index was used, None otherwise
        """
        # Look for $near or $geoWithin queries
        for field, condition in filter.items():
            if not isinstance(condition, dict):
                continue
            
            # Handle $near query
            if '$near' in condition:
                near_point = _extract_coordinates(condition['$near'])
                if not near_point:
                    continue
                
                lon, lat = near_point
                max_dist = condition.get('$maxDistance')
                min_dist = condition.get('$minDistance', 0)
                
                # Use geospatial index to get candidate IDs
                candidate_ids = self._index_manager.query_geospatial_near(
                    field, lon, lat, max_dist, min_dist
                )
                
                if candidate_ids:
                    # Build id -> record map
                    id_map = {doc['_id']: doc for doc in self._data}
                    results = []
                    
                    for doc_id in candidate_ids:
                        if doc_id in id_map:
                            record = id_map[doc_id]
                            # Verify with exact distance calculation
                            record_point = _extract_coordinates(record.get(field))
                            if record_point:
                                distance = _haversine_distance(near_point, record_point)
                                if min_dist <= distance and (max_dist is None or distance <= max_dist):
                                    record['_geo_distance_' + field] = distance
                                    results.append(record)
                    
                    # Sort by distance
                    results.sort(key=lambda r: r.get('_geo_distance_' + field, float('inf')))
                    
                    if not find_all:
                        return results[:1]
                    
                    return results
            
            # Handle $geoWithin query
            elif '$geoWithin' in condition:
                geometry = _extract_geometry(condition['$geoWithin'])
                if not geometry:
                    continue
                
                # Use geospatial index to get candidate IDs
                candidate_ids = self._index_manager.query_geospatial_within(field, geometry)
                
                if candidate_ids:
                    # Build id -> record map
                    id_map = {doc['_id']: doc for doc in self._data}
                    results = []
                    
                    for doc_id in candidate_ids:
                        if doc_id in id_map:
                            record = id_map[doc_id]
                            # Verify with exact geometry check
                            record_point = _extract_coordinates(record.get(field))
                            if record_point and _geometry_contains(geometry, record_point):
                                results.append(record)
                    
                    if not find_all:
                        return results[:1]
                    
                    return results
            
            # Handle $geoIntersects query
            elif '$geoIntersects' in condition:
                geometry = _extract_geometry(condition['$geoIntersects'])
                if not geometry:
                    continue
                
                # For intersects, we need to check all documents
                # (geospatial index helps less here without R-tree)
                continue
        
        return None  # No geospatial index optimization applicable
    
    def _sort_by_near_distance(self, filter: Dict, records: List[Dict]) -> List[Dict]:
        """Sort records by distance if $near operator was used.
        
        Args:
            filter: Query filter
            records: Matched records
        
        Returns:
            Records sorted by distance (if $near was used), otherwise unchanged
        """
        # Check if filter contains $near
        for key, condition in filter.items():
            if isinstance(condition, dict) and '$near' in condition:
                # Sort by the stored distance
                distance_key = '_geo_distance_' + key
                return sorted(records, key=lambda r: r.get(distance_key, float('inf')))
        return records
    
    @_synchronized_read
    def _find(self, filter: Dict, find_all: bool = False) -> List[Dict]:
        return self._find_with_index(filter, find_all)
    
    def _save(self) -> None:
        """Save the database to disk."""
        with open(self._filename, 'w', encoding='utf-8') as file:
            self._save_database(file)
    
    @contextmanager
    def transaction(self):
        """
        Create a transaction context for atomic multi-operation support.
        
        All operations within the context are atomic - either all succeed
        or all are rolled back on error.
        
        Usage:
            with db.transaction() as txn:
                db.insert_one({"name": "Alice", "balance": 1000})
                db.insert_one({"name": "Bob", "balance": 500})
                # If any operation fails, both inserts are rolled back
        
        Raises:
            TransactionError: If nested transactions are attempted
        """
        with self._transaction_manager.transaction() as txn:
            yield txn
    
    def begin_transaction(self) -> 'TransactionContext':
        """
        Explicitly begin a transaction (alternative to context manager).
        
        Must be followed by commit() or rollback().
        
        Usage:
            txn = db.begin_transaction()
            try:
                db.insert_one({...})
                db.update_one({...})
                db.commit_transaction()
            except:
                db.rollback_transaction()
        """
        return self._transaction_manager.begin()
    
    def commit_transaction(self) -> None:
        """Commit the current transaction."""
        self._transaction_manager.commit()
    
    def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        self._transaction_manager.rollback()
    
    def in_transaction(self) -> bool:
        """Check if currently inside a transaction."""
        return self._transaction_manager.is_active()
