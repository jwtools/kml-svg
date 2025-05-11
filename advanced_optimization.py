#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Advanced Geometry Optimization Demo for KML to SVG Converter

This script demonstrates advanced usage of the geometry optimization capabilities
by showcasing different optimization techniques and their effects on various types
of KML data. It generates multiple SVG outputs with different optimization settings
to allow visual comparison.
"""

import os
import time
import argparse
import logging
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Polygon, LineString

from kml_parser import parse_kml, extract_kml_styles
from geo_utils import get_bounding_box
from svg_generator import create_svg_map
from geometry_optimizer import simplify_polygon, simplify_linestring, adaptive_simplify

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_advanced_optimization(kml_file, output_dir="output"):
    """
    Demonstrate advanced optimization techniques with different settings.
    Generates multiple SVG outputs and performance comparison charts.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Load KML data without optimization first (as baseline)
    logger.info(f"Loading KML file: {kml_file}")
    baseline_data = parse_kml(kml_file, optimize=False)
    boundary_coords = baseline_data['boundary']
    baseline_features = baseline_data['features']
    bbox = get_bounding_box(boundary_coords)
    
    # Extract feature counts by type
    feature_types = {}
    for feature in baseline_features:
        ftype = feature.get('type')
        feature_types[ftype] = feature_types.get(ftype, 0) + 1
    
    # Load KML styles
    kml_styles = extract_kml_styles(kml_file)
    
    # Calculate baseline metrics
    baseline_vertices = count_vertices(baseline_features)
    logger.info(f"KML contains {len(baseline_features)} features with {baseline_vertices} total vertices")
    logger.info(f"Feature distribution: {feature_types}")
    
    # Define optimization scenarios to test
    scenarios = [
        {
            "name": "No Optimization",
            "optimize": False,
            "simplify_tolerance": 0.0,
            "max_features": None,
            "file_suffix": "baseline"
        },
        {
            "name": "Light Optimization",
            "optimize": True,
            "simplify_tolerance": 0.000005,
            "max_features": None,
            "file_suffix": "light_opt"
        },
        {
            "name": "Medium Optimization",
            "optimize": True,
            "simplify_tolerance": 0.00002,
            "max_features": None,
            "file_suffix": "medium_opt"
        },
        {
            "name": "Aggressive Optimization",
            "optimize": True,
            "simplify_tolerance": 0.0001,
            "max_features": None,
            "file_suffix": "aggressive_opt"
        }
    ]
    
    # Run all scenarios and collect results
    results = []
    
    for scenario in scenarios:
        logger.info(f"\nRunning scenario: {scenario['name']}")
        
        start_time = time.time()
        kml_data = parse_kml(
            kml_file, 
            optimize=scenario["optimize"],
            simplify_tolerance=scenario["simplify_tolerance"],
            max_features=scenario["max_features"]
        )
        
        # Use the same boundary for all scenarios
        optimized_features = kml_data['features']
        
        # Calculate metrics
        optimized_vertices = count_vertices(optimized_features)
        reduction_percent = ((baseline_vertices - optimized_vertices) / baseline_vertices * 100) if baseline_vertices > 0 else 0
        
        # Generate SVG file
        output_file = os.path.join(output_dir, f"map_{scenario['file_suffix']}.svg")
        create_svg_map(
            osm_data=None,  # Skip OSM data for this test
            boundary_coords=boundary_coords,
            output_file=output_file,
            svg_width=800,
            svg_height=600,
            kml_features=optimized_features,
            kml_styles=kml_styles,
            skip_labels=False
        )
        
        total_time = time.time() - start_time
        file_size = os.path.getsize(output_file) / 1024  # KB
        
        # Collect results
        results.append({
            "name": scenario["name"],
            "vertices": optimized_vertices,
            "reduction": reduction_percent,
            "time": total_time,
            "file_size": file_size,
            "output_file": output_file
        })
        
        logger.info(f"Completed {scenario['name']}:")
        logger.info(f"  - Vertices: {optimized_vertices} ({reduction_percent:.2f}% reduction)")
        logger.info(f"  - Processing time: {total_time:.2f} seconds")
        logger.info(f"  - SVG size: {file_size:.2f} KB")
        logger.info(f"  - SVG file: {output_file}")
    
    # Generate comparison chart
    generate_comparison_chart(results, output_dir)
    
    # Print summary table
    logger.info("\n=== Optimization Comparison Summary ===")
    logger.info(f"{'Scenario':<25} {'Vertices':<10} {'Reduction':<12} {'Time (s)':<10} {'Size (KB)':<10}")
    logger.info("-" * 70)
    for r in results:
        logger.info(f"{r['name']:<25} {r['vertices']:<10} {r['reduction']:.2f}%{'':<5} {r['time']:.2f}{'':<5} {r['file_size']:.2f}")

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

def generate_comparison_chart(results, output_dir):
    """Generate a chart comparing the optimization results."""
    try:
        # Extract data for charting
        names = [r['name'] for r in results]
        vertices = [r['vertices'] for r in results]
        times = [r['time'] for r in results]
        sizes = [r['file_size'] for r in results]
        
        # Create the figure with multiple subplots
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12))
        
        # Vertex count subplot
        ax1.bar(names, vertices, color='skyblue')
        ax1.set_title('Total Vertices by Optimization Level')
        ax1.set_ylabel('Vertex Count')
        ax1.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Processing time subplot
        ax2.bar(names, times, color='lightgreen')
        ax2.set_title('Processing Time by Optimization Level')
        ax2.set_ylabel('Time (seconds)')
        ax2.grid(axis='y', linestyle='--', alpha=0.7)
        
        # File size subplot
        ax3.bar(names, sizes, color='salmon')
        ax3.set_title('SVG File Size by Optimization Level')
        ax3.set_ylabel('Size (KB)')
        ax3.grid(axis='y', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        # Save the chart
        chart_path = os.path.join(output_dir, 'optimization_comparison.png')
        plt.savefig(chart_path)
        logger.info(f"Comparison chart saved to: {chart_path}")
        
        plt.close(fig)
    except Exception as e:
        logger.error(f"Error generating comparison chart: {e}")
        logger.info("Continuing without chart generation.")

def demonstrate_simplification_levels(kml_file, feature_index=0, output_dir="output"):
    """
    Demonstrate different simplification levels on a single feature.
    This generates visualizations showing the effect of different
    simplification tolerances on a specific feature.
    """
    try:
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Load KML data
        kml_data = parse_kml(kml_file, optimize=False)
        features = kml_data['features']
        
        # Ensure the requested feature index exists
        if feature_index >= len(features):
            logger.error(f"Feature index {feature_index} out of range (max: {len(features)-1})")
            return
            
        # Get the selected feature
        feature = features[feature_index]
        feature_type = feature.get('type')
        feature_name = feature.get('name', f"Feature #{feature_index}")
        
        if feature_type not in ['Polygon', 'LineString']:
            logger.error(f"Feature must be Polygon or LineString, but got {feature_type}")
            return
            
        logger.info(f"Demonstrating simplification levels on {feature_type} '{feature_name}'")
        
        # Extract coordinates
        original_coords = feature.get('coordinates', [])
        original_count = len(original_coords)
        
        # Define tolerance levels to test
        tolerance_levels = [0.000001, 0.000005, 0.00001, 0.00005, 0.0001, 0.0005]
        
        # Apply simplification at each level
        results = []
        for tolerance in tolerance_levels:
            if feature_type == 'Polygon':
                simplified_coords = simplify_polygon(original_coords, tolerance=tolerance)
            else:  # LineString
                simplified_coords = simplify_linestring(original_coords, tolerance=tolerance)
                
            simplified_count = len(simplified_coords)
            reduction = (original_count - simplified_count) / original_count * 100
            
            results.append({
                'tolerance': tolerance,
                'vertices': simplified_count,
                'reduction': reduction
            })
            
            logger.info(f"Tolerance {tolerance:.6f}: {simplified_count} vertices ({reduction:.2f}% reduction)")
        
        # Generate visualization
        try:
            # Create plot
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # Plot vertex count
            x = range(len(tolerance_levels))
            ax.plot(x, [r['vertices'] for r in results], 'o-', color='blue', linewidth=2, markersize=8)
            
            # Plot reduction percentage on secondary y-axis
            ax2 = ax.twinx()
            ax2.plot(x, [r['reduction'] for r in results], 's-', color='red', linewidth=2, markersize=8)
            
            # Set labels and title
            ax.set_xlabel('Simplification Tolerance')
            ax.set_ylabel('Vertex Count', color='blue')
            ax2.set_ylabel('Reduction (%)', color='red')
            ax.set_title(f'Simplification Effect on {feature_type} "{feature_name}" ({original_count} original vertices)')
            
            # Set x-tick labels to tolerance values
            ax.set_xticks(x)
            ax.set_xticklabels([f"{t:.6f}" for t in tolerance_levels], rotation=45)
            
            # Set grid
            ax.grid(True, linestyle='--', alpha=0.7)
            
            # Add legend
            ax.legend(['Vertex Count'], loc='upper left')
            ax2.legend(['Reduction %'], loc='upper right')
            
            plt.tight_layout()
            
            # Save the plot
            chart_path = os.path.join(output_dir, 'simplification_levels.png')
            plt.savefig(chart_path)
            logger.info(f"Simplification levels chart saved to: {chart_path}")
            
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"Error generating simplification levels chart: {e}")
            
    except Exception as e:
        logger.error(f"Error demonstrating simplification levels: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Advanced Geometry Optimization Demo")
    parser.add_argument("-k", "--kml", required=True, help="Path to input KML file")
    parser.add_argument("-o", "--output-dir", default="output", help="Output directory for generated files")
    parser.add_argument("--feature-index", type=int, default=0, 
                        help="Index of the feature to use for simplification level demonstration")
    parser.add_argument("--simplify-demo", action="store_true", 
                        help="Run simplification level demonstration on a single feature")
    
    args = parser.parse_args()
    
    if args.simplify_demo:
        demonstrate_simplification_levels(args.kml, args.feature_index, args.output_dir)
    else:
        run_advanced_optimization(args.kml, args.output_dir)
