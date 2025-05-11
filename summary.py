#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KML to SVG Converter - Summary and Examples

This script provides information about the refactored KML to SVG converter project
and examples of how to use it.
"""

import sys
import os
from config_parser import load_config

def print_section(title):
    """Print a section title."""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60)

def print_subsection(title):
    """Print a subsection title."""
    print("\n" + "-" * 50)
    print(f" {title} ".center(50, "-"))
    print("-" * 50)

def main():
    """Main function to display project information and examples."""
    print_section("KML to SVG Converter - Project Summary")
    
    print("\nThis project converts KML files (Google Maps format) to SVG maps with additional")
    print("features from OpenStreetMap data. The code has been refactored into a modular")
    print("structure for better maintainability and extensibility.")
    
    print_subsection("Project Structure")
    print("\nThe project has been restructured into the following modules:")
    print("\n  - main.py             - Main entry point script")
    print("  - kml-svg.py          - Backward compatibility wrapper")
    print("  - kml_parser.py       - KML file parsing functionality")
    print("  - geo_utils.py        - Geographic utilities")
    print("  - osm_data.py         - OpenStreetMap data fetching and caching")
    print("  - svg_styling.py      - SVG element styling based on OSM tags")
    print("  - coord_transform.py  - Coordinate transformation utilities")
    print("  - svg_generator.py    - SVG map generation")
    print("  - config_parser.py    - Configuration file parsing")
    print("  - test.py             - Test script to verify functionality")
    
    print_subsection("Configuration")
    
    config = load_config()
    svg_config = config.get('svg', {})
    default_width = svg_config.get('width', 800)
    default_height = svg_config.get('height', 600)
    
    print("\nThe project uses a configuration file located at config/config.yaml.")
    print("\nDefault SVG dimensions:")
    print(f"  - Width:  {default_width} pixels")
    print(f"  - Height: {default_height} pixels")
    
    print_subsection("Usage Examples")
    
    print("\n1. Basic usage:")
    print("   python main.py -k \"kml/Test territoire.kml\" -o \"output/map.svg\"")
    
    print("\n2. Custom dimensions:")
    print("   python main.py -k \"kml/Test territoire.kml\" -o \"output/map.svg\" -w 1200 -h 900")
    
    print("\n3. Use custom configuration file:")
    print("   python main.py -k \"kml/Test territoire.kml\" -o \"output/map.svg\" -c \"path/to/custom_config.yaml\"")
    
    print("\n4. Run tests:")
    print("   python test.py -v")
    
    print("\n5. Backward compatibility (using the original script name):")
    print("   python kml-svg.py -k \"kml/Test territoire.kml\" -o \"output/map.svg\"")
    
    print_section("Get Started")
    
    # Check if we have sample KML files to suggest
    kml_dir = os.path.join(os.getcwd(), 'kml')
    if os.path.exists(kml_dir):
        kml_files = [f for f in os.listdir(kml_dir) if f.endswith('.kml')]
        if kml_files:
            print("\nTry converting one of these sample KML files:")
            for i, kml_file in enumerate(kml_files[:5], 1):  # Show up to 5 samples
                print(f"  {i}. {kml_file}")
            print("\nExample command:")
            print(f"  python main.py -k \"kml/{kml_files[0]}\" -o \"output/map.svg\"")
    
    print("\nFor more information, see the README.md file.")

if __name__ == "__main__":
    main()
