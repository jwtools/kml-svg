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
    added_names = set()    # Track label positions to prevent overlaps
    used_label_areas = []
    
    # Always draw the boundary as a thin grey line
    draw_boundary(dwg, background_group, boundary_coords, bbox, svg_width, svg_height)
    
    # Process KML features if available (now just gets the boundary)
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
    """Draw the boundary polygon as a thin grey line"""
    svg_points = transform_coordinates(boundary_coords, bbox, svg_width, svg_height)
    
    # Create boundary path
    poly_path = f'M {svg_points[0][0]},{svg_points[0][1]}'
    for x, y in svg_points[1:]:
        poly_path += f' L {x},{y}'
    poly_path += ' Z'
    
    path = dwg.path(d=poly_path)
    path['fill'] = 'none'
    path['stroke'] = '#999999'  # Grey color
    path['stroke-width'] = 1    # Thin line
    group.add(path)

def process_kml_features(dwg, kml_group, kml_features, kml_styles, boundary_coords, bbox, 
                        svg_width, svg_height, text_group, used_label_areas, skip_labels):
    """Process and render KML features - modified to only show outlines without content"""
    logger.info(f"Processing KML features (outlines only)")
    
    # Create subgroups for different feature types
    polygon_group = dwg.g(id='kml-polygons')
    line_group = dwg.g(id='kml-lines')
    point_group = dwg.g(id='kml-points')
    
    # We'll only add the boundary polygon as a thin grey line
    # The actual KML features won't be rendered
    
    # Add subgroups to main KML group (they'll be empty but kept for structure)
    kml_group.add(polygon_group)
    kml_group.add(line_group)
    kml_group.add(point_group)

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
    from shapely.geometry import Polygon, LineString
    from shapely.ops import linemerge
    for road_name, road_data in roads_by_name.items():
        if not road_data['segments']:
            continue
        # Merge all segments (not just inside ones)
        all_lines = [LineString(seg) for seg in road_data['segments'] if len(seg) > 1]
        if not all_lines:
            continue
        merged = linemerge(all_lines)
        # Collect all coordinates from all segments for true geometric center
        all_coords = []
        for seg in road_data['segments']:
            all_coords.extend(seg)
        if not all_coords:
            continue
        # Compute geometric center of all segments (in SVG coordinates)
        svg_all_points = [lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height) for lon, lat in all_coords]
        geo_center_x = sum(p[0] for p in svg_all_points) / len(svg_all_points)
        geo_center_y = sum(p[1] for p in svg_all_points) / len(svg_all_points)
        road_center = (geo_center_x, geo_center_y)
        # Find the closest point on any segment to the geometric center
        min_dist = float('inf')
        best_point = None
        best_angle = 0
        best_svg_points = None
        for line in all_lines:
            svg_points = [lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height) for lon, lat in line.coords]
            for i in range(len(svg_points) - 1):
                p1, p2 = svg_points[i], svg_points[i + 1]
                proj = project_point_to_line(road_center, p1, p2)
                dist = ((road_center[0] - proj[0])**2 + (road_center[1] - proj[1])**2)**0.5
                if dist < min_dist:
                    min_dist = dist
                    best_point = proj
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    angle = math.degrees(math.atan2(dy, dx))
                    if angle < -90 or angle > 90:
                        dx = -dx
                        dy = -dy
                        angle = math.degrees(math.atan2(dy, dx))
                    best_angle = angle
                    best_svg_points = svg_points
        if best_point is None or best_svg_points is None:
            continue
        text_width = len(road_name) * 6
        text_height = 12
        # Snap label to the best position on the road
        label_x, label_y = snap_label_to_road(best_point[0], best_point[1], best_angle, best_svg_points, 0, text_width, text_height, road_center)
        if not check_label_collision(label_x, label_y, text_width, text_height, best_angle, used_label_areas)[0]:
            text = dwg.text(road_name)
            text['x'] = label_x
            text['y'] = label_y
            text['font-family'] = 'Arial, sans-serif'
            text['font-size'] = '12px'
            text['text-anchor'] = 'middle'
            text['fill'] = '#333333'
            if best_angle != 0:
                text['transform'] = f'rotate({best_angle} {label_x} {label_y})'
            # Add white outline/background for better readability
            bg = dwg.text(road_name)
            bg['x'] = label_x
            bg['y'] = label_y
            bg['font-family'] = 'Arial, sans-serif'
            bg['font-size'] = '12px'
            bg['text-anchor'] = 'middle'
            bg['fill'] = 'none'
            bg['stroke'] = 'white'
            bg['stroke-width'] = 3
            bg['stroke-linecap'] = 'round'
            bg['stroke-linejoin'] = 'round'
            if best_angle != 0:
                bg['transform'] = f'rotate({best_angle} {label_x} {label_y})'
            text_group.add(bg)
            text_group.add(text)
            # Add to used areas
            corners = calculate_label_corners(label_x, label_y, text_width, text_height, best_angle)
            used_label_areas.append(Polygon(corners))
            added_names.add(road_name)

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
    
    # Also create a box without buffer for checking actual text overlap
    actual_text_corners = calculate_label_corners(x, y, width, height, angle, 0)
    actual_text_box = Polygon(actual_text_corners)
    
    # Define a more comprehensive set of alternative positions to try
    # This spiral pattern tries positions further away from the original point
    spiral_offsets = []
    max_distance = 40  # Maximum distance to try (reduced from 60 to keep labels closer to roads)
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
    # Reduced distances to keep labels closer to roads
    cardinal_offsets = [
        (0, -15), (0, 15),     # North, South - closer positions
        (-15, 0), (15, 0),     # West, East - closer positions
        (0, -25), (0, 25),     # Further North, South
        (-25, 0), (25, 0),     # Further West, East
        (10, 10), (-10, 10),   # Diagonal directions
        (10, -10), (-10, -10) # Diagonal directions
    ]
    
    # Combine cardinal directions with spiral pattern, prioritizing cardinal
    retry_offsets = cardinal_offsets + spiral_offsets
    
    # Check collision with existing labels
    collision_found = False
    severe_collision = False
    intersecting_areas = []
    
    # First, identify all intersecting areas
    for existing_area in used_label_areas:
        # Check if buffer areas intersect (less severe)
        if new_box.intersects(existing_area):
            collision_found = True
            intersecting_areas.append(existing_area)
            
            # Check if actual text areas intersect (more severe)
            # Use centroid to approximate the text area of existing labels
            existing_center = existing_area.centroid
            # Estimate existing text dimensions (assuming similar buffer ratio)
            existing_width = existing_area.bounds[2] - existing_area.bounds[0]
            existing_height = existing_area.bounds[3] - existing_area.bounds[1]
            estimated_text_width = existing_width * 0.8  # Estimate actual text width
            estimated_text_height = existing_height * 0.8  # Estimate actual text height
            
            # Create approximate text area for existing label
            existing_text_corners = calculate_label_corners(
                existing_center.x, existing_center.y, 
                estimated_text_width, estimated_text_height, 
                0, 0  # No buffer
            )
            existing_text_box = Polygon(existing_text_corners)
            
            # Check for severe collision (actual text overlaps)
            if actual_text_box.intersects(existing_text_box):
                severe_collision = True
    
    # Allow slight buffer overlaps but no severe text overlaps
    if not collision_found or (collision_found and not severe_collision and buffer_distance > 10):
        # Accept this position if only buffer areas overlap but not text
        return False, (x, y)
    
    # If collision found, try alternative positions
    # Prioritize positions with minimal overlap with existing labels
    min_overlap = float('inf')
    best_pos = (x, y)
    
    # For each offset, calculate overlap with ALL existing areas
    for dx, dy in retry_offsets:
        alt_corners = calculate_label_corners(x + dx, y + dy, width, height, angle, buffer_distance)
        alt_box = Polygon(alt_corners)
        
        # Also create actual text box for this alternative position
        alt_text_corners = calculate_label_corners(x + dx, y + dy, width, height, angle, 0)
        alt_text_box = Polygon(alt_text_corners)
        
        # Calculate total overlap with all existing areas
        total_overlap = sum(alt_box.intersection(area).area for area in used_label_areas if alt_box.intersects(area))
        
        # Check for severe text overlaps at this position
        text_overlaps = False
        for existing_area in used_label_areas:
            existing_center = existing_area.centroid
            existing_width = existing_area.bounds[2] - existing_area.bounds[0]
            existing_height = existing_area.bounds[3] - existing_area.bounds[1]
            estimated_text_width = existing_width * 0.8
            estimated_text_height = existing_height * 0.8
            
            existing_text_corners = calculate_label_corners(
                existing_center.x, existing_center.y, 
                estimated_text_width, estimated_text_height, 
                0, 0
            )
            existing_text_box = Polygon(existing_text_corners)
            
            if alt_text_box.intersects(existing_text_box):
                text_overlaps = True
                break
        
        # Check if this is a valid position (minimal or no overlap)
        if total_overlap == 0:
            return False, (x + dx, y + dy)
        
        # If no text overlaps and buffer overlap is minimal, consider this position
        if not text_overlaps and total_overlap < min_overlap:
            min_overlap = total_overlap
            best_pos = (x + dx, y + dy)
        # Even with text overlaps, track best position as fallback
        elif text_overlaps and total_overlap < min_overlap:
            min_overlap = total_overlap
            # Only update position if we don't already have a non-text-overlapping position
            if best_pos == (x, y):
                best_pos = (x + dx, y + dy)
    
    # If all positions have collisions, try once more with a reduced buffer
    if buffer_distance > 5:
        reduced_buffer = max(buffer_distance / 2, 5)
        # Just try a few key positions with reduced buffer
        for dx, dy in cardinal_offsets:
            alt_corners = calculate_label_corners(x + dx, y + dy, width, height, angle, reduced_buffer)
            alt_box = Polygon(alt_corners)
            
            # Create actual text box for this position
            alt_text_corners = calculate_label_corners(x + dx, y + dy, width, height, angle, 0)
            alt_text_box = Polygon(alt_text_corners)
            
            # Check for severe text overlaps
            text_overlaps = False
            for existing_area in used_label_areas:
                existing_center = existing_area.centroid
                existing_width = existing_area.bounds[2] - existing_area.bounds[0]
                existing_height = existing_area.bounds[3] - existing_area.bounds[1]
                estimated_text_width = existing_width * 0.8
                estimated_text_height = existing_height * 0.8
                
                existing_text_corners = calculate_label_corners(
                    existing_center.x, existing_center.y, 
                    estimated_text_width, estimated_text_height, 
                    0, 0
                )
                existing_text_box = Polygon(existing_text_corners)
                
                if alt_text_box.intersects(existing_text_box):
                    text_overlaps = True
                    break
            
            # Accept position with reduced buffer if no text overlaps
            if not text_overlaps:
                return False, (x + dx, y + dy)
    
    # Always return a position - we never want to remove labels
    # Return the position with minimal overlap
    return False, best_pos

def snap_label_to_road(x, y, angle, svg_points, offset=0, text_width=0, text_height=0, road_center=None):
    """
    Snap a label position to the nearest point on the road, accounting for angle and readability.
    Now also considers proximity to the geometric center of the road.
    Args:
        x, y (float): Current label position
        angle (float): Rotation angle of the label in degrees
        svg_points (list): List of road segment points in SVG coordinates
        offset (float): Offset perpendicular to the road line
        text_width (float): Width of the text label (for optimizing position)
        text_height (float): Height of the text label (for optimizing position)
        road_center (tuple): (x, y) of the geometric center of the road in SVG coordinates
    Returns:
        tuple: (snapped_x, snapped_y) - New position snapped to road
    """
    if len(svg_points) < 2:
        return x, y
    if road_center is None:
        road_center = (x, y)
    suitable_segments = []
    total_road_length = 0
    for i in range(len(svg_points) - 1):
        p1, p2 = svg_points[i], svg_points[i + 1]
        segment_length = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
        total_road_length += segment_length

    is_short_road = total_road_length < text_width * 1.5

    for i in range(len(svg_points) - 1):
        p1, p2 = svg_points[i], svg_points[i + 1]
        segment_length = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
        min_segment_length = text_width * 0.5 if is_short_road else text_width * 0.75
        if segment_length < min_segment_length:
            continue
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        segment_angle = math.degrees(math.atan2(dy, dx))
        if segment_angle < -90 or segment_angle > 90:
            segment_angle = math.degrees(math.atan2(-dy, -dx))
        horizontality = abs(segment_angle)
        projected = project_point_to_line((x, y), p1, p2)
        p1_to_proj = ((projected[0] - p1[0])**2 + (projected[1] - p1[1])**2)**0.5
        p2_to_proj = ((projected[0] - p2[0])**2 + (projected[1] - p2[1])**2)**0.5
        segment_to_segment_ratio = p1_to_proj / (p1_to_proj + p2_to_proj)
        if is_short_road:
            mid_x = (p1[0] + p2[0]) / 2
            mid_y = (p1[1] + p2[1]) / 2
            projected = (mid_x, mid_y)
            dist = ((x - mid_x)**2 + (y - mid_y)**2)**0.5
        else:
            dist = ((x - projected[0])**2 + (y - projected[1])**2)**0.5
        # New: compute how close this segment's midpoint is to the road's geometric center
        seg_mid_x = (p1[0] + p2[0]) / 2
        seg_mid_y = (p1[1] + p2[1]) / 2
        center_dist = ((seg_mid_x - road_center[0])**2 + (seg_mid_y - road_center[1])**2)**0.5
        suitable_segments.append({
            'segment_idx': i,
            'projected_point': projected,
            'distance': dist,
            'length': segment_length,
            'angle': segment_angle,
            'horizontality': horizontality,
            'segment_ratio': segment_to_segment_ratio,
            'is_middle': abs(segment_to_segment_ratio - 0.5) < 0.2,
            'center_dist': center_dist,
            'seg_mid': (seg_mid_x, seg_mid_y)
        })

    if not suitable_segments:
        return x, y

    # Find min/max for normalization
    min_center_dist = min(s['center_dist'] for s in suitable_segments)
    max_center_dist = max(s['center_dist'] for s in suitable_segments)
    center_dist_range = max(max_center_dist - min_center_dist, 1e-6)

    for segment in suitable_segments:
        distance_score = 1 - min(segment['distance'] / 100, 1)
        length_score = min(segment['length'] / (text_width * 2), 1)
        horizontality_score = 1 - (segment['horizontality'] / 90)
        middle_score = 1.0 - abs(segment['segment_ratio'] - 0.5) * 2
        # New: score for proximity to road center (1 = closest)
        center_proximity_score = 1 - (segment['center_dist'] - min_center_dist) / center_dist_range
        # Strongly weight center proximity for all roads
        if is_short_road:
            segment['score'] = (
                distance_score * 0.1 +
                length_score * 0.1 +
                horizontality_score * 0.1 +
                middle_score * 0.2 +
                center_proximity_score * 0.5
            )
        else:
            segment['score'] = (
                distance_score * 0.15 +
                length_score * 0.15 +
                horizontality_score * 0.1 +
                middle_score * 0.2 +
                center_proximity_score * 0.4
            )

    suitable_segments.sort(key=lambda s: s['score'], reverse=True)
    best_segment = suitable_segments[0]
    segment_idx = best_segment['segment_idx']
    projected_point = best_segment['projected_point']
    # Use the angle of the best segment (not returned, but could be used if needed)
    if offset != 0 and segment_idx < len(svg_points) - 1:
        p1, p2 = svg_points[segment_idx], svg_points[segment_idx + 1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = ((dx)**2 + (dy)**2)**0.5
        if length > 0:
            perpendicular_x = -dy / length
            perpendicular_y = dx / length
            projected_point = (
                projected_point[0] + perpendicular_x * offset,
                projected_point[1] + perpendicular_y * offset
            )
    return projected_point
