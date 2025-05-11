#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Geometry Optimizer Module

This module handles the optimization of complex geometries for improved SVG rendering
performance. It includes functions for simplifying polygons, smoothing lines,
and reducing point density while maintaining visual quality.
"""

import logging
import numpy as np
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
# In Shapely 2.0+, the simplify function is a method of geometries
# so we don't need to import it separately
from shapely.ops import unary_union

# Set up logging
logger = logging.getLogger(__name__)

def simplify_polygon(polygon, tolerance=0.00001, preserve_topology=True):
    """
    Simplify a polygon to reduce the number of vertices.
    
    Args:
        polygon (list): List of (lon, lat) coordinates
        tolerance (float, optional): Simplification tolerance. Higher values = more simplification.
        preserve_topology (bool, optional): Whether to preserve topology during simplification.
        
    Returns:
        list: Simplified list of coordinates
    """
    if len(polygon) < 4:
        return polygon  # Don't simplify if not enough points
        
    try:
        # Convert to shapely Polygon
        shapely_poly = Polygon(polygon)
        
        # Check if polygon is valid
        if not shapely_poly.is_valid:
            # Try to fix invalid polygon
            shapely_poly = shapely_poly.buffer(0)
            if not shapely_poly.is_valid:
                logger.warning("Could not repair invalid polygon")
                return polygon
          # Simplify the polygon - in Shapely 2.0+, simplify is a method of the geometry
        simplified = shapely_poly.simplify(tolerance=tolerance, preserve_topology=preserve_topology)
        
        # Get coordinates
        if isinstance(simplified, Polygon):
            return list(simplified.exterior.coords)
        elif isinstance(simplified, MultiPolygon):
            # Return the largest polygon
            largest = max(simplified.geoms, key=lambda x: x.area)
            return list(largest.exterior.coords)
        else:
            logger.warning(f"Unexpected type after simplification: {type(simplified)}")
            return polygon
    except Exception as e:
        logger.error(f"Error simplifying polygon: {e}")
        return polygon

def simplify_linestring(linestring, tolerance=0.00001, preserve_topology=True):
    """
    Simplify a linestring to reduce the number of vertices.
    
    Args:
        linestring (list): List of (lon, lat) coordinates
        tolerance (float, optional): Simplification tolerance. Higher values = more simplification.
        preserve_topology (bool, optional): Whether to preserve topology during simplification.
        
    Returns:
        list: Simplified list of coordinates
    """
    if len(linestring) < 3:
        return linestring  # Don't simplify if not enough points
        
    try:        # Convert to shapely LineString
        shapely_line = LineString(linestring)
        
        # Simplify the linestring - in Shapely 2.0+, simplify is a method of the geometry
        simplified = shapely_line.simplify(tolerance=tolerance, preserve_topology=preserve_topology)
        
        # Get coordinates
        return list(simplified.coords)
    except Exception as e:
        logger.error(f"Error simplifying linestring: {e}")
        return linestring

def adaptive_simplify(geometry, geometry_type, feature_name=None, target_points=100):
    """
    Adaptively simplify a geometry to target a specific point count.
    
    Args:
        geometry (list): List of (lon, lat) coordinates
        geometry_type (str): Type of geometry ('Polygon', 'LineString', etc.)
        feature_name (str, optional): Name of the feature for logging
        target_points (int, optional): Target number of points after simplification
        
    Returns:
        list: Simplified list of coordinates
    """
    if not geometry:
        return geometry
        
    original_point_count = len(geometry)
    
    # Skip simplification if already under target
    if original_point_count <= target_points:
        return geometry
    
    # Start with a low tolerance and increase as needed
    min_tolerance = 0.000001
    max_tolerance = 0.001
    current_tolerance = min_tolerance
    step_factor = 2.0  # Multiplicative factor for each step
    max_iterations = 10
    
    feature_desc = f"'{feature_name}'" if feature_name else f"{geometry_type}"
    logger.info(f"Adaptive simplification of {feature_desc}: {original_point_count} points -> target {target_points}")
    
    # Iteratively try to reach target point count
    for iteration in range(max_iterations):
        if geometry_type == 'Polygon':
            simplified = simplify_polygon(geometry, current_tolerance)
        elif geometry_type == 'LineString':
            simplified = simplify_linestring(geometry, current_tolerance)
        else:
            # Unsupported geometry type
            return geometry
            
        current_point_count = len(simplified)
        
        # Check if we've reached our target
        if current_point_count <= target_points:
            percent_reduction = (1 - current_point_count / original_point_count) * 100
            logger.info(f"Simplified {feature_desc} from {original_point_count} to {current_point_count} points ({percent_reduction:.1f}% reduction)")
            return simplified
            
        # Increase tolerance
        current_tolerance *= step_factor
        if current_tolerance > max_tolerance:
            # Reached maximum tolerance, return the best we have
            percent_reduction = (1 - current_point_count / original_point_count) * 100
            logger.info(f"Reached max tolerance. Simplified {feature_desc} from {original_point_count} to {current_point_count} points ({percent_reduction:.1f}% reduction)")
            return simplified
    
    # If we've exhausted iterations, return the last result
    return simplified

def optimize_feature(feature, is_large_file=False):
    """
    Optimize a feature for better rendering performance.
    
    Args:
        feature (dict): Feature dictionary
        is_large_file (bool, optional): Whether this is part of a large file (more aggressive optimization)
        
    Returns:
        dict: Optimized feature
    """
    if not feature:
        return feature
        
    feature_type = feature.get('type')
    name = feature.get('name', 'unnamed')
    
    # Target different point counts based on feature type and file size
    target_points = {
        'Polygon': 200 if is_large_file else 400,
        'LineString': 150 if is_large_file else 300,
        'MultiGeometry': 100 if is_large_file else 200  # Per sub-geometry
    }
    
    if feature_type == 'Polygon':
        coords = feature.get('coordinates', [])
        if len(coords) > target_points[feature_type]:
            feature['coordinates'] = adaptive_simplify(coords, 'Polygon', name, target_points[feature_type])
            
    elif feature_type == 'LineString':
        coords = feature.get('coordinates', [])
        if len(coords) > target_points[feature_type]:
            feature['coordinates'] = adaptive_simplify(coords, 'LineString', name, target_points[feature_type])
            
    elif feature_type == 'MultiGeometry':
        multi_coords = feature.get('coordinates', [])
        geom_types = feature.get('geometry_types', [])
        
        if len(multi_coords) == len(geom_types):
            for i, (coords, geom_type) in enumerate(zip(multi_coords, geom_types)):
                if geom_type in ('Polygon', 'LineString') and len(coords) > target_points['MultiGeometry']:
                    multi_coords[i] = adaptive_simplify(coords, geom_type, f"{name}_{i}", target_points['MultiGeometry'])
            
            feature['coordinates'] = multi_coords
    
    return feature
