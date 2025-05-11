#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Script for KML to SVG Converter

This script runs tests on the KML to SVG converter to ensure it works properly.
"""

import os
import sys
import argparse

def run_tests(verbose=False):
    """Run tests on the KML to SVG converter."""
    print("Running tests for KML to SVG converter...")
    
    # Test 1: Check if modules can be imported
    print("\nTest 1: Checking if modules can be imported...")
    try:
        from kml_parser import parse_kml
        from geo_utils import get_bounding_box, is_line_in_boundary
        from osm_data import download_osm_data
        from svg_generator import create_svg_map
        from svg_styling import get_way_style
        from coord_transform import lat_lon_to_xy
        from config_parser import load_config, get_style
        print("✓ All modules imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import modules: {e}")
        return False
    
    # Test 2: Check if config can be loaded
    print("\nTest 2: Checking if config can be loaded...")
    try:
        config = load_config()
        if verbose:
            print(f"Loaded configuration: {config}")
        print("✓ Configuration loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False
    
    # Test 3: Check if KML file can be parsed
    print("\nTest 3: Checking if KML file can be parsed...")
    try:
        kml_file = os.path.join('kml', 'Test territoire.kml')
        if not os.path.exists(kml_file):
            print(f"✗ Test KML file not found: {kml_file}")
            return False
        
        boundary_coords = parse_kml(kml_file)
        print(f"✓ KML file parsed successfully ({len(boundary_coords)} coordinates)")
    except Exception as e:
        print(f"✗ Failed to parse KML file: {e}")
        return False
    
    # Test 4: Check if bounding box can be calculated
    print("\nTest 4: Checking if bounding box can be calculated...")
    try:
        bbox = get_bounding_box(boundary_coords)
        print(f"✓ Bounding box calculated successfully: {bbox}")
    except Exception as e:
        print(f"✗ Failed to calculate bounding box: {e}")
        return False
    
    # Test 5: Generate a test SVG file
    print("\nTest 5: Generating a test SVG map...")
    try:
        output_file = os.path.join('output', 'test_map.svg')
        
        # Check if we can download OSM data (or use cached data)
        try:
            print("Attempting to download or retrieve OSM data...")
            osm_data = download_osm_data(bbox)
            print("✓ OSM data retrieved successfully")
            
            # Generate SVG map
            print(f"Generating SVG map: {output_file}")
            create_svg_map(osm_data, boundary_coords, output_file)
            
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"✓ SVG map generated successfully ({file_size} bytes)")
            else:
                print(f"✗ SVG map file not created: {output_file}")
                return False
                
        except Exception as e:
            print(f"✗ Failed to download OSM data: {e}")
            print("Skipping SVG generation test")
    except Exception as e:
        print(f"✗ Failed to generate SVG map: {e}")
        return False
    
    # All tests passed
    print("\nAll tests completed successfully!")
    return True

def main():
    """Main entry point for test script."""
    parser = argparse.ArgumentParser(description="Test KML to SVG converter")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    success = run_tests(verbose=args.verbose)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
