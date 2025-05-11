#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Road Labels Script

This script tests the road labeling functionality including the following cases:
1. Test for duplicate road labels
2. Test for proper labeling of small roads and paths
3. Test for residential road labeling
4. Test for centering road names on KML segments
"""

import os
import sys
import time
import logging
import argparse
import traceback
from pathlib import Path

from kml_parser import parse_kml, extract_kml_styles
from osm_data import download_osm_data, load_osm_cache, save_osm_cache, get_cache_key
from svg_generator import create_svg_map
from geo_utils import get_bounding_box

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_test(kml_file, output_dir):
    """Run road label tests"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    logger.info(f"Starting road label tests with KML file: {kml_file}")
    logger.info(f"Test results will be saved to: {output_dir}")
    
    # Parse KML file
    kml_data = parse_kml(kml_file)
    kml_features = kml_data['features']
    boundary_coords = kml_data['boundary']
    kml_styles = extract_kml_styles(kml_file)
    
    # Debug: Print boundary coordinates
    logger.debug(f"Boundary coordinates: {boundary_coords[:3]}...")
    
    # Calculate the bounding box
    bbox = get_bounding_box(boundary_coords)
    
    # Default map size
    svg_width = 800
    svg_height = 600
      # Get OSM data
    logger.info("Downloading or retrieving cached OSM data...")
    
    # Load cache and check if we already have data for this bounding box
    osm_data = None
    cache_key = get_cache_key(bbox)
    
    try:
        cache = load_osm_cache()
        if cache_key in cache:
            logger.info("Using cached OSM data...")
            osm_data = cache[cache_key]
        else:
            logger.info("Downloading OSM data...")
            osm_data = download_osm_data(bbox)
            cache[cache_key] = osm_data
            save_osm_cache(cache)
    except Exception as e:
        logger.error(f"Error loading or saving OSM data: {e}")
        logger.error("Downloading OSM data without caching...")
        osm_data = download_osm_data(bbox)
    
    # Test 1: Basic Road Labels
    logger.info("Test 1: Basic road labels")
    output_file = output_dir / f"basic_road_labels_{timestamp}.svg"
    create_svg_map(
        osm_data, 
        boundary_coords, 
        str(output_file), 
        svg_width=svg_width, 
        svg_height=svg_height,
        kml_features=kml_features,
        kml_styles=kml_styles
    )
    logger.info(f"Basic road labels test output: {output_file}")
    
    # Test 2: Debug View with Boundaries
    logger.info("Test 2: Debug view with boundaries")
    output_file = output_dir / f"debug_road_labels_{timestamp}.svg"
    create_svg_map(
        osm_data, 
        boundary_coords, 
        str(output_file), 
        svg_width=svg_width, 
        svg_height=svg_height,
        kml_features=kml_features,
        kml_styles=kml_styles,
        debug_bounds=True
    )
    logger.info(f"Debug view test output: {output_file}")
    
    # Test 3: Larger Map
    logger.info("Test 3: Larger map for better label visualization")
    output_file = output_dir / f"large_road_labels_{timestamp}.svg"
    create_svg_map(
        osm_data, 
        boundary_coords, 
        str(output_file), 
        svg_width=1200, 
        svg_height=900,
        kml_features=kml_features,
        kml_styles=kml_styles
    )
    logger.info(f"Larger map test output: {output_file}")
    
    # Test 4: Just road labels (no other features)
    logger.info("Test 4: Just road labels (no other features)")
    output_file = output_dir / f"only_roads_{timestamp}.svg"
    create_svg_map(
        osm_data, 
        boundary_coords, 
        str(output_file), 
        svg_width=svg_width, 
        svg_height=svg_height,
        kml_features=[], # No KML features
        kml_styles={}
    )
    logger.info(f"Only roads test output: {output_file}")
    
    logger.info("Road label tests completed successfully!")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test road labeling functionality")
    parser.add_argument("-k", "--kml", required=True, help="KML file to use for testing")
    parser.add_argument("-o", "--output-dir", default="output/road_label_tests", 
                        help="Directory to store test outputs")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Set logging level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        logger.info(f"Starting test with KML file: {args.kml}")
        run_test(args.kml, args.output_dir)
        logger.info("Test completed successfully")
    except Exception as e:
        logger.error(f"Error during testing: {e}")
        if args.verbose:
            logger.error(traceback.format_exc())
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
