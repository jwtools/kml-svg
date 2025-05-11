#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Coordinate Transformation Module

This module handles the transformation of geographic coordinates to SVG coordinates.
"""

import math
import logging

# Set up logging
logger = logging.getLogger(__name__)

def lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height, padding=0.05):
    """
    Convert geographic coordinates to SVG coordinates with aspect ratio handling.
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
        bbox (tuple): (min_lon, min_lat, max_lon, max_lat)
        svg_width (int): Width of SVG canvas
        svg_height (int): Height of SVG canvas
        padding (float, optional): Padding percentage for the SVG canvas. Defaults to 0.05 (5%).
        
    Returns:
        tuple: (x, y) SVG coordinates
        
    Raises:
        ValueError: If bounding box dimensions are invalid
    """
    try:
        min_lon, min_lat, max_lon, max_lat = bbox
        
        # Validate coordinates
        if lat is None or lon is None or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            logger.error(f"Invalid coordinates: lat={lat}, lon={lon}")
            return (svg_width/2, svg_height/2)  # Return center of canvas as fallback
        
        # Clamp coordinates to bbox with a small margin
        margin = 0.001
        lat = max(min_lat - margin, min(lat, max_lat + margin))
        lon = max(min_lon - margin, min(lon, max_lon + margin))
        
        # Calculate width/height ratio to maintain proportions
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat
        
        if lon_range <= 0 or lat_range <= 0:
            raise ValueError("Invalid bounding box dimensions: zero or negative range")
        
        # Add padding to prevent features from touching the edges
        effective_width = svg_width * (1 - 2 * padding)
        effective_height = svg_height * (1 - 2 * padding)
        
        # Calculate scales that would preserve the aspect ratio in both directions
        scale_x = effective_width / lon_range
        scale_y = effective_height / lat_range
        
        # Use the smaller scale to ensure the map fits in both dimensions
        scale = min(scale_x, scale_y)
        
        # Calculate centered offsets
        x_offset = (svg_width - (lon_range * scale)) / 2
        y_offset = (svg_height - (lat_range * scale)) / 2
        
        # Transform coordinates
        x = x_offset + (lon - min_lon) * scale
        y = y_offset + (max_lat - lat) * scale  # Invert Y axis
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Transformed coordinates: ({lon}, {lat}) -> ({x}, {y})")
            
        return x, y
    except Exception as e:
        logger.error(f"Coordinate transformation error: {e}")
        return (svg_width/2, svg_height/2)  # Return center of canvas as fallback

def transform_coordinates(coordinates, bbox, svg_width, svg_height, padding=0.05):
    """
    Transform a list of geographic coordinates to SVG coordinates.
    
    Args:
        coordinates (list): List of (longitude, latitude) coordinates
        bbox (tuple): (min_lon, min_lat, max_lon, max_lat)
        svg_width (int): Width of SVG canvas
        svg_height (int): Height of SVG canvas
        padding (float, optional): Padding percentage for the SVG canvas. Defaults to 0.05 (5%).
        
    Returns:
        list: List of (x, y) SVG coordinates
    """
    return [lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height, padding) 
            for lon, lat in coordinates]

def transform_feature(feature, bbox, svg_width, svg_height, padding=0.05):
    """
    Transform a feature's coordinates to SVG coordinates.
    
    Args:
        feature (dict): Feature dictionary with type and coordinates
        bbox (tuple): (min_lon, min_lat, max_lon, max_lat)
        svg_width (int): Width of SVG canvas
        svg_height (int): Height of SVG canvas
        padding (float, optional): Padding percentage for the SVG canvas. Defaults to 0.05 (5%).
        
    Returns:
        dict: Feature with transformed coordinates
    """
    feature_type = feature['type']
    
    if feature_type == 'MultiGeometry':
        # For MultiGeometry, transform each geometry
        svg_coords = []
        for coords in feature['coordinates']:
            svg_coords.append(transform_coordinates(coords, bbox, svg_width, svg_height, padding))
        return {**feature, 'svg_coordinates': svg_coords}
    else:
        # For Point, LineString, Polygon
        svg_coords = transform_coordinates(feature['coordinates'], bbox, svg_width, svg_height, padding)
        return {**feature, 'svg_coordinates': svg_coords}

def calculate_label_corners(x, y, width, height, angle, buffer=5):
    """
    Calculate label corners with buffer.
    
    Args:
        x (float): X coordinate of label center
        y (float): Y coordinate of label center
        width (float): Width of label
        height (float): Height of label
        angle (float): Rotation angle in degrees
        buffer (float, optional): Buffer around the label. Defaults to 5.
        
    Returns:
        list: Four corner points of the buffered label area
    """
    cos_a = math.cos(math.radians(angle))
    sin_a = math.sin(math.radians(angle))
    w2 = (width/2 + buffer)
    h2 = (height/2 + buffer)
    return [
        (x - w2*cos_a + h2*sin_a, y - w2*sin_a - h2*cos_a),
        (x + w2*cos_a + h2*sin_a, y + w2*sin_a - h2*cos_a),
        (x + w2*cos_a - h2*sin_a, y + w2*sin_a + h2*cos_a),
        (x - w2*cos_a - h2*sin_a, y - w2*sin_a + h2*cos_a)
    ]

def project_point_to_line(point, line_start, line_end):
    """
    Project a point onto a line segment, returning the projected point.
    
    Args:
        point (tuple): (x, y) point to project
        line_start (tuple): (x, y) starting point of line
        line_end (tuple): (x, y) ending point of line
        
    Returns:
        tuple: (x, y) projected point on the line
    """
    px, py = point
    ax, ay = line_start
    bx, by = line_end
    apx = px - ax
    apy = py - ay
    abx = bx - ax
    aby = by - ay
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return line_start
    t = max(0, min(1, (apx * abx + apy * aby) / ab2))
    return (ax + t * abx, ay + t * aby)

def calculate_feature_center(coordinates):
    """
    Calculate the center point of a feature.
    
    Args:
        coordinates (list): List of (x, y) coordinates
        
    Returns:
        tuple: (x, y) center point
    """
    if not coordinates:
        return (0, 0)
    
    # For simple calculation, average all points
    x_sum = sum(p[0] for p in coordinates)
    y_sum = sum(p[1] for p in coordinates)
    return (x_sum / len(coordinates), y_sum / len(coordinates))

def kml_color_to_svg(kml_color):
    """
    Convert KML color format (aabbggrr) to SVG format (#rrggbb).
    
    Args:
        kml_color (str): KML color string
        
    Returns:
        tuple: (svg_color, opacity) - SVG color string and opacity value
    """
    if not kml_color or len(kml_color) != 8:
        return ("#000000", 1.0)
    
    try:
        a = int(kml_color[0:2], 16) / 255
        b = kml_color[2:4]
        g = kml_color[4:6]
        r = kml_color[6:8]
        
        svg_color = f"#{r}{g}{b}"
        opacity = a
        
        return (svg_color, opacity)
    except Exception as e:
        logger.warning(f"Color conversion failed: {e}")
        return ("#000000", 1.0)
