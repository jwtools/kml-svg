# KML to SVG Converter

This tool converts KML files (Google Maps format) to SVG maps with additional features from OpenStreetMap data.

## Features

- Convert KML files to SVG maps with extensive feature support:
  - Points
  - LineStrings
  - Polygons
  - MultiGeometry
- Extract and apply KML styling (colors, line widths, icons)
- Include OpenStreetMap data (roads, buildings, parks, etc.)
- Smart label placement with overlap avoidance
- Caches OSM data for faster subsequent runs
- Optimized for large KML files with automatic simplification
- Advanced geometry optimization for complex features
- Proper boundary detection and coordinate transformation
- Advanced styling options for different feature types

## Project Structure

The project has a modular structure:

- `main.py` - Main entry point script
- `kml-svg.py` - Backward compatibility wrapper around the new modular implementation
- `kml_parser.py` - KML file parsing and style extraction
- `geo_utils.py` - Geographic utilities (bounding box, boundary tests, feature area calculation)
- `geometry_optimizer.py` - Geometry simplification and optimization for complex features
- `osm_data.py` - OpenStreetMap data fetching and caching
- `svg_styling.py` - SVG element styling based on OSM tags and KML styles
- `coord_transform.py` - Coordinate transformation and color conversion
- `svg_generator.py` - SVG map generation with layered rendering
- `config/` - Configuration files
- `kml/` - Input KML files
- `output/` - Generated SVG maps
- `osm-cache/` - Cached OSM data

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the tool with a KML file:

```bash
python main.py -k "kml/your-file.kml" -o "output/map.svg"
```

Or use the original script (which now delegates to the modular implementation):

```bash
python kml-svg.py -k "kml/your-file.kml" -o "output/map.svg"
```

### Command-line Arguments

```
usage: main.py [-h] -k KML [-o OUTPUT] [-w WIDTH] [--height HEIGHT] [-c CONFIG] [-v] [--no-osm]
               [--no-labels] [--debug-bounds] [--optimize] [--simplify SIMPLIFY] [--max-features MAX_FEATURES]
               
SVG Map Generator from KML files
options:
  -h, --help            show this help message and exit
  -k KML, --kml KML     Path to input KML file
  -o OUTPUT, --output OUTPUT
                        Path to output SVG file (default: carte_generee.svg)
  -w WIDTH, --width WIDTH
                        Width of SVG canvas (default: 800)
  --height HEIGHT       Height of SVG canvas (default: 600)
  -c CONFIG, --config CONFIG
                        Path to custom config file
  -v, --verbose         Enable verbose output
  --no-osm              Skip OSM data download (use only KML features)
  --no-labels           Skip rendering of text labels
  --debug-bounds        Add boundary visualization for debugging
  --optimize            Enable geometry optimization for complex features
  --simplify SIMPLIFY   Simplification tolerance for complex geometries (default: 0.00001)
  --max-features MAX_FEATURES
                        Maximum number of features to process from KML file
```

## Examples

1. Generate a map with default settings:
```bash
python main.py -k kml/territory.kml
```

2. Generate a map with custom dimensions and no OSM data:
```bash
python main.py -k kml/territory.kml -o custom_map.svg -w 1200 --height 800 --no-osm
```

3. Generate a debug map with boundary visualization:
```bash
python main.py -k kml/territory.kml --debug-bounds -v
```

4. Generate an optimized map with simplified geometries:
```bash
python main.py -k kml/large_complex_file.kml --optimize --simplify 0.00005
```

## Geometry Optimization

For large or complex KML files, the tool provides advanced geometry optimization capabilities:

- **Automatic Simplification**: Reduces the number of points in complex polygons and linestrings while maintaining visual fidelity
- **Adaptive Simplification**: Intelligently adjusts simplification levels based on feature complexity
- **Memory Optimization**: Special handling for very large KML files (>10MB)
- **Progress Reporting**: Shows progress indicators when parsing large files

### How Geometry Optimization Works

The optimization system uses several strategies to improve performance and reduce file size:

1. **Ramer-Douglas-Peucker Algorithm**: This algorithm simplifies geometries by removing points that don't contribute significantly to the shape. The tolerance parameter controls how aggressive the simplification is.

2. **Adaptive Tolerance**: For very complex geometries, the system can automatically adjust the tolerance level to target a specific number of vertices.

3. **Geometry Type-Specific Handling**: Different optimization strategies are applied to different geometry types (Polygon, LineString, Point, MultiGeometry).

4. **Topology Preservation**: The simplification process maintains the topological integrity of features, ensuring that simplified geometries don't self-intersect or overlap incorrectly.

5. **Memory-Efficient Processing**: For large files, features are processed in batches to minimize memory usage.

### Using Geometry Optimization

To enable geometry optimization:

```bash
python main.py -k kml/your-file.kml --optimize
```

Fine-tune the simplification level (higher values = more simplification):

```bash
python main.py -k kml/your-file.kml --optimize --simplify 0.00005
```

Limit the maximum number of features to process (useful for extremely large files):

```bash
python main.py -k kml/your-file.kml --optimize --max-features 1000
```

### Testing Optimization Performance

You can test the performance improvements of the geometry optimizer using the included test script:

```bash
python test_optimization.py -k kml/your-file.kml
```

This will generate both optimized and unoptimized versions of the SVG map and provide detailed performance metrics including:
- Vertex count reduction
- Processing time improvement
- SVG file size reduction

For very complex KML files, you can expect significant improvements in both processing time and file size.

### When to Use Optimization

- **Large KML Files (>10MB)**: Almost always beneficial, with minimal visual impact
- **Files with Complex Polygons**: Very effective for coastlines, administrative boundaries, and natural features with many vertices
- **Web Applications**: Recommended when the SVG will be served over the web to reduce transfer size
- **Limited Resources**: Essential when processing on systems with limited memory

### Advanced Optimization Options

The geometry optimizer provides several advanced options that can be configured in code:

```python
from kml_parser import parse_kml

# Basic optimization
kml_data = parse_kml("file.kml", optimize=True)

# Advanced optimization
kml_data = parse_kml(
    "file.kml",
    optimize=True,
    simplify_tolerance=0.00002,  # More aggressive simplification
    max_features=500             # Limit to 500 features
)
```

4. Process a large KML file with optimization:
```bash
python main.py -k kml/large_territory.kml --optimize --max-features 1000
```

5. Fine-tune simplification for very detailed KML:
```bash
python main.py -k kml/detailed_map.kml --optimize --simplify 0.000005
```

6. Run advanced optimization demo with comparison visualization:
```bash
python advanced_optimization.py -k kml/your-file.kml
```

7. Demonstrate different simplification levels on a specific feature:
```bash
python advanced_optimization.py -k kml/your-file.kml --simplify-demo --feature-index 2
```

## Optimization for Large Files

The script includes special optimizations for large KML files (>10MB):
- Feature limiting to prevent memory issues
- Polygon simplification for complex geometries
- Batch processing for better performance
- Memory usage optimizations
- Error handling with graceful degradation

## Testing and Performance Evaluation

Several test scripts are provided to help evaluate the performance and capabilities of the converter:

1. Basic test with the test.py script:
```bash
python test.py -k kml/your-file.kml
```

2. Optimization testing with performance metrics:
```bash
python test_optimization.py -k kml/your-file.kml
```

3. Advanced optimization comparisons with visualizations:
```bash
python advanced_optimization.py -k kml/your-file.kml
```

4. Comprehensive test suite (tests all features with detailed report):
```bash
python comprehensive_test.py -k kml/your-file.kml
```

The comprehensive test runs the converter with different optimization settings and evaluates:
- Performance metrics (processing time, memory usage)
- Geometry simplification effectiveness
- Error handling capabilities
- Label placement quality
- OSM data integration

A detailed test report is generated with comparisons between different optimization levels.

## Notes

- The first polygon in the KML file is used as the map boundary by default
- For best results, ensure KML files have proper styling information
- OSM data is cached to avoid excessive downloads
- Custom styles can be defined in configuration files

## License

[Your License Information]

## Authors

[Your Name]
