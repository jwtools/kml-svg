#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main Entry Point for KML to SVG Converter

This module serves as the entry point for the KML to SVG conversion process.
"""

import sys
import os
import argparse
import logging
import traceback

from kml_parser import parse_kml, extract_kml_styles
from geo_utils import get_bounding_box
from osm_data import download_osm_data
from svg_generator import create_svg_map
from config_parser import load_config

def setup_logging(verbose=False):
    """Set up logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    return logger

def main():
    """Main entry point for the KML to SVG conversion"""
    # Load configuration
    config = load_config()
    svg_config = config.get('svg', {})
    default_width = svg_config.get('width', 800)
    default_height = svg_config.get('height', 600)
      # Parse command-line arguments
    parser = argparse.ArgumentParser(description="SVG Map Generator from KML files")
    parser.add_argument("-k", "--kml", required=True, help="Path to input KML file")
    parser.add_argument("-o", "--output", default="carte_generee.svg", help="Path to output SVG file (default: carte_generee.svg)")
    parser.add_argument("-w", "--width", type=int, default=default_width, help=f"Width of SVG canvas (default: {default_width})")
    parser.add_argument("--height", type=int, default=default_height, help=f"Height of SVG canvas (default: {default_height})")
    parser.add_argument("-c", "--config", help="Path to custom config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--no-osm", action="store_true", help="Skip OSM data download (use only KML features)")
    parser.add_argument("--no-labels", action="store_true", help="Skip rendering of text labels")
    parser.add_argument("--debug-bounds", action="store_true", help="Add boundary visualization for debugging")
    parser.add_argument("--optimize", action="store_true", help="Enable geometry optimization for complex features")
    parser.add_argument("--simplify", type=float, default=0.00001, help="Simplification tolerance for complex geometries (default: 0.00001)")
    parser.add_argument("--max-features", type=int, help="Maximum number of features to process from KML file")
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging(args.verbose)
    
    # If custom config file provided, reload configuration
    if args.config:
        if not os.path.exists(args.config):
            logger.error(f"Config file not found: {args.config}")
            sys.exit(1)
        config = load_config(args.config)
    
    kml_file = args.kml
    output_file = args.output
    svg_width = args.width
    svg_height = args.height
    verbose = args.verbose
    skip_osm = args.no_osm
    skip_labels = args.no_labels
    debug_bounds = args.debug_bounds
    
    try:        # Extract data from KML file
        logger.info(f"Parsing KML file: {kml_file}")
        kml_data = parse_kml(
            kml_file=kml_file, 
            optimize=args.optimize,
            max_features=args.max_features,
            simplify_tolerance=args.simplify
        )
        boundary_coords = kml_data['boundary']
        kml_features = kml_data['features']
        
        # Extract KML styles
        kml_styles = extract_kml_styles(kml_file)
        
        # Calculate bounding box
        logger.info("Calculating bounding box...")
        bbox = get_bounding_box(boundary_coords)
        
        # Download OSM data (unless --no-osm flag is set)
        osm_data = None
        if not skip_osm:
            logger.info("Downloading or retrieving cached OSM data...")
            osm_data = download_osm_data(bbox)
        
        # Create SVG
        logger.info(f"Generating SVG map: {output_file}")
        create_svg_map(
            osm_data=osm_data, 
            boundary_coords=boundary_coords, 
            output_file=output_file, 
            svg_width=svg_width, 
            svg_height=svg_height,
            kml_features=kml_features,
            kml_styles=kml_styles,
            skip_labels=skip_labels,
            debug_bounds=debug_bounds
        )
        
        logger.info(f"SVG map created successfully: {output_file}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        if verbose:
            logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
