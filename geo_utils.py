#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Geographic Utilities Module

This module contains functions for geographic operations, such as bounding box
calculation and boundary tests.
"""

from shapely.geometry import Point, Polygon, LineString, MultiPoint
from shapely.ops import unary_union
import logging

# Set up logging
logger = logging.getLogger(__name__)

def get_bounding_box(coords, padding=0.001):
    """
    Calculate the bounding box with a margin.
    
    Args:
        coords (list): List of (longitude, latitude) coordinates
        padding (float, optional): Padding to add around the bounding box. Defaults to 0.001.
        
    Returns:
        tuple: (min_lon, min_lat, max_lon, max_lat)
        
    Raises:
        ValueError: If coordinates list is empty or invalid
    """
    if not coords:
        raise ValueError("Empty coordinates list")
    
    try:
        min_lon = min(c[0] for c in coords) - padding
        max_lon = max(c[0] for c in coords) + padding
        min_lat = min(c[1] for c in coords) - padding
        max_lat = max(c[1] for c in coords) + padding
        
        logger.info(f"Calculated bounding box: lon({min_lon}, {max_lon}), lat({min_lat}, {max_lat})")
        
        # Validate coordinates are within reasonable ranges
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and
                -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise ValueError(f"Invalid coordinate ranges in bounding box")
        
        return min_lon, min_lat, max_lon, max_lat
    except Exception as e:
        raise ValueError(f"Error calculating bounding box: {str(e)}")

def get_feature_bounding_box(features, padding=0.001):
    """
    Calculate the bounding box for a list of features.
    
    Args:
        features (list): List of feature dictionaries with 'coordinates' key
        padding (float, optional): Padding to add around the bounding box. Defaults to 0.001.
        
    Returns:
        tuple: (min_lon, min_lat, max_lon, max_lat)
        
    Raises:
        ValueError: If features list is empty or invalid
    """
    if not features:
        raise ValueError("Empty features list")
    
    all_coords = []
    
    for feature in features:
        if feature['type'] == 'MultiGeometry':
            # For MultiGeometry, flatten all coordinates
            for geom_coords in feature['coordinates']:
                all_coords.extend(geom_coords)
        else:
            all_coords.extend(feature['coordinates'])
    
    return get_bounding_box(all_coords, padding)

def is_point_in_boundary(point, boundary_coords, buffer=0):
    """
    Check if a point is inside the boundary polygon with optional buffer.
    
    Args:
        point (tuple): (longitude, latitude)
        boundary_coords (list): List of (longitude, latitude) coordinates
        buffer (float, optional): Buffer distance to add around boundary. Defaults to 0.
        
    Returns:
        bool: True if point is inside boundary (with buffer), False otherwise
    """
    if not boundary_coords:
        return True
    try:
        polygon = Polygon(boundary_coords)
        if buffer > 0:
            polygon = polygon.buffer(buffer)
        return polygon.contains(Point(point))
    except Exception as e:
        logger.warning(f"Boundary test failed for point {point}: {e}")
        return True  # If test fails, include the feature rather than exclude it

def is_line_in_boundary(points, boundary_coords, buffer=0.0002):
    """
    Check if a line intersects or is contained within the boundary polygon.
    
    Args:
        points (list): List of (longitude, latitude) coordinates representing a line
        boundary_coords (list): List of (longitude, latitude) coordinates
        buffer (float, optional): Buffer distance to add around boundary. Defaults to 0.0002.
        
    Returns:
        bool: True if line intersects boundary, False otherwise
    """
    if not boundary_coords:
        return True
    try:
        polygon = Polygon(boundary_coords)
        shape = Polygon(points) if len(points) > 2 else LineString(points)
        
        # Add buffer to boundary
        buffered_polygon = polygon.buffer(buffer)
        
        # Check for intersection with buffered boundary
        intersects = buffered_polygon.intersects(shape)
        
        # For debugging certain features
        if logger.isEnabledFor(logging.DEBUG) and any(2.179 <= p[0] <= 2.181 and 48.944 <= p[1] <= 48.946 for p in points):
            logger.debug(f"Boundary test for feature near allotment area:")
            logger.debug(f"- Points: {points[:2]}...")
            logger.debug(f"- Intersects with boundary: {intersects}")
            logger.debug(f"- Shape type: {'Polygon' if len(points) > 2 else 'LineString'}")
            logger.debug(f"- Area overlaps: {buffered_polygon.intersection(shape).area > 0}")
        
        return intersects
        
    except Exception as e:
        logger.warning(f"Boundary test failed: {e}")
        return True  # If test fails, include the feature rather than exclude it

def calculate_feature_area(coords):
    """
    Calculate the area of a feature in square degrees.
    
    Args:
        coords (list): List of (longitude, latitude) coordinates
        
    Returns:
        float: Area of the feature
    """
    try:
        if len(coords) < 3:
            return 0
        
        polygon = Polygon(coords)
        return polygon.area
    except Exception as e:
        logger.warning(f"Area calculation failed: {e}")
        return 0

def calculate_overlap_percentage(feature_coords, boundary_coords):
    """
    Calculate the percentage of a feature that overlaps with the boundary polygon.
    
    Args:
        feature_coords (list): List of (longitude, latitude) coordinates for the feature
        boundary_coords (list): List of (longitude, latitude) coordinates for the boundary
        
    Returns:
        float: Percentage of overlap (0-100)
    """
    if not boundary_coords or not feature_coords or len(feature_coords) < 3:
        return 0
    
    try:
        feature_polygon = Polygon(feature_coords)
        boundary_polygon = Polygon(boundary_coords)
        
        if not feature_polygon.is_valid or not boundary_polygon.is_valid:
            return 0
        
        intersection = feature_polygon.intersection(boundary_polygon)
        
        if intersection.is_empty:
            return 0
        
        return (intersection.area / feature_polygon.area) * 100
    except Exception as e:
        logger.warning(f"Overlap calculation failed: {e}")
        return 0

def distance_to_boundary(point, boundary_coords):
    """
    Calculate the distance from a point to the boundary polygon.
    
    Args:
        point (tuple): (longitude, latitude)
        boundary_coords (list): List of (longitude, latitude) coordinates
        
    Returns:
        float: Distance to boundary in degrees
    """
    if not boundary_coords:
        return float('inf')
    
    try:
        boundary = Polygon(boundary_coords)
        return Point(point).distance(boundary)
    except Exception as e:
        logger.warning(f"Distance calculation failed: {e}")
        return float('inf')

def simplify_boundary(boundary_coords, tolerance=0.0001):
    """
    Simplify boundary polygon to reduce number of points for better performance.
    
    Args:
        boundary_coords (list): List of (longitude, latitude) coordinates
        tolerance (float, optional): Simplification tolerance. Defaults to 0.0001.
        
    Returns:
        list: Simplified list of coordinates
    """
    if not boundary_coords or len(boundary_coords) < 4:
        return boundary_coords
    
    try:
        boundary = Polygon(boundary_coords)
        simplified = boundary.simplify(tolerance, preserve_topology=True)
        
        # Extract coordinates from the simplified polygon
        coords = list(simplified.exterior.coords)
        
        # Remove the last point if it's the same as the first (closed polygon)
        if coords[0] == coords[-1]:
            coords = coords[:-1]
        
        logger.info(f"Simplified boundary from {len(boundary_coords)} to {len(coords)} points")
        return coords
    except Exception as e:
        logger.warning(f"Boundary simplification failed: {e}")
        return boundary_coords
