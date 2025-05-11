#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KML Parser Module

This module handles the parsing of KML files and extraction of boundary coordinates 
and feature data from various KML element types.
"""

from pykml import parser
import logging
import os

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    
# Import geometry optimizer if available
try:
    from geometry_optimizer import optimize_feature
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False
    def optimize_feature(feature, is_large_file=False):
        return feature  # No-op function if optimizer not available

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_kml(kml_file, optimize=False, max_features=None, simplify_tolerance=0.00001):
    """
    Extract boundary coordinates from a KML file.
    
    Args:
        kml_file (str): Path to the KML file
        optimize (bool, optional): Whether to optimize geometries
        max_features (int, optional): Maximum number of features to process
        simplify_tolerance (float, optional): Tolerance for simplification operations
        
    Returns:
        dict: Dictionary containing:
            - 'boundary': List of (longitude, latitude) coordinates for the boundary
            - 'features': List of feature dictionaries
        
    Raises:
        ValueError: If no polygon is found in the KML file
    """
    try:
        # Calculate file size for optimization decisions
        file_size_mb = os.path.getsize(kml_file) / (1024 * 1024)
        is_large_file = file_size_mb > 10  # Consider files > 10MB as large
        
        if is_large_file:
            logger.info(f"Processing large KML file ({file_size_mb:.2f} MB), optimizing memory usage")
        
        with open(kml_file, 'rb') as f:
            tree = parser.parse(f)
            root = tree.getroot()
        
        boundary_coords = []
        features = []
        
        # Count placemarks for progress reporting
        placemarks = root.findall(".//{http://www.opengis.net/kml/2.2}Placemark")
        total_placemarks = len(placemarks)
        logger.info(f"Found {total_placemarks} placemarks in KML file")
        
        # Process in batches for large files
        batch_size = 1000 if is_large_file else total_placemarks
        max_features_limit = max_features if max_features else (5000 if is_large_file else float('inf'))
        
        # Use tqdm for progress bar if available
        placemark_iter = tqdm(placemarks, desc="Parsing KML") if TQDM_AVAILABLE and is_large_file else placemarks
        
        for i, placemark in enumerate(placemark_iter):
            if len(features) >= max_features_limit:
                logger.warning(f"Reached maximum feature limit ({max_features_limit}), truncating remaining features")
                break
                
            # Progress reporting for large files (only if tqdm not available)
            if is_large_file and i % batch_size == 0 and not TQDM_AVAILABLE:
                logger.info(f"Processed {i}/{total_placemarks} placemarks ({i/total_placemarks*100:.1f}%)")
            
            try:
                # Get placemark name if available
                name_elem = placemark.find(".//{http://www.opengis.net/kml/2.2}name")
                name = name_elem.text if name_elem is not None else "Unnamed Feature"
                
                # Get description if available
                desc_elem = placemark.find(".//{http://www.opengis.net/kml/2.2}description")
                description = desc_elem.text if desc_elem is not None else None
                
                # Check for style URLs
                style_url_elem = placemark.find(".//{http://www.opengis.net/kml/2.2}styleUrl")
                style_url = style_url_elem.text if style_url_elem is not None else None
                
                # Parse Polygon
                polygon = placemark.findall(".//{http://www.opengis.net/kml/2.2}Polygon")
                if polygon:
                    coords_elem = polygon[0].findall(".//{http://www.opengis.net/kml/2.2}coordinates")
                    if coords_elem:
                        # Coordinates are stored as a string
                        coords_str = coords_elem[0].text.strip()
                        # Convert string to coordinate list
                        coord_pairs = coords_str.split()
                        coords = []
                        for pair in coord_pairs:
                            parts = pair.split(',')
                            if len(parts) >= 2:
                                try:
                                    lon, lat = float(parts[0]), float(parts[1])
                                    coords.append((lon, lat))
                                except ValueError:
                                    logger.warning(f"Invalid coordinate in {name}: {pair}")
                                    continue
                        
                        # Skip empty or invalid coordinate sets
                        if len(coords) < 3:
                            logger.warning(f"Skipping polygon {name} with insufficient coordinates: {len(coords)}")
                            continue
                        
                        # Simplify very complex polygons for large files or if optimize flag is set                        if (is_large_file or optimize) and len(coords) > 500:
                            from shapely.geometry import Polygon as ShapelyPolygon
                            # In Shapely 2.0+, simplify is a method of geometries
                            try:
                                poly = ShapelyPolygon(coords)
                                simplified = poly.simplify(tolerance=simplify_tolerance)
                                original_count = len(coords)
                                coords = list(simplified.exterior.coords)
                                logger.info(f"Simplified complex polygon {name} from {original_count} to {len(coords)} vertices")
                            except Exception as e:
                                logger.warning(f"Failed to simplify complex polygon {name}: {e}")
                        
                        # First polygon is assumed to be the boundary if none defined yet
                        if not boundary_coords:
                            boundary_coords = coords
                            logger.info(f"Using polygon '{name}' as boundary")
                        
                        # Create a feature
                        feature = {
                            'type': 'Polygon',
                            'name': name,
                            'description': description,
                            'style_url': style_url,
                            'coordinates': coords
                        }
                        
                        # Optimize the feature if available and requested
                        if OPTIMIZER_AVAILABLE and optimize:
                            feature = optimize_feature(feature, is_large_file)
                            
                        # Add to features list
                        features.append(feature)
                        continue  # Skip to next placemark
                
                # Parse LineString
                linestring = placemark.findall(".//{http://www.opengis.net/kml/2.2}LineString")
                if linestring:
                    coords_elem = linestring[0].findall(".//{http://www.opengis.net/kml/2.2}coordinates")
                    if coords_elem:
                        coords_str = coords_elem[0].text.strip()
                        coord_pairs = coords_str.split()
                        coords = []
                        for pair in coord_pairs:
                            parts = pair.split(',')
                            if len(parts) >= 2:
                                try:
                                    lon, lat = float(parts[0]), float(parts[1])
                                    coords.append((lon, lat))
                                except ValueError:
                                    logger.warning(f"Invalid coordinate in LineString {name}: {pair}")
                                    continue
                        
                        # Skip if too few coordinates
                        if len(coords) < 2:
                            logger.warning(f"Skipping LineString {name} with insufficient coordinates: {len(coords)}")
                            continue
                            
                        # Simplify very complex linestrings
                        if (is_large_file or optimize) and len(coords) > 500:
                            from shapely.geometry import LineString as ShapelyLineString
                            try:
                                line = ShapelyLineString(coords)
                                simplified = line.simplify(tolerance=simplify_tolerance)
                                original_count = len(coords)
                                coords = list(simplified.coords)
                                logger.info(f"Simplified complex LineString {name} from {original_count} to {len(coords)} vertices")
                            except Exception as e:
                                logger.warning(f"Failed to simplify complex LineString {name}: {e}")
                        
                        # Create a feature
                        feature = {
                            'type': 'LineString',
                            'name': name,
                            'description': description,
                            'style_url': style_url,
                            'coordinates': coords
                        }
                        
                        # Optimize the feature if available and requested
                        if OPTIMIZER_AVAILABLE and optimize:
                            feature = optimize_feature(feature, is_large_file)
                            
                        # Add to features list
                        features.append(feature)
                        continue
                
                # Parse Point
                point = placemark.findall(".//{http://www.opengis.net/kml/2.2}Point")
                if point:
                    coords_elem = point[0].findall(".//{http://www.opengis.net/kml/2.2}coordinates")
                    if coords_elem:
                        coords_str = coords_elem[0].text.strip()
                        parts = coords_str.split(',')
                        if len(parts) >= 2:
                            try:
                                lon, lat = float(parts[0]), float(parts[1])
                                coords = [(lon, lat)]
                                
                                # Create feature
                                feature = {
                                    'type': 'Point',
                                    'name': name,
                                    'description': description,
                                    'style_url': style_url,
                                    'coordinates': coords
                                }
                                
                                # Points don't need optimization, but we'll run it through
                                # the optimizer for consistency if requested
                                if OPTIMIZER_AVAILABLE and optimize:
                                    feature = optimize_feature(feature, is_large_file)
                                
                                features.append(feature)
                            except ValueError:
                                logger.warning(f"Invalid coordinate in Point {name}: {coords_str}")
                        continue
                
                # Parse MultiGeometry
                multigeometry = placemark.findall(".//{http://www.opengis.net/kml/2.2}MultiGeometry")
                if multigeometry:
                    multi_coords = []
                    geom_types = []
                    
                    # Check for polygons in multigeometry
                    for poly in multigeometry[0].findall(".//{http://www.opengis.net/kml/2.2}Polygon"):
                        coords_elem = poly.findall(".//{http://www.opengis.net/kml/2.2}coordinates")
                        if coords_elem:
                            coords_str = coords_elem[0].text.strip()
                            coord_pairs = coords_str.split()
                            poly_coords = []
                            for pair in coord_pairs:
                                parts = pair.split(',')
                                if len(parts) >= 2:
                                    try:
                                        lon, lat = float(parts[0]), float(parts[1])
                                        poly_coords.append((lon, lat))
                                    except ValueError:
                                        continue
                            
                            # Skip polygons with too few points
                            if len(poly_coords) < 3:
                                continue
                                
                            # Simplify complex polygons
                            if (is_large_file or optimize) and len(poly_coords) > 500:
                                from shapely.geometry import Polygon as ShapelyPolygon
                                try:
                                    poly = ShapelyPolygon(poly_coords)
                                    simplified = poly.simplify(tolerance=simplify_tolerance)
                                    original_count = len(poly_coords)
                                    poly_coords = list(simplified.exterior.coords)
                                    logger.info(f"Simplified complex polygon in MultiGeometry from {original_count} to {len(poly_coords)} vertices")
                                except Exception:
                                    pass
                                    
                            multi_coords.append(poly_coords)
                            geom_types.append('Polygon')
                    
                    # Check for linestrings in multigeometry
                    for line in multigeometry[0].findall(".//{http://www.opengis.net/kml/2.2}LineString"):
                        coords_elem = line.findall(".//{http://www.opengis.net/kml/2.2}coordinates")
                        if coords_elem:
                            coords_str = coords_elem[0].text.strip()
                            coord_pairs = coords_str.split()
                            line_coords = []
                            for pair in coord_pairs:
                                parts = pair.split(',')
                                if len(parts) >= 2:
                                    try:
                                        lon, lat = float(parts[0]), float(parts[1])
                                        line_coords.append((lon, lat))
                                    except ValueError:
                                        continue
                            
                            # Skip linestrings with too few points
                            if len(line_coords) < 2:
                                continue
                                
                            # Simplify complex linestrings
                            if (is_large_file or optimize) and len(line_coords) > 500:
                                from shapely.geometry import LineString as ShapelyLineString
                                try:
                                    line = ShapelyLineString(line_coords)
                                    simplified = line.simplify(tolerance=simplify_tolerance)
                                    original_count = len(line_coords)
                                    line_coords = list(simplified.coords)
                                    logger.info(f"Simplified complex LineString in MultiGeometry from {original_count} to {len(line_coords)} vertices")
                                except Exception:
                                    pass
                                    
                            multi_coords.append(line_coords)
                            geom_types.append('LineString')
                    
                    # Check for points in multigeometry
                    for pt in multigeometry[0].findall(".//{http://www.opengis.net/kml/2.2}Point"):
                        coords_elem = pt.findall(".//{http://www.opengis.net/kml/2.2}coordinates")
                        if coords_elem:
                            coords_str = coords_elem[0].text.strip()
                            parts = coords_str.split(',')
                            if len(parts) >= 2:
                                try:
                                    lon, lat = float(parts[0]), float(parts[1])
                                    multi_coords.append([(lon, lat)])
                                    geom_types.append('Point')
                                except ValueError:
                                    continue
                    
                    if multi_coords:
                        # Create feature
                        feature = {
                            'type': 'MultiGeometry',
                            'name': name,
                            'description': description,
                            'style_url': style_url,
                            'coordinates': multi_coords,
                            'geometry_types': geom_types
                        }
                        
                        # Optimize if available and requested
                        if OPTIMIZER_AVAILABLE and optimize:
                            feature = optimize_feature(feature, is_large_file)
                        
                        features.append(feature)
            except Exception as feature_error:
                logger.error(f"Error processing feature '{name}': {feature_error}")
                continue
        
        if is_large_file:
            logger.info(f"Processed all {total_placemarks} placemarks, extracted {len(features)} valid features")
        
        if not boundary_coords and features:
            # If no boundary was found, use the first polygon as boundary
            for feature in features:
                if feature['type'] == 'Polygon':
                    boundary_coords = feature['coordinates']
                    logger.info(f"Using first polygon feature '{feature['name']}' as boundary")
                    break
        
        if not boundary_coords:
            raise ValueError("No polygon found in the KML file to use as boundary")
        
        logger.info(f"Extracted boundary and {len(features)} features from KML file")
        
        return {
            'boundary': boundary_coords,
            'features': features
        }
    except Exception as e:
        logger.error(f"Error parsing KML file: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        raise

def extract_kml_styles(kml_file):
    """
    Extract style definitions from a KML file.
    
    Args:
        kml_file (str): Path to the KML file
        
    Returns:
        dict: Dictionary of style definitions keyed by style ID
    """
    try:
        # Calculate file size for optimization decisions
        file_size_mb = os.path.getsize(kml_file) / (1024 * 1024)
        is_large_file = file_size_mb > 10  # Consider files > 10MB as large
        
        with open(kml_file, 'rb') as f:
            tree = parser.parse(f)
            root = tree.getroot()
        
        styles = {}
        
        # Look for Style elements
        style_elements = root.findall(".//{http://www.opengis.net/kml/2.2}Style")
        
        # For very large files, limit the number of styles processed
        if is_large_file and len(style_elements) > 200:
            logger.warning(f"Large number of styles found ({len(style_elements)}), limiting to 200 styles")
            style_elements = style_elements[:200]
        
        for style in style_elements:
            try:
                if 'id' in style.attrib:
                    style_id = style.attrib['id']
                    
                    # Extract line style
                    line_style = style.find(".//{http://www.opengis.net/kml/2.2}LineStyle")
                    line_info = {}
                    if line_style is not None:
                        color_elem = line_style.find(".//{http://www.opengis.net/kml/2.2}color")
                        if color_elem is not None:
                            line_info['color'] = color_elem.text
                        
                        width_elem = line_style.find(".//{http://www.opengis.net/kml/2.2}width")
                        if width_elem is not None:
                            try:
                                line_info['width'] = float(width_elem.text)
                            except ValueError:
                                line_info['width'] = 1.0
                    
                    # Extract polygon style
                    poly_style = style.find(".//{http://www.opengis.net/kml/2.2}PolyStyle")
                    poly_info = {}
                    if poly_style is not None:
                        color_elem = poly_style.find(".//{http://www.opengis.net/kml/2.2}color")
                        if color_elem is not None:
                            poly_info['color'] = color_elem.text
                        
                        fill_elem = poly_style.find(".//{http://www.opengis.net/kml/2.2}fill")
                        if fill_elem is not None:
                            poly_info['fill'] = fill_elem.text == '1'
                        
                        outline_elem = poly_style.find(".//{http://www.opengis.net/kml/2.2}outline")
                        if outline_elem is not None:
                            poly_info['outline'] = outline_elem.text == '1'
                    
                    # Extract icon style
                    icon_style = style.find(".//{http://www.opengis.net/kml/2.2}IconStyle")
                    icon_info = {}
                    if icon_style is not None:
                        icon_elem = icon_style.find(".//{http://www.opengis.net/kml/2.2}Icon/{http://www.opengis.net/kml/2.2}href")
                        if icon_elem is not None:
                            icon_info['href'] = icon_elem.text
                            
                        color_elem = icon_style.find(".//{http://www.opengis.net/kml/2.2}color")
                        if color_elem is not None:
                            icon_info['color'] = color_elem.text
                            
                        scale_elem = icon_style.find(".//{http://www.opengis.net/kml/2.2}scale")
                        if scale_elem is not None:
                            try:
                                icon_info['scale'] = float(scale_elem.text)
                            except ValueError:
                                icon_info['scale'] = 1.0
                        
                    # Add to styles dictionary
                    styles[style_id] = {
                        'line_style': line_info if line_info else None,
                        'poly_style': poly_info if poly_info else None,
                        'icon_style': icon_info if icon_info else None
                    }
            except Exception as style_error:
                logger.warning(f"Error processing style {style.attrib.get('id', 'unknown')}: {style_error}")
                continue
                
        logger.info(f"Extracted {len(styles)} style definitions from KML file")
        return styles
    except Exception as e:
        logger.error(f"Error extracting styles from KML file: {e}")
        return {}
