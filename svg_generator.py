#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SVG Generator Module

This module handles the creation of SVG maps from OSM data and KML features.
"""

import xml.etree.ElementTree as ET
import svgwrite
import math
import logging
import numpy as np
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import linemerge, unary_union

from geo_utils import is_line_in_boundary, get_bounding_box
from svg_styling import get_way_style, get_feature_style
from coord_transform import lat_lon_to_xy, calculate_label_corners, project_point_to_line
from coord_transform import transform_feature, transform_coordinates
from config_parser import load_config

# Set up logging
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()
SVG_CONFIG = config.get('svg', {})

def create_svg_map(osm_data, boundary_coords, output_file, svg_width=None, svg_height=None, 
                   kml_features=None, kml_styles=None, skip_labels=False, debug_bounds=False):
    """
    Create an SVG file of the map.
    
    Args:
        osm_data (bytes): OSM XML data or None if only KML features are used
        boundary_coords (list): List of (longitude, latitude) coordinates for the boundary
        output_file (str): Path to output SVG file
        svg_width (int, optional): Width of SVG canvas. Defaults to config value or 800.
        svg_height (int, optional): Height of SVG canvas. Defaults to config value or 600.
        kml_features (list, optional): List of KML features to render.
        kml_styles (dict, optional): Dictionary of KML style definitions.
        skip_labels (bool, optional): If True, skip rendering text labels.
        debug_bounds (bool, optional): If True, add boundary visualization.
    """
    # Get dimensions from config if not provided
    svg_width = svg_width or SVG_CONFIG.get('width', 800)
    svg_height = svg_height or SVG_CONFIG.get('height', 600)
    
    bbox = get_bounding_box(boundary_coords)
    
    # Initialize SVG with white background
    dwg = svgwrite.Drawing(output_file, (svg_width, svg_height))
    dwg.add(dwg.rect(insert=(0, 0), size=(svg_width, svg_height), fill='white'))
    
    # Create groups for different layers
    background_group = dwg.g(id='background')
    natural_group = dwg.g(id='natural-features')
    landuse_group = dwg.g(id='landuse')
    kml_group = dwg.g(id='kml-features')
    building_group = dwg.g(id='buildings')
    road_group = dwg.g(id='roads')
    path_group = dwg.g(id='paths')
    parking_group = dwg.g(id='parking')
    point_group = dwg.g(id='points')
    text_group = dwg.g(id='text')
    
    # Add background pattern for transparency
    add_background_pattern(dwg, background_group, svg_width, svg_height)
    
    # Initialize set to track added street names
    added_names = set()
    # Track label positions to prevent overlaps
    used_label_areas = []
    
    # Draw boundary if debug mode is on
    if debug_bounds:
        draw_boundary(dwg, background_group, boundary_coords, bbox, svg_width, svg_height)
    
    # Process KML features if available
    if kml_features:
        process_kml_features(dwg, kml_group, kml_features, kml_styles, boundary_coords, bbox, 
                            svg_width, svg_height, text_group, used_label_areas, skip_labels)
    
    # Process OSM data if available
    if osm_data:
        process_osm_data(dwg, osm_data, boundary_coords, bbox, svg_width, svg_height, 
                      natural_group, landuse_group, building_group, road_group, path_group, 
                      parking_group, text_group, added_names, used_label_areas, skip_labels)
    
    # Add groups to SVG in correct order
    dwg.add(background_group)
    dwg.add(natural_group)
    dwg.add(landuse_group)
    dwg.add(kml_group)
    dwg.add(parking_group)
    dwg.add(building_group)
    dwg.add(road_group)
    dwg.add(path_group)
    dwg.add(point_group)
    if not skip_labels:
        dwg.add(text_group)
    
    # Save the SVG file
    dwg.save()
    logger.info(f"SVG map saved to {output_file}")

def add_background_pattern(dwg, group, width, height):
    """Add a subtle background pattern to the map"""
    pattern = dwg.pattern(id='bg_pattern', size=(10, 10), patternUnits="userSpaceOnUse")
    pattern.add(dwg.rect((0, 0), (10, 10), fill='#F8F8F8'))
    pattern.add(dwg.line((0, 0), (10, 10), stroke='#F0F0F0', stroke_width=0.5))
    
    dwg.defs.add(pattern)
    group.add(dwg.rect((0, 0), (width, height), fill='url(#bg_pattern)'))

def draw_boundary(dwg, group, boundary_coords, bbox, svg_width, svg_height):
    """Draw the boundary polygon for debugging"""
    svg_points = transform_coordinates(boundary_coords, bbox, svg_width, svg_height)
    
    # Create boundary path
    poly_path = f'M {svg_points[0][0]},{svg_points[0][1]}'
    for x, y in svg_points[1:]:
        poly_path += f' L {x},{y}'
    poly_path += ' Z'
    
    path = dwg.path(d=poly_path)
    path['fill'] = 'none'
    path['stroke'] = '#FF0000'
    path['stroke-width'] = 2
    path['stroke-dasharray'] = '5,5'
    group.add(path)

def process_kml_features(dwg, kml_group, kml_features, kml_styles, boundary_coords, bbox, 
                        svg_width, svg_height, text_group, used_label_areas, skip_labels):
    """Process and render KML features"""
    logger.info(f"Processing {len(kml_features)} KML features")
    
    # Create subgroups for different feature types
    polygon_group = dwg.g(id='kml-polygons')
    line_group = dwg.g(id='kml-lines')
    point_group = dwg.g(id='kml-points')
    
    # Transform all features to SVG coordinates
    for feature in kml_features:
        transformed_feature = transform_feature(feature, bbox, svg_width, svg_height)
        
        # Get style for the feature
        style = get_feature_style(transformed_feature, kml_styles, True)
        if not style:
            continue
        
        feature_type = transformed_feature['type']
        
        if feature_type == 'Polygon':
            render_polygon(dwg, polygon_group, transformed_feature, style)
            
            # Add label if available and labels aren't skipped
            if not skip_labels and 'name' in transformed_feature and transformed_feature['name']:
                add_feature_label(dwg, text_group, transformed_feature, used_label_areas)
        
        elif feature_type == 'LineString':
            render_linestring(dwg, line_group, transformed_feature, style)
            
            # Add label if available and labels aren't skipped
            if not skip_labels and 'name' in transformed_feature and transformed_feature['name']:
                add_feature_label(dwg, text_group, transformed_feature, used_label_areas)
        
        elif feature_type == 'Point':
            render_point(dwg, point_group, transformed_feature, style)
            
            # Add label if available and labels aren't skipped
            if not skip_labels and 'name' in transformed_feature and transformed_feature['name']:
                add_point_label(dwg, text_group, transformed_feature, used_label_areas)
        
        elif feature_type == 'MultiGeometry':
            render_multigeometry(dwg, polygon_group, line_group, point_group,
                                transformed_feature, style)
            
            # Add label if available and labels aren't skipped
            if not skip_labels and 'name' in transformed_feature and transformed_feature['name']:
                add_feature_label(dwg, text_group, transformed_feature, used_label_areas)
    
    # Add subgroups to main KML group
    kml_group.add(polygon_group)
    kml_group.add(line_group)
    kml_group.add(point_group)

def render_polygon(dwg, group, feature, style):
    """Render a polygon feature"""
    svg_points = feature['svg_coordinates']
    if len(svg_points) < 3:
        return
    
    poly_path = f'M {svg_points[0][0]},{svg_points[0][1]}'
    for x, y in svg_points[1:]:
        poly_path += f' L {x},{y}'
    poly_path += ' Z'
    
    path = dwg.path(d=poly_path)
    path['fill'] = style.get('fill', '#3388FF')
    path['stroke'] = style.get('stroke', '#0066CC')
    path['stroke-width'] = style.get('stroke-width', 1)
    path['fill-opacity'] = style.get('opacity', 0.7)
    path['stroke-opacity'] = style.get('opacity', 0.9)
    
    group.add(path)

def render_linestring(dwg, group, feature, style):
    """Render a linestring feature"""
    svg_points = feature['svg_coordinates']
    if len(svg_points) < 2:
        return
    
    path = dwg.path(d=f'M {svg_points[0][0]},{svg_points[0][1]}')
    for x, y in svg_points[1:]:
        path.push(f'L {x},{y}')
    
    path['stroke'] = style.get('stroke', '#3388FF')
    path['stroke-width'] = style.get('stroke-width', 2)
    path['fill'] = 'none'
    path['stroke-opacity'] = style.get('opacity', 0.9)
    
    group.add(path)

def render_point(dwg, group, feature, style):
    """Render a point feature"""
    if not feature['svg_coordinates']:
        return
    
    x, y = feature['svg_coordinates'][0]
    radius = style.get('radius', 5)
    
    # Check if there's an icon to use
    if 'icon' in style:
        # Add icon if available
        pass
    else:
        # Default to circle
        circle = dwg.circle(center=(x, y), r=radius)
        circle['fill'] = style.get('fill', '#3388FF')
        circle['stroke'] = style.get('stroke', '#FFFFFF')
        circle['stroke-width'] = style.get('stroke-width', 1)
        circle['fill-opacity'] = style.get('opacity', 0.9)
        
        group.add(circle)

def render_multigeometry(dwg, polygon_group, line_group, point_group, feature, style):
    """Render a multigeometry feature"""
    svg_coords_list = feature['svg_coordinates']
    geometry_types = feature.get('geometry_types', [])
    
    if len(svg_coords_list) != len(geometry_types):
        logger.warning(f"Geometry type count mismatch for feature {feature.get('name', 'unnamed')}")
        return
    
    for i, (svg_coords, geom_type) in enumerate(zip(svg_coords_list, geometry_types)):
        if geom_type == 'Polygon':
            sub_feature = {
                'svg_coordinates': svg_coords,
                'type': 'Polygon'
            }
            render_polygon(dwg, polygon_group, sub_feature, style)
        
        elif geom_type == 'LineString':
            sub_feature = {
                'svg_coordinates': svg_coords,
                'type': 'LineString'
            }
            render_linestring(dwg, line_group, sub_feature, style)
        
        elif geom_type == 'Point':
            sub_feature = {
                'svg_coordinates': svg_coords,
                'type': 'Point'
            }
            render_point(dwg, point_group, sub_feature, style)

def add_feature_label(dwg, text_group, feature, used_label_areas):
    """Add a label for a feature at its center"""
    if 'name' not in feature or not feature['name']:
        return
    
    if feature['type'] == 'Point':
        add_point_label(dwg, text_group, feature, used_label_areas)
        return
    
    name = feature['name']
    svg_coords = feature['svg_coordinates']
    
    if not svg_coords or (feature['type'] == 'MultiGeometry' and not svg_coords[0]):
        return
    
    # Calculate center point
    if feature['type'] == 'MultiGeometry':
        # For MultiGeometry, use the first polygon or the longest linestring
        best_coords = []
        for coords in svg_coords:
            if len(coords) > len(best_coords):
                best_coords = coords
        
        if not best_coords:
            return
            
        center_x = sum(p[0] for p in best_coords) / len(best_coords)
        center_y = sum(p[1] for p in best_coords) / len(best_coords)
    else:
        # For normal features
        center_x = sum(p[0] for p in svg_coords) / len(svg_coords)
        center_y = sum(p[1] for p in svg_coords) / len(svg_coords)
      # Add the label if it doesn't collide
    text_width = len(name) * 6
    text_height = 12
    
    has_collision, (label_x, label_y) = check_label_collision(center_x, center_y, text_width, text_height, 0, used_label_areas)
    
    if not has_collision:        
        text = dwg.text(name, insert=(label_x, label_y))
        text['font-family'] = 'Arial, sans-serif'
        text['font-size'] = '12px'
        text['text-anchor'] = 'middle'
        text['dominant-baseline'] = 'middle'
        text['fill'] = '#333333'
        
        # Add background for better readability
        padding = 2
        bg = dwg.rect(
            insert=(label_x - text_width/2 - padding, label_y - text_height/2 - padding),
            size=(text_width + 2*padding, text_height + 2*padding),
            rx=2, ry=2
        )
        bg['fill'] = 'white'
        bg['fill-opacity'] = 0.7
        
        text_group.add(bg)
        text_group.add(text)
        
        # Add to used areas
        corners = calculate_label_corners(label_x, label_y, text_width, text_height, 0)
        used_label_areas.append(Polygon(corners))

def add_point_label(dwg, text_group, feature, used_label_areas):
    """Add a label for a point feature"""
    if 'name' not in feature or not feature['name']:
        return
    
    name = feature['name']
    if not feature['svg_coordinates']:
        return
    
    x, y = feature['svg_coordinates'][0]
    text_width = len(name) * 6
    text_height = 12
    
    # Position label slightly below the point
    label_x = x
    label_y = y + 15
    
    has_collision, (label_x, label_y) = check_label_collision(label_x, label_y, text_width, text_height, 0, used_label_areas)
    
    if not has_collision:
        text = dwg.text(name, insert=(label_x, label_y))
        text['font-family'] = 'Arial, sans-serif'
        text['font-size'] = '12px'
        text['text-anchor'] = 'middle'
        text['fill'] = '#333333'
        
        # Add background for better readability
        padding = 2
        bg = dwg.rect(
            insert=(label_x - text_width/2 - padding, label_y - text_height/2 - padding),
            size=(text_width + 2*padding, text_height + 2*padding),
            rx=2, ry=2
        )
        bg['fill'] = 'white'
        bg['fill-opacity'] = 0.7
        
        text_group.add(bg)
        text_group.add(text)
        
        # Add to used areas
        corners = calculate_label_corners(label_x, label_y, text_width, text_height, 0)
        used_label_areas.append(Polygon(corners))

def check_label_collision(x, y, width, height, angle, used_label_areas, buffer_distance=20):
    """
    Check if a label area collides with existing labels and find alternative positions if needed.
    
    Args:
        x, y (float): Center coordinates of the label
        width, height (float): Dimensions of the label
        angle (float): Rotation angle of the label in degrees
        used_label_areas (list): List of existing label areas as Shapely Polygons
        buffer_distance (float): Extra buffer distance around the label to avoid close placement
    
    Returns:
        tuple: (collision_detected, (suggested_x, suggested_y))
    """
    # Create points for the four corners of the label area with buffer
    corners = calculate_label_corners(x, y, width, height, angle, buffer_distance)
    new_box = Polygon(corners)

    # Define a more comprehensive set of alternative positions to try
    # This spiral pattern tries positions further away from the original point
    spiral_offsets = []
    max_distance = 60  # Maximum distance to try
    steps = 12  # Number of positions to try around each ring
    rings = 3   # Number of distance rings
    
    for ring in range(1, rings+1):
        distance = ring * (max_distance / rings)
        for step in range(steps):
            angle_rad = 2 * np.pi * step / steps
            dx = distance * np.cos(angle_rad)
            dy = distance * np.sin(angle_rad)
            spiral_offsets.append((dx, dy))
    
    # Add cardinal directions at different distances as priority positions
    cardinal_offsets = [
        (0, -30), (0, 30),     # North, South
        (-30, 0), (30, 0),     # West, East
        (0, -45), (0, 45),     # Further North, South
        (-45, 0), (45, 0),     # Further West, East
    ]
    
    # Combine cardinal directions with spiral pattern, prioritizing cardinal
    retry_offsets = cardinal_offsets + spiral_offsets
    
    # Check collision with existing labels
    for existing_area in used_label_areas:
        if new_box.intersects(existing_area):
            # Try alternative positions
            for dx, dy in retry_offsets:
                alt_corners = calculate_label_corners(x + dx, y + dy, width, height, angle, buffer_distance)
                alt_box = Polygon(alt_corners)
                
                # If we found a non-colliding position, return the new coordinates
                if not any(alt_box.intersects(area) for area in used_label_areas):
                    return False, (x + dx, y + dy)
            
            # If all positions have collisions, try to find the position with the least overlap
            min_overlap = float('inf')
            best_pos = (x, y)
            
            for dx, dy in retry_offsets:
                alt_corners = calculate_label_corners(x + dx, y + dy, width, height, angle, buffer_distance/2)
                alt_box = Polygon(alt_corners)
                
                # Calculate total overlap with all existing areas
                total_overlap = sum(alt_box.intersection(area).area for area in used_label_areas)
                
                if total_overlap < min_overlap:
                    min_overlap = total_overlap
                    best_pos = (x + dx, y + dy)
            
            # Return the position with minimal overlap
            return True, best_pos
    
    # No collision with default position
    return False, (x, y)

def process_osm_data(dwg, osm_data, boundary_coords, bbox, svg_width, svg_height, 
                  natural_group, landuse_group, building_group, road_group, path_group, 
                  parking_group, text_group, added_names, used_label_areas, skip_labels):
    """Process and render OSM data"""
    # Parse XML
    root = ET.fromstring(osm_data)
    nodes = {n.attrib['id']: (float(n.attrib['lat']), float(n.attrib['lon'])) 
             for n in root.findall('node')}
    
    # Collection for grouping road segments by name
    roads_by_name = {}
    
    # First pass: collect all roads
    for way in root.findall('way'):
        way_nodes = []
        tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall('tag')}
        road_name = tags.get('name')
        if 'highway' in tags and road_name and not skip_labels:
            # Get coordinates for way
            for nd in way.findall('nd'):
                if nd.attrib['ref'] in nodes:
                    lat, lon = nodes[nd.attrib['ref']]
                    way_nodes.append((lon, lat))
            
            if way_nodes:
                if road_name not in roads_by_name:
                    roads_by_name[road_name] = {'segments': [], 'tags': tags, 'inside_segments': []}
                
                # Check if this segment is inside the boundary
                is_inside = is_line_in_boundary(way_nodes, boundary_coords)
                roads_by_name[road_name]['segments'].append(way_nodes)
                if is_inside:
                    roads_by_name[road_name]['inside_segments'].append(way_nodes)
    
    # Add road labels
    if not skip_labels:
        add_road_labels(dwg, roads_by_name, boundary_coords, bbox, svg_width, svg_height, 
                        text_group, added_names, used_label_areas)
    
    # Process ways for drawing roads and other features
    for way in root.findall('way'):
        way_nodes = []
        tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall('tag')}
        
        for nd in way.findall('nd'):
            if nd.attrib['ref'] in nodes:
                lat, lon = nodes[nd.attrib['ref']]
                way_nodes.append((lon, lat))
        
        if not way_nodes:
            continue
            
        is_inside = is_line_in_boundary(way_nodes, boundary_coords)
        style = get_way_style(tags, is_inside)
        if not style:
            continue
            
        svg_points = []
        for lon, lat in way_nodes:
            x, y = lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height)
            svg_points.append((x, y))
            
        if len(svg_points) < 2:
            continue
            
        if style.get('type') == 'road':
            if style.get('casing'):
                path = dwg.path(d=f'M {svg_points[0][0]},{svg_points[0][1]}')
                for x, y in svg_points[1:]:
                    path.push(f'L {x},{y}')
                path['stroke'] = style.get('casing-color', '#000000')
                path['stroke-width'] = style.get('casing-width', 1)
                path['fill'] = 'none'
                road_group.add(path)
            
            path = dwg.path(d=f'M {svg_points[0][0]},{svg_points[0][1]}')
            for x, y in svg_points[1:]:
                path.push(f'L {x},{y}')
            path['stroke'] = style.get('stroke', '#000000')
            path['stroke-width'] = style.get('stroke-width', 1)
            path['fill'] = 'none'
            path['stroke-opacity'] = style.get('opacity', 1)
            
            if style.get('is_path'):
                path_group.add(path)
            else:
                road_group.add(path)
                
        elif style.get('type') == 'polygon':
            poly_path = f'M {svg_points[0][0]},{svg_points[0][1]}'
            for x, y in svg_points[1:]:
                poly_path += f' L {x},{y}'
            poly_path += ' Z'
            
            path = dwg.path(d=poly_path)
            path['fill'] = style.get('fill', '#000000')
            path['stroke'] = style.get('stroke', 'none')
            path['stroke-width'] = style.get('stroke-width', 1)
            path['fill-opacity'] = style.get('opacity', 1)
            path['stroke-opacity'] = style.get('opacity', 1)
            
            if 'natural' in tags or tags.get('waterway'):
                natural_group.add(path)
            elif 'landuse' in tags or 'leisure' in tags:
                landuse_group.add(path)
            elif 'building' in tags:
                building_group.add(path)
            elif tags.get('amenity') == 'parking':
                parking_group.add(path)
                # Add parking symbol
                center_x = sum(p[0] for p in svg_points) / len(svg_points)
                center_y = sum(p[1] for p in svg_points) / len(svg_points)
                parking_text = dwg.text("P", insert=(center_x, center_y))
                parking_text['font-family'] = 'Arial, sans-serif'
                parking_text['font-size'] = '14px'
                parking_text['text-anchor'] = 'middle'
                parking_text['dominant-baseline'] = 'middle'
                parking_text['font-weight'] = 'bold'
                parking_text['fill'] = '#666666'
                parking_group.add(parking_text)

def add_road_labels(dwg, roads_by_name, boundary_coords, bbox, svg_width, svg_height, 
                    text_group, added_names, used_label_areas):
    """Add labels for roads"""
    from shapely.geometry import Polygon, LineString, MultiLineString, Point
    from shapely.ops import linemerge, unary_union, nearest_points
    
    for road_name, road_data in roads_by_name.items():
        if not road_data['segments']:
            continue
        
        # Merge all segments with the same name
        all_lines = [LineString(seg) for seg in road_data['segments'] if len(seg) > 1]
        if not all_lines:
            continue
            
        # Improved segment merging:
        # 1. First try to merge all segments with the same name into a single geometry
        # 2. For disconnected segments, check if they're close enough to be treated as one road
        merged = linemerge(all_lines)
        
        # If we have multiple non-connected lines, check if they're part of the same road
        # but just have a small gap between them
        if merged.geom_type == 'MultiLineString' and len(list(merged.geoms)) > 1:
            connect_threshold = 0.0005  # Maximum distance to connect segments (in degrees)
            new_lines = list(merged.geoms)
            
            # Sort lines by length (descending) to merge smaller segments into the longest ones first
            new_lines.sort(key=lambda line: line.length, reverse=True)
            
            merged_lines = []
            remaining_lines = new_lines.copy()
            
            # Start with the longest segment
            current_line = remaining_lines.pop(0)
            merged_lines.append(current_line)
            
            # Keep trying to merge until no more merges are possible
            while remaining_lines:
                closest_idx = -1
                min_distance = float('inf')
                
                # Find the closest remaining line to our current line
                for i, line in enumerate(remaining_lines):
                    # Get closest points between the current merged line and this line
                    p1, p2 = nearest_points(current_line, line)
                    dist = p1.distance(p2)
                    
                    if dist < min_distance:
                        min_distance = dist
                        closest_idx = i
                
                # If we found a close enough segment, merge it
                if min_distance < connect_threshold:
                    next_line = remaining_lines.pop(closest_idx)
                    # Create a new merged line
                    current_line = linemerge([current_line, next_line])
                    
                    # If merging didn't work (due to topology), just add as separate line
                    if current_line.geom_type == 'MultiLineString':
                        merged_lines[-1] = list(current_line.geoms)[0]  # Replace with first part
                        merged_lines.extend(list(current_line.geoms)[1:])  # Add other parts
                        
                        # Continue with the longest remaining merged segment
                        current_line = max(merged_lines, key=lambda line: line.length)
                    else:
                        # Replace the last merged line with the new merged line
                        merged_lines[-1] = current_line
                else:
                    # If no close segments, start a new merge group with the longest remaining
                    if remaining_lines:
                        current_line = remaining_lines.pop(0)
                        merged_lines.append(current_line)
            
            # Create a new MultiLineString from our merged segments
            if len(merged_lines) == 1:
                merged = merged_lines[0]
            else:
                merged = MultiLineString(merged_lines)
        
        # Clip to boundary with a buffer to ensure roads that touch the boundary are included
        boundary_poly = Polygon(boundary_coords).buffer(0.0005)  # Add small buffer
        
        if merged.is_empty:
            continue        # Determine if this is a small road or path
        is_small_road = 'highway' in road_data['tags'] and road_data['tags']['highway'] in [
            'footway', 'path', 'pedestrian', 'service', 'track', 'living_street'
        ]
        is_residential = 'highway' in road_data['tags'] and road_data['tags']['highway'] == 'residential'
          # Choose different labeling strategy based on road type and geometry
        if merged.geom_type == 'MultiLineString':
            segments_to_label = []
            
            # Define appropriate length thresholds based on road type
            if is_residential:
                length_threshold = 0.0001  # Lower threshold for residential roads
            elif is_small_road:
                length_threshold = 0.0002  # Small threshold for minor roads
            else:
                length_threshold = 0.0005  # Default threshold for major roads
            
            # Sort segments by length, largest first
            sorted_segments = sorted(merged.geoms, key=lambda line: line.length, reverse=True)
            
            # For roads with multiple segments, try to label each significant segment
            # but avoid too many labels on the same road
            for line in sorted_segments:
                if line.length > length_threshold:
                    clipped = line.intersection(boundary_poly)
                    if not clipped.is_empty and clipped.length > 0:
                        segments_to_label.append(clipped)
            
            # Limit the number of segments to label based on road type
            if not is_residential and not is_small_road:
                # For major roads, limit to 2 labels if there are many segments
                if len(segments_to_label) > 2:
                    segments_to_label = segments_to_label[:2]
        else:
            # Single contiguous road
            clipped = merged.intersection(boundary_poly)
            if not clipped.is_empty and clipped.length > 0:
                segments_to_label = [clipped]
        
        if not segments_to_label:
            continue
              # Try to label each segment
        for i, clipped in enumerate(segments_to_label):
            if clipped.is_empty or clipped.length == 0:
                continue

            # Special case handling for different road types
            is_small_road = 'highway' in road_data['tags'] and road_data['tags']['highway'] in [
                'footway', 'path', 'pedestrian', 'service', 'track', 'living_street'
            ]
            is_residential = 'highway' in road_data['tags'] and road_data['tags']['highway'] == 'residential'
            
            # If we've already labeled this road, apply distance rules
            if road_name in added_names:
                # For residential roads - important for navigation
                if is_residential:
                    # Always label the first segment
                    if i == 0:
                        pass  # Continue with label placement
                    # For subsequent segments, check distance is sufficient
                    else:
                        # Calculate distance between this and previously labeled segments
                        prev_centers = []
                        for prev_clip in segments_to_label[:i]:
                            # Get the center of the previous segment
                            prev_center = list(prev_clip.interpolate(0.5, normalized=True).coords)[0]
                            prev_x, prev_y = lat_lon_to_xy(prev_center[1], prev_center[0], bbox, svg_width, svg_height)
                            prev_centers.append((prev_x, prev_y))
                        
                        # Calculate center of current segment
                        curr_center = list(clipped.interpolate(0.5, normalized=True).coords)[0]
                        curr_x, curr_y = lat_lon_to_xy(curr_center[1], curr_center[0], bbox, svg_width, svg_height)
                        
                        # Make sure labels are far enough apart (15% of map width for residential)
                        min_distance = min(((curr_x - x)**2 + (curr_y - y)**2)**0.5 for x, y in prev_centers) if prev_centers else float('inf')
                        if min_distance < svg_width * 0.15:
                            continue
                
                # For small roads (footways, paths, etc.)
                elif is_small_road:
                    # Only check distance for multiple segments
                    if i > 0:
                        # Check distance from previous segments
                        prev_centers = []
                        for prev_clip in segments_to_label[:i]:
                            prev_center = list(prev_clip.interpolate(0.5, normalized=True).coords)[0]
                            prev_x, prev_y = lat_lon_to_xy(prev_center[1], prev_center[0], bbox, svg_width, svg_height)
                            prev_centers.append((prev_x, prev_y))
                        
                        # Calculate center of current segment
                        curr_center = list(clipped.interpolate(0.5, normalized=True).coords)[0]
                        curr_x, curr_y = lat_lon_to_xy(curr_center[1], curr_center[0], bbox, svg_width, svg_height)
                        
                        # Skip if too close (20% of map width for small roads)
                        min_distance = min(((curr_x - x)**2 + (curr_y - y)**2)**0.5 for x, y in prev_centers) if prev_centers else float('inf')
                        if min_distance < svg_width * 0.2:
                            continue
                
                # For major roads, be more restrictive to avoid cluttered labels
                else:
                    # Only allow multiple labels for major roads in specific cases:
                    # 1. We have many segments (3+)
                    # 2. This is not the second segment (avoid cluttering)
                    if i > 0 and len(segments_to_label) < 3:
                        continue
                    
                    # For multiple labels, check they're far enough apart
                    prev_centers = []
                    for prev_clip in segments_to_label[:i]:
                        prev_center = list(prev_clip.interpolate(0.5, normalized=True).coords)[0]
                        prev_x, prev_y = lat_lon_to_xy(prev_center[1], prev_center[0], bbox, svg_width, svg_height)
                        prev_centers.append((prev_x, prev_y))
                    
                    # Calculate center of current segment
                    curr_center = list(clipped.interpolate(0.5, normalized=True).coords)[0]
                    curr_x, curr_y = lat_lon_to_xy(curr_center[1], curr_center[0], bbox, svg_width, svg_height)
                    
                    # Require 30% of map width between labels for major roads
                    min_distance = min(((curr_x - x)**2 + (curr_y - y)**2)**0.5 for x, y in prev_centers) if prev_centers else float('inf')
                    if min_distance < svg_width * 0.3:
                        continue
                  # Find better center point by analyzing the segment geometry
            if clipped.geom_type == 'LineString':
                # Get line coordinates in SVG space
                svg_points = [lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height) 
                             for lon, lat in clipped.coords]
                
                if len(svg_points) < 2:
                    continue
                
                # Find the longest straight subsegment to place the label on
                max_subsegment_length = 0
                best_subsegment = None
                
                for i in range(len(svg_points) - 1):
                    p1, p2 = svg_points[i], svg_points[i + 1]
                    length = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
                    if length > max_subsegment_length:
                        max_subsegment_length = length
                        best_subsegment = (i, i + 1)
                
                # Calculate total length to determine center-point correctly
                total_length = 0
                segment_lengths = []
                segment_starts = [0]
                
                for i in range(len(svg_points) - 1):
                    p1, p2 = svg_points[i], svg_points[i + 1]
                    length = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
                    total_length += length
                    segment_lengths.append(length)
                    segment_starts.append(total_length)
                
                # Get the best subsegment for label placement
                if best_subsegment:
                    idx1, idx2 = best_subsegment
                    p1, p2 = svg_points[idx1], svg_points[idx2]
                    
                    # Calculate center point of best subsegment
                    center_x = (p1[0] + p2[0]) / 2
                    center_y = (p1[1] + p2[1]) / 2
                    
                    # Calculate angle for best subsegment
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    angle = math.degrees(math.atan2(dy, dx))
                    
                    # Normalize angle to be readable (avoid upside-down text)
                    if angle < -90 or angle > 90:
                        dx = -dx
                        dy = -dy
                        angle = math.degrees(math.atan2(dy, dx))
                    
                    best_angle = angle
                else:
                    # Fallback to simple center if no good subsegment
                    center_point = list(clipped.interpolate(0.5, normalized=True).coords)[0]
                    center_x, center_y = lat_lon_to_xy(center_point[1], center_point[0], bbox, svg_width, svg_height)
                    best_angle = 0
            else:
                # Fallback for non-LineString geometries
                center_point = list(clipped.interpolate(0.5, normalized=True).coords)[0]
                center_x, center_y = lat_lon_to_xy(center_point[1], center_point[0], bbox, svg_width, svg_height)
                best_angle = 0            # Set appropriate text styles based on road type
            if is_residential:
                # Residential roads get full-size text with smaller buffer
                text_width = len(road_name) * 6
                text_height = 12
                font_size = '12px'
                buffer_distance = 12  # Very small buffer to ensure labels fit
            elif is_small_road:
                # Other small roads get smaller text
                text_width = len(road_name) * 5.5
                text_height = 11
                font_size = '11px'
                buffer_distance = 15  # Small buffer distance
            else:
                # Major roads
                text_width = len(road_name) * 6
                text_height = 12
                font_size = '12px'
                buffer_distance = 20  # Standard buffer distance
            
            # --- OSM-style label clarity improvements ---
            # Always center the label on the best segment, with a white outline and clear font
            found_position = False
            best_x, best_y = center_x, center_y  # Default to center
            # Only use the best position (center of best segment)
            # Try to avoid overlap, but do not repeat the label unless the road is long
            collision, (new_x, new_y) = check_label_collision(
                center_x, center_y, text_width, text_height, best_angle, used_label_areas, buffer_distance
            )
            if not collision:
                best_x, best_y = new_x, new_y
                found_position = True
            # If there is a collision, try a few offsets, but do not repeat label on every segment
            else:
                for dx, dy in [(0, -20), (0, 20), (-20, 0), (20, 0)]:
                    collision, (alt_x, alt_y) = check_label_collision(
                        center_x + dx, center_y + dy, text_width, text_height, best_angle, used_label_areas, buffer_distance
                    )
                    if not collision:
                        best_x, best_y = alt_x, alt_y
                        found_position = True
                        break
            # Render the label only once per road unless it's very long
            if found_position:
                # White outline (background)
                bg = dwg.text(road_name)
                bg['x'] = best_x
                bg['y'] = best_y
                bg['font-family'] = 'Arial, sans-serif'
                bg['font-size'] = font_size
                bg['text-anchor'] = 'middle'
                bg['fill'] = 'none'
                bg['stroke'] = 'white'
                bg['stroke-width'] = 4
                bg['stroke-linecap'] = 'round'
                bg['stroke-linejoin'] = 'round'
                if best_angle != 0:
                    bg['transform'] = f'rotate({best_angle} {best_x} {best_y})'
                text_group.add(bg)
                # Foreground text
                text = dwg.text(road_name)
                text['x'] = best_x
                text['y'] = best_y
                text['font-family'] = 'Arial, sans-serif'
                text['font-size'] = font_size
                text['text-anchor'] = 'middle'
                text['fill'] = '#333333'
                if best_angle != 0:
                    text['transform'] = f'rotate({best_angle} {best_x} {best_y})'
                text_group.add(text)
                # Track label area
                corners = calculate_label_corners(best_x, best_y, text_width, text_height, best_angle)
                used_label_areas.append(Polygon(corners))
                added_names.add(road_name)
