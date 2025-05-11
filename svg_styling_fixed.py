#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SVG Styling Module

This module handles the styling of SVG elements based on OSM tags.
"""

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
