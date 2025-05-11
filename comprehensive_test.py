#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Comprehensive Test Script for KML to SVG Converter

This script tests all the major features of the KML to SVG converter,
including geometry optimization, smart label placement, and error handling.
It generates a report of test results along with performance metrics.
"""

import os
import sys
import time
import logging
import argparse
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

from kml_parser import parse_kml, extract_kml_styles
from geo_utils import get_bounding_box
from osm_data import download_osm_data
from svg_generator import create_svg_map
from geometry_optimizer import simplify_polygon, simplify_linestring

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_comprehensive_test(kml_file, output_dir="output/test_results"):
    """
    Run a comprehensive test of the KML to SVG converter.
    
    Args:
        kml_file (str): Path to the KML file to test
        output_dir (str): Directory to save test output
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a timestamp for unique filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create log file
    log_file = os.path.join(output_dir, f"test_log_{timestamp}.txt")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    logger.info(f"Starting comprehensive test with KML file: {kml_file}")
    logger.info(f"Test results will be saved to: {output_dir}")
    
    results = {}
    
    # Test 1: Basic conversion without optimization
    logger.info("Test 1: Basic conversion without optimization")
    try:
        start_time = time.time()
        kml_data = parse_kml(kml_file, optimize=False)
        boundary_coords = kml_data['boundary']
        kml_features = kml_data['features']
        kml_styles = extract_kml_styles(kml_file)
        
        # Calculate stats
        feature_count = len(kml_features)
        vertex_count = count_vertices(kml_features)
        
        # Generate SVG
        basic_output = os.path.join(output_dir, f"basic_conversion_{timestamp}.svg")
        bbox = get_bounding_box(boundary_coords)
        create_svg_map(
            osm_data=None,
            boundary_coords=boundary_coords,
            output_file=basic_output,
            svg_width=800,
            svg_height=600,
            kml_features=kml_features,
            kml_styles=kml_styles,
            skip_labels=False
        )
        
        basic_time = time.time() - start_time
        basic_size = os.path.getsize(basic_output) / 1024  # KB
        
        results['basic'] = {
            'success': True,
            'time': basic_time,
            'features': feature_count,
            'vertices': vertex_count,
            'file_size': basic_size,
            'output_file': basic_output
        }
        
        logger.info(f"Basic conversion successful:")
        logger.info(f"  - Time: {basic_time:.2f} seconds")
        logger.info(f"  - Features: {feature_count}")
        logger.info(f"  - Vertices: {vertex_count}")
        logger.info(f"  - File size: {basic_size:.2f} KB")
        logger.info(f"  - Output: {basic_output}")
        
    except Exception as e:
        logger.error(f"Basic conversion failed: {e}")
        logger.error(traceback.format_exc())
        results['basic'] = {
            'success': False,
            'error': str(e)
        }
    
    # Test 2: Optimized conversion
    logger.info("\nTest 2: Optimized conversion")
    try:
        start_time = time.time()
        kml_data = parse_kml(kml_file, optimize=True, simplify_tolerance=0.00001)
        boundary_coords = kml_data['boundary']
        kml_features = kml_data['features']
        kml_styles = extract_kml_styles(kml_file)
        
        # Calculate stats
        opt_feature_count = len(kml_features)
        opt_vertex_count = count_vertices(kml_features)
        
        # Generate SVG
        opt_output = os.path.join(output_dir, f"optimized_conversion_{timestamp}.svg")
        create_svg_map(
            osm_data=None,
            boundary_coords=boundary_coords,
            output_file=opt_output,
            svg_width=800,
            svg_height=600,
            kml_features=kml_features,
            kml_styles=kml_styles,
            skip_labels=False
        )
        
        opt_time = time.time() - start_time
        opt_size = os.path.getsize(opt_output) / 1024  # KB
        
        # Calculate improvements
        if results['basic']['success']:
            time_improvement = (results['basic']['time'] - opt_time) / results['basic']['time'] * 100
            vertex_reduction = (results['basic']['vertices'] - opt_vertex_count) / results['basic']['vertices'] * 100
            size_reduction = (results['basic']['file_size'] - opt_size) / results['basic']['file_size'] * 100
        else:
            time_improvement = vertex_reduction = size_reduction = 0
        
        results['optimized'] = {
            'success': True,
            'time': opt_time,
            'features': opt_feature_count,
            'vertices': opt_vertex_count,
            'file_size': opt_size,
            'output_file': opt_output,
            'time_improvement': time_improvement,
            'vertex_reduction': vertex_reduction,
            'size_reduction': size_reduction
        }
        
        logger.info(f"Optimized conversion successful:")
        logger.info(f"  - Time: {opt_time:.2f} seconds")
        logger.info(f"  - Features: {opt_feature_count}")
        logger.info(f"  - Vertices: {opt_vertex_count}")
        logger.info(f"  - File size: {opt_size:.2f} KB")
        logger.info(f"  - Output: {opt_output}")
        
        if results['basic']['success']:
            logger.info(f"Improvements:")
            logger.info(f"  - Processing time: {time_improvement:.2f}% faster")
            logger.info(f"  - Vertex count: {vertex_reduction:.2f}% reduction")
            logger.info(f"  - File size: {size_reduction:.2f}% smaller")
            
    except Exception as e:
        logger.error(f"Optimized conversion failed: {e}")
        logger.error(traceback.format_exc())
        results['optimized'] = {
            'success': False,
            'error': str(e)
        }
    
    # Test 3: Aggressive optimization
    logger.info("\nTest 3: Aggressive optimization")
    try:
        start_time = time.time()
        kml_data = parse_kml(kml_file, optimize=True, simplify_tolerance=0.0001, max_features=100)
        boundary_coords = kml_data['boundary']
        kml_features = kml_data['features']
        kml_styles = extract_kml_styles(kml_file)
        
        # Calculate stats
        agg_feature_count = len(kml_features)
        agg_vertex_count = count_vertices(kml_features)
        
        # Generate SVG
        agg_output = os.path.join(output_dir, f"aggressive_optimization_{timestamp}.svg")
        create_svg_map(
            osm_data=None,
            boundary_coords=boundary_coords,
            output_file=agg_output,
            svg_width=800,
            svg_height=600,
            kml_features=kml_features,
            kml_styles=kml_styles,
            skip_labels=False
        )
        
        agg_time = time.time() - start_time
        agg_size = os.path.getsize(agg_output) / 1024  # KB
        
        # Calculate improvements compared to basic
        if results['basic']['success']:
            time_improvement = (results['basic']['time'] - agg_time) / results['basic']['time'] * 100
            vertex_reduction = (results['basic']['vertices'] - agg_vertex_count) / results['basic']['vertices'] * 100
            size_reduction = (results['basic']['file_size'] - agg_size) / results['basic']['file_size'] * 100
        else:
            time_improvement = vertex_reduction = size_reduction = 0
        
        results['aggressive'] = {
            'success': True,
            'time': agg_time,
            'features': agg_feature_count,
            'vertices': agg_vertex_count,
            'file_size': agg_size,
            'output_file': agg_output,
            'time_improvement': time_improvement,
            'vertex_reduction': vertex_reduction,
            'size_reduction': size_reduction
        }
        
        logger.info(f"Aggressive optimization successful:")
        logger.info(f"  - Time: {agg_time:.2f} seconds")
        logger.info(f"  - Features: {agg_feature_count}")
        logger.info(f"  - Vertices: {agg_vertex_count}")
        logger.info(f"  - File size: {agg_size:.2f} KB")
        logger.info(f"  - Output: {agg_output}")
        
        if results['basic']['success']:
            logger.info(f"Improvements vs. basic:")
            logger.info(f"  - Processing time: {time_improvement:.2f}% faster")
            logger.info(f"  - Vertex count: {vertex_reduction:.2f}% reduction")
            logger.info(f"  - File size: {size_reduction:.2f}% smaller")
            
    except Exception as e:
        logger.error(f"Aggressive optimization failed: {e}")
        logger.error(traceback.format_exc())
        results['aggressive'] = {
            'success': False,
            'error': str(e)
        }
    
    # Test 4: Full map with OSM data
    logger.info("\nTest 4: Full map with OSM data")
    try:
        start_time = time.time()
        kml_data = parse_kml(kml_file, optimize=True)
        boundary_coords = kml_data['boundary']
        kml_features = kml_data['features']
        kml_styles = extract_kml_styles(kml_file)
        
        # Get bounding box
        bbox = get_bounding_box(boundary_coords)
        
        # Download OSM data
        logger.info("Downloading or retrieving cached OSM data...")
        osm_data = download_osm_data(bbox)
        
        # Generate SVG
        full_output = os.path.join(output_dir, f"full_map_{timestamp}.svg")
        create_svg_map(
            osm_data=osm_data,
            boundary_coords=boundary_coords,
            output_file=full_output,
            svg_width=800,
            svg_height=600,
            kml_features=kml_features,
            kml_styles=kml_styles,
            skip_labels=False
        )
        
        full_time = time.time() - start_time
        full_size = os.path.getsize(full_output) / 1024  # KB
        
        results['full_map'] = {
            'success': True,
            'time': full_time,
            'features': len(kml_features),
            'vertices': count_vertices(kml_features),
            'file_size': full_size,
            'output_file': full_output
        }
        
        logger.info(f"Full map with OSM data successful:")
        logger.info(f"  - Time: {full_time:.2f} seconds")
        logger.info(f"  - Features: {len(kml_features)}")
        logger.info(f"  - File size: {full_size:.2f} KB")
        logger.info(f"  - Output: {full_output}")
            
    except Exception as e:
        logger.error(f"Full map with OSM data failed: {e}")
        logger.error(traceback.format_exc())
        results['full_map'] = {
            'success': False,
            'error': str(e)
        }
    
    # Test 5: Error handling
    logger.info("\nTest 5: Error handling (intentional errors)")
    
    # 5.1 Test with invalid KML file
    try:
        # Create a temp file with invalid KML content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as tmp:
            tmp.write("<kml><Invalid>This is not valid KML</Invalid></kml>")
            invalid_kml_file = tmp.name
        
        try:
            parse_kml(invalid_kml_file)
            results['error_handling_invalid_kml'] = {
                'success': False,
                'notes': "Failed to catch invalid KML"
            }
        except Exception as e:
            # This is expected to fail
            results['error_handling_invalid_kml'] = {
                'success': True,
                'notes': "Correctly caught invalid KML"
            }
            logger.info(f"Error handling test (invalid KML): Passed")
        
        # Clean up
        os.unlink(invalid_kml_file)
        
    except Exception as e:
        logger.error(f"Error handling test (invalid KML) setup failed: {e}")
    
    # 5.2 Test with boundary-less KML
    try:
        # Create a temp file with KML that has no polygons
        with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as tmp:
            tmp.write("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <Placemark>
    <name>Point</name>
    <Point>
      <coordinates>-122.0,37.0</coordinates>
    </Point>
  </Placemark>
</Document>
</kml>""")
            no_boundary_kml = tmp.name
        
        try:
            parse_kml(no_boundary_kml)
            results['error_handling_no_boundary'] = {
                'success': False,
                'notes': "Failed to catch KML without polygon boundary"
            }
        except ValueError as e:
            if "No polygon found" in str(e):
                results['error_handling_no_boundary'] = {
                    'success': True,
                    'notes': "Correctly caught KML without polygon boundary"
                }
                logger.info(f"Error handling test (no boundary): Passed")
            else:
                results['error_handling_no_boundary'] = {
                    'success': False,
                    'notes': f"Wrong error: {str(e)}"
                }
        except Exception as e:
            results['error_handling_no_boundary'] = {
                'success': False,
                'notes': f"Wrong exception type: {type(e).__name__}"
            }
        
        # Clean up
        os.unlink(no_boundary_kml)
        
    except Exception as e:
        logger.error(f"Error handling test (no boundary) setup failed: {e}")
    
    # Generate summary report
    report_file = os.path.join(output_dir, f"test_report_{timestamp}.txt")
    with open(report_file, 'w') as f:
        f.write("KML to SVG Converter - Comprehensive Test Report\n")
        f.write("==============================================\n\n")
        f.write(f"Test date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"KML file: {os.path.abspath(kml_file)}\n\n")
        
        # Basic conversion results
        f.write("Test 1: Basic Conversion\n")
        f.write("-----------------------\n")
        if results['basic']['success']:
            f.write(f"Status: Success\n")
            f.write(f"Processing time: {results['basic']['time']:.2f} seconds\n")
            f.write(f"Feature count: {results['basic']['features']}\n")
            f.write(f"Vertex count: {results['basic']['vertices']}\n")
            f.write(f"Output file size: {results['basic']['file_size']:.2f} KB\n")
            f.write(f"Output file: {os.path.abspath(results['basic']['output_file'])}\n")
        else:
            f.write(f"Status: Failed\n")
            f.write(f"Error: {results['basic'].get('error', 'Unknown error')}\n")
        f.write("\n")
        
        # Optimized conversion results
        f.write("Test 2: Optimized Conversion\n")
        f.write("---------------------------\n")
        if results['optimized']['success']:
            f.write(f"Status: Success\n")
            f.write(f"Processing time: {results['optimized']['time']:.2f} seconds\n")
            f.write(f"Feature count: {results['optimized']['features']}\n")
            f.write(f"Vertex count: {results['optimized']['vertices']}\n")
            f.write(f"Output file size: {results['optimized']['file_size']:.2f} KB\n")
            f.write(f"Output file: {os.path.abspath(results['optimized']['output_file'])}\n")
            
            if results['basic']['success']:
                f.write("\nImprovements vs. Basic Conversion:\n")
                f.write(f"Time improvement: {results['optimized']['time_improvement']:.2f}%\n")
                f.write(f"Vertex reduction: {results['optimized']['vertex_reduction']:.2f}%\n")
                f.write(f"File size reduction: {results['optimized']['size_reduction']:.2f}%\n")
        else:
            f.write(f"Status: Failed\n")
            f.write(f"Error: {results['optimized'].get('error', 'Unknown error')}\n")
        f.write("\n")
        
        # Aggressive optimization results
        f.write("Test 3: Aggressive Optimization\n")
        f.write("------------------------------\n")
        if results['aggressive']['success']:
            f.write(f"Status: Success\n")
            f.write(f"Processing time: {results['aggressive']['time']:.2f} seconds\n")
            f.write(f"Feature count: {results['aggressive']['features']}\n")
            f.write(f"Vertex count: {results['aggressive']['vertices']}\n")
            f.write(f"Output file size: {results['aggressive']['file_size']:.2f} KB\n")
            f.write(f"Output file: {os.path.abspath(results['aggressive']['output_file'])}\n")
            
            if results['basic']['success']:
                f.write("\nImprovements vs. Basic Conversion:\n")
                f.write(f"Time improvement: {results['aggressive']['time_improvement']:.2f}%\n")
                f.write(f"Vertex reduction: {results['aggressive']['vertex_reduction']:.2f}%\n")
                f.write(f"File size reduction: {results['aggressive']['size_reduction']:.2f}%\n")
        else:
            f.write(f"Status: Failed\n")
            f.write(f"Error: {results['aggressive'].get('error', 'Unknown error')}\n")
        f.write("\n")
        
        # Full map with OSM data results
        f.write("Test 4: Full Map with OSM Data\n")
        f.write("----------------------------\n")
        if results['full_map']['success']:
            f.write(f"Status: Success\n")
            f.write(f"Processing time: {results['full_map']['time']:.2f} seconds\n")
            f.write(f"Feature count: {results['full_map']['features']}\n")
            f.write(f"Output file size: {results['full_map']['file_size']:.2f} KB\n")
            f.write(f"Output file: {os.path.abspath(results['full_map']['output_file'])}\n")
        else:
            f.write(f"Status: Failed\n")
            f.write(f"Error: {results['full_map'].get('error', 'Unknown error')}\n")
        f.write("\n")
        
        # Error handling tests
        f.write("Test 5: Error Handling\n")
        f.write("---------------------\n")
        
        # Invalid KML test
        f.write("5.1 Invalid KML: ")
        if results.get('error_handling_invalid_kml', {}).get('success', False):
            f.write("Passed\n")
        else:
            f.write("Failed\n")
        f.write(f"Notes: {results.get('error_handling_invalid_kml', {}).get('notes', 'No notes')}\n\n")
        
        # No boundary test
        f.write("5.2 No Boundary: ")
        if results.get('error_handling_no_boundary', {}).get('success', False):
            f.write("Passed\n")
        else:
            f.write("Failed\n")
        f.write(f"Notes: {results.get('error_handling_no_boundary', {}).get('notes', 'No notes')}\n\n")
        
        # Overall summary
        f.write("\nOverall Results\n")
        f.write("--------------\n")
        success_count = sum(1 for k, v in results.items() if v.get('success', False))
        test_count = len(results)
        f.write(f"Tests passed: {success_count} / {test_count}\n")
        
        if results['basic']['success'] and results['optimized']['success'] and results['aggressive']['success']:
            f.write("\nOptimization Performance Summary\n")
            f.write(f"Standard optimization vertex reduction: {results['optimized']['vertex_reduction']:.2f}%\n")
            f.write(f"Aggressive optimization vertex reduction: {results['aggressive']['vertex_reduction']:.2f}%\n")
            f.write(f"Standard optimization file size reduction: {results['optimized']['size_reduction']:.2f}%\n")
            f.write(f"Aggressive optimization file size reduction: {results['aggressive']['size_reduction']:.2f}%\n")
    
    logger.info(f"\nTest report saved to: {report_file}")
    return report_file, results

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
    parser = argparse.ArgumentParser(description="Comprehensive test for the KML to SVG converter")
    parser.add_argument("-k", "--kml", required=True, help="Path to input KML file for testing")
    parser.add_argument("-o", "--output-dir", default="output/test_results", 
                        help="Output directory for test results (default: output/test_results)")
    
    args = parser.parse_args()
    
    report_file, results = run_comprehensive_test(args.kml, args.output_dir)
    print(f"\nTest complete! Report saved to: {report_file}")
