#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SVG Styling Module

This module handles the styling of SVG elements based on OSM tags and KML styles.
"""

import logging
from coord_transform import kml_color_to_svg

# Set up logging
logger = logging.getLogger(__name__)

def get_way_style(tags, is_inside=True):
    """
    Determine rendering style based on OSM tags and position.
    
    Args:
        tags (dict): OSM tags
        is_inside (bool, optional): Whether the feature is inside the boundary. Defaults to True.
        
    Returns:
        dict: Style dictionary with rendering properties or None if no style is applicable
    """
    base_style = None
    
    if "building" in tags:
        base_style = {
            "fill": "#E4E0D8",  # Light beige for buildings
            "stroke": "#D4D0C8",
            "stroke-width": 1,
            "opacity": 0.9,
            "type": "polygon"
        }
    
    elif "amenity" in tags and tags["amenity"] == "parking":
        base_style = {
            "fill": "#F0F0F0",  # Very light gray for parking
            "stroke": "#D0D0D0",
            "stroke-width": 1,
            "opacity": 0.8,
            "type": "polygon",
            "symbol": "P"
        }
    
    elif "highway" in tags:
        highway_type = tags["highway"]
        style = {
            "type": "road",
            "casing": True
        }
        
        if highway_type in ["footway", "path", "pedestrian"]:
            style.update({
                "stroke": "#FFFFFF",  # White for pedestrian paths
                "stroke-width": 2,
                "casing-color": "#E0E0E0",
                "casing-width": 3,
                "opacity": 0.8,
                "is_path": True
            })
        elif highway_type in ["motorway", "trunk"]:
            style.update({
                "stroke": "#FFA07A",
                "stroke-width": 6,
                "casing-color": "#FF8C69",
                "casing-width": 8,
                "opacity": 1
            })
        elif highway_type in ["primary"]:
            style.update({
                "stroke": "#FCD68A",
                "stroke-width": 5,
                "casing-color": "#F4BC6C",
                "casing-width": 7,
                "opacity": 1
            })
        elif highway_type in ["secondary"]:
            style.update({
                "stroke": "#FAFAFA",
                "stroke-width": 4,
                "casing-color": "#E0E0E0",
                "casing-width": 6,
                "opacity": 1
            })
        else:
            style.update({
                "stroke": "#FFFFFF",
                "stroke-width": 2.5,
                "casing-color": "#E0E0E0",
                "casing-width": 3.5,
                "opacity": 0.8
            })
        base_style = style
    
    elif "waterway" in tags or tags.get("natural") == "water":
        base_style = {
            "fill": "#B3D1FF",
            "stroke": "#A1C3FF",
            "stroke-width": 1,
            "opacity": 0.6,
            "type": "polygon"
        }
    
    elif any(tag in tags for tag in ["leisure", "landuse", "natural"]):
        if tags.get("landuse") in ["allotment", "allotments"]:  # Handle both singular and plural
            base_style = {
                "fill": "#E8F4D9",  # Pale green for allotments
                "stroke": "#76A32D",  # Darker, more visible contour
                "stroke-width": 2,    # Thicker border
                "opacity": 0.9,       # Increased opacity
                "type": "polygon"
            }
        elif tags.get("leisure") in ["park", "garden"] or tags.get("landuse") == "grass":
            base_style = {
                "fill": "#90EE90",  # Light green for green spaces
                "stroke": "#7BE37B",
                "stroke-width": 1,
                "opacity": 0.7,
                "type": "polygon"
            }
        elif tags.get("natural") == "wood" or tags.get("landuse") in ["forest", "recreation_ground"]:
            base_style = {
                "fill": "#C6DFB3",  # Dark green for forests
                "stroke": "#B5CE9F",
                "stroke-width": 1,
                "opacity": 0.6,
                "type": "polygon"
            }
    
    if base_style and not is_inside:
        if base_style.get("type") == "road":
            if "is_path" not in base_style:  # Keep footpaths visible
                base_style["stroke"] = "#CCCCCC"
                base_style["casing-color"] = "#BBBBBB"
                base_style["opacity"] = 0.5
        else:
            base_style["fill"] = "#EEEEEE"
            base_style["stroke"] = "#DDDDDD"
            base_style["opacity"] = 0.3
    
    return base_style

def get_kml_style(feature, kml_styles):
    """
    Determine rendering style based on KML style information.
    
    Args:
        feature (dict): KML feature data
        kml_styles (dict): Dictionary of KML style definitions
        
    Returns:
        dict: Style dictionary with rendering properties
    """
    # Default styles
    default_style = {
        "Polygon": {
            "fill": "#3388FF",
            "stroke": "#0066CC",
            "stroke-width": 1,
            "opacity": 0.7,
            "type": "polygon"
        },
        "LineString": {
            "stroke": "#3388FF",
            "stroke-width": 2,
            "opacity": 0.9,
            "type": "line"
        },
        "Point": {
            "fill": "#3388FF",
            "radius": 5,
            "opacity": 0.9,
            "type": "point"
        },
        "MultiGeometry": {
            "fill": "#3388FF",
            "stroke": "#0066CC",
            "stroke-width": 1,
            "opacity": 0.7,
            "type": "multi"
        }
    }
    
    feature_type = feature.get('type')
    style_url = feature.get('style_url')
    
    # Get default style for this feature type
    style = default_style.get(feature_type, default_style['Polygon']).copy()
    
    # If no style URL or no matching style, return default
    if not style_url or not kml_styles:
        return style
    
    # Style URLs in KML are in the format "#style_id"
    style_id = style_url[1:] if style_url.startswith('#') else style_url
    
    if style_id not in kml_styles:
        return style
    
    # Get the KML style definition
    kml_style = kml_styles[style_id]
    
    # Apply style based on feature type
    if feature_type in ('Polygon', 'MultiGeometry'):
        poly_style = kml_style.get('poly_style', {})
        line_style = kml_style.get('line_style', {})
        
        if poly_style:
            if 'color' in poly_style:
                fill_color, fill_opacity = kml_color_to_svg(poly_style['color'])
                style['fill'] = fill_color
                style['opacity'] = fill_opacity
            
            if 'fill' in poly_style:
                style['fill-opacity'] = 0 if not poly_style['fill'] else style['opacity']
        
        if line_style:
            if 'color' in line_style:
                stroke_color, stroke_opacity = kml_color_to_svg(line_style['color'])
                style['stroke'] = stroke_color
                style['stroke-opacity'] = stroke_opacity
            
            if 'width' in line_style:
                style['stroke-width'] = line_style['width']
    
    elif feature_type == 'LineString':
        line_style = kml_style.get('line_style', {})
        
        if line_style:
            if 'color' in line_style:
                stroke_color, stroke_opacity = kml_color_to_svg(line_style['color'])
                style['stroke'] = stroke_color
                style['opacity'] = stroke_opacity
            
            if 'width' in line_style:
                style['stroke-width'] = line_style['width']
    
    elif feature_type == 'Point':
        icon_style = kml_style.get('icon_style', {})
        
        if icon_style:
            if 'color' in icon_style:
                fill_color, fill_opacity = kml_color_to_svg(icon_style['color'])
                style['fill'] = fill_color
                style['opacity'] = fill_opacity
            
            if 'scale' in icon_style:
                style['radius'] = 5 * icon_style['scale']
            
            if 'href' in icon_style:
                style['icon'] = icon_style['href']
    
    return style

def get_feature_style(feature, kml_styles=None, is_inside=True):
    """
    Get the style for a KML feature, with optional boundary context.
    
    Args:
        feature (dict): Feature data (KML or OSM)
        kml_styles (dict, optional): Dictionary of KML style definitions
        is_inside (bool, optional): Whether the feature is inside the boundary
        
    Returns:
        dict: Style dictionary with rendering properties
    """
    # Determine if this is a KML or OSM feature
    if 'type' in feature and feature['type'] in ('Polygon', 'LineString', 'Point', 'MultiGeometry'):
        # KML feature
        style = get_kml_style(feature, kml_styles or {})
    elif 'tags' in feature:
        # OSM feature
        style = get_way_style(feature['tags'], is_inside)
    else:
        # Unknown feature type
        return None
    
    # Modify style if feature is outside boundary
    if not is_inside and style:
        if style.get('type') in ('polygon', 'multi'):
            style['opacity'] = min(style.get('opacity', 1.0) * 0.5, 0.5)
        elif style.get('type') in ('line', 'road'):
            style['opacity'] = min(style.get('opacity', 1.0) * 0.7, 0.7)
    
    return style
