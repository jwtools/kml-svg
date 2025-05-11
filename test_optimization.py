#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for the KML to SVG converter with geometry optimization.
This script demonstrates the use of the geometry optimizer module
on a sample KML file, comparing performance with and without optimization.
"""

import os
import time
import argparse
import logging
from shapely.geometry import Polygon, LineString

from kml_parser import parse_kml
from geo_utils import get_bounding_box
from svg_generator import create_svg_map

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_optimization(kml_file, output_dir="output"):
    """Test the geometry optimization features on a KML file."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Process without optimization
    start_time = time.time()
    logger.info(f"Parsing KML file without optimization: {kml_file}")
    kml_data = parse_kml(kml_file, optimize=False)
    boundary_coords = kml_data['boundary']
    kml_features = kml_data['features']
    
    # Calculate total vertices
    total_vertices = count_vertices(kml_features)
    
    # Create SVG without optimization
    bbox = get_bounding_box(boundary_coords)
    unoptimized_output = os.path.join(output_dir, "unoptimized_map.svg")
    create_svg_map(
        osm_data=None,  # Skip OSM data for this test
        boundary_coords=boundary_coords,
        output_file=unoptimized_output,
        svg_width=800,
        svg_height=600,
        kml_features=kml_features,
        skip_labels=False
    )
    unoptimized_time = time.time() - start_time
    unoptimized_size = os.path.getsize(unoptimized_output)
    
    # Process with optimization
    start_time = time.time()
    logger.info(f"Parsing KML file with optimization: {kml_file}")
    kml_data = parse_kml(kml_file, optimize=True, simplify_tolerance=0.00001)
    boundary_coords = kml_data['boundary']
    optimized_kml_features = kml_data['features']
    
    # Calculate optimized vertices
    optimized_vertices = count_vertices(optimized_kml_features)
    
    # Create SVG with optimization
    optimized_output = os.path.join(output_dir, "optimized_map.svg")
    create_svg_map(
        osm_data=None,  # Skip OSM data for this test
        boundary_coords=boundary_coords,
        output_file=optimized_output,
        svg_width=800,
        svg_height=600,
        kml_features=optimized_kml_features,
        skip_labels=False
    )
    optimized_time = time.time() - start_time
    optimized_size = os.path.getsize(optimized_output)
    
    # Print results
    logger.info("\nOptimization Test Results:")
    logger.info("--------------------------")
    logger.info(f"Original vertices count: {total_vertices}")
    logger.info(f"Optimized vertices count: {optimized_vertices}")
    logger.info(f"Vertex reduction: {total_vertices - optimized_vertices} ({((total_vertices - optimized_vertices) / total_vertices * 100):.2f}%)")
    logger.info(f"\nUnoptimized processing time: {unoptimized_time:.2f} seconds")
    logger.info(f"Optimized processing time: {optimized_time:.2f} seconds")
    logger.info(f"Time improvement: {((unoptimized_time - optimized_time) / unoptimized_time * 100):.2f}%")
    logger.info(f"\nUnoptimized SVG size: {unoptimized_size / 1024:.2f} KB")
    logger.info(f"Optimized SVG size: {optimized_size / 1024:.2f} KB")
    logger.info(f"Size reduction: {((unoptimized_size - optimized_size) / unoptimized_size * 100):.2f}%")
    logger.info(f"\nUnoptimized SVG saved to: {unoptimized_output}")
    logger.info(f"Optimized SVG saved to: {optimized_output}")

def count_vertices(features):
    """Count the total number of vertices in all features."""
    total = 0
    for feature in features:
        feature_type = feature.get('type')
        
        if feature_type == 'Polygon':
            total += len(feature.get('coordinates', []))
        elif feature_type == 'LineString':
            total += len(feature.get('coordinates', []))
        elif feature_type == 'Point':
            total += 1
        elif feature_type == 'MultiGeometry':
            for coords in feature.get('coordinates', []):
                total += len(coords)
    
    return total

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test geometry optimization in KML to SVG converter")
    parser.add_argument("-k", "--kml", required=True, help="Path to input KML file")
    parser.add_argument("-o", "--output-dir", default="output", help="Output directory for generated SVGs")
    
    args = parser.parse_args()
    test_optimization(args.kml, args.output_dir)
