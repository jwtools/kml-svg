#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main Entry Point for KML to SVG Converter

This module serves as the entry point for the KML to SVG conversion process.
"""

import sys
import os
import argparse

from kml_parser import parse_kml
from geo_utils import get_bounding_box
from osm_data import download_osm_data
from svg_generator import create_svg_map
from config_parser import load_config

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
    
    args = parser.parse_args()
    
    # If custom config file provided, reload configuration
    if args.config:
        if not os.path.exists(args.config):
            print(f"Error: Config file not found: {args.config}")
            sys.exit(1)
        config = load_config(args.config)
    
    kml_file = args.kml
    output_file = args.output
    svg_width = args.width
    svg_height = args.height
    verbose = args.verbose
    
    try:
        # Extract polygon from KML file
        if verbose:
            print(f"Parsing KML file: {kml_file}")
        boundary_coords = parse_kml(kml_file)
        
        # Calculate bounding box
        if verbose:
            print("Calculating bounding box...")
        bbox = get_bounding_box(boundary_coords)
        
        # Download OSM data
        if verbose:
            print("Downloading or retrieving cached OSM data...")
        osm_data = download_osm_data(bbox)
        
        # Create SVG
        if verbose:
            print(f"Generating SVG map: {output_file}")
        create_svg_map(osm_data, boundary_coords, output_file, svg_width=svg_width, svg_height=svg_height)
        
        print(f"SVG map created successfully: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
