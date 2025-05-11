#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KML to SVG Converter

This script converts KML files to SVG maps with additional features from OpenStreetMap data.
This is now a wrapper around the modular implementation for backward compatibility.
"""

import sys

# Import functions from the modular implementation
from kml_parser import parse_kml
from geo_utils import get_bounding_box
from osm_data import download_osm_data
from svg_generator import create_svg_map

# The original functions are kept here as documentation but not used
def _original_parse_kml(kml_file):
    """Extraire un polygone à partir d'un fichier KML."""
    with open(kml_file, 'rb') as f:
        tree = parser.parse(f)
        root = tree.getroot()
        
    boundary_coords = []
    
    # Chercher les coordonnées dans les placemarks
    for placemark in root.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
        polygon = placemark.findall(".//{http://www.opengis.net/kml/2.2}Polygon")
        if polygon:
            coords_elem = polygon[0].findall(".//{http://www.opengis.net/kml/2.2}coordinates")
            if coords_elem:
                # Les coordonnées sont stockées comme une chaîne de caractères
                coords_str = coords_elem[0].text.strip()
                # Convertir la chaîne en liste de coordonnées
                coord_pairs = coords_str.split()
                for pair in coord_pairs:
                    lon, lat, _ = pair.split(',')  # Ignorer l'altitude
                    boundary_coords.append((float(lon), float(lat)))
                break  # On prend le premier polygone trouvé
    
    if not boundary_coords:
        raise ValueError("Aucun polygone trouvé dans le fichier KML")
    
    return boundary_coords

def get_bounding_box(coords, padding=0.001):  # Increased padding from 0.0005 to 0.001
    """Calcule la boîte englobante avec un peu de marge."""
    if not coords:
        raise ValueError("Empty coordinates list")
    
    try:
        min_lon = min(c[0] for c in coords) - padding
        max_lon = max(c[0] for c in coords) + padding
        min_lat = min(c[1] for c in coords) - padding
        max_lat = max(c[1] for c in coords) + padding
        
        print(f"Calculated bounding box: lon({min_lon}, {max_lon}), lat({min_lat}, {max_lat})")
        
        # Validate coordinates are within reasonable ranges
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and
                -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise ValueError(f"Invalid coordinate ranges in bounding box")
        
        return min_lon, min_lat, max_lon, max_lat
    except Exception as e:
        raise ValueError(f"Error calculating bounding box: {str(e)}")

def get_cache_key(bbox):
    """Generate a cache key from bbox coordinates."""
    min_lon, min_lat, max_lon, max_lat = bbox
    return f"{min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}"

def load_osm_cache():
    """Load cached OSM data from file."""
    try:
        cache_file = os.path.join('osm-cache', 'osmdata.json')
        with open(cache_file, 'r') as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_osm_cache(cache):
    """Save OSM data to cache file."""
    cache_file = os.path.join('osm-cache', 'osmdata.json')
    # Ensure the cache directory exists
    os.makedirs('osm-cache', exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(cache, f, indent=2)

def download_osm_data(bbox):
    """Télécharge les données OSM pour la zone spécifiée avec cache."""
    cache = load_osm_cache()
    cache_key = get_cache_key(bbox)
    
    # Check if we have cached data
    if cache_key in cache:
        print("Using cached OSM data...")
        return cache[cache_key].encode('utf-8')
    
    min_lon, min_lat, max_lon, max_lat = bbox
    
    # Validate bbox coordinates
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and
            -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ValueError(f"Invalid bounding box coordinates: {bbox}")
    
    print("Downloading OSM data (not in cache)...")
    overpass_url = "https://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:xml][timeout:30];
    (
        // Get allotments and paths in the immediate area
        way["landuse"="allotment"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["landuse"="allotments"]({min_lat},{min_lon},{max_lat},{max_lon});  // Add plural form
        way["highway"="footway"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["highway"="path"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["highway"="pedestrian"]({min_lat},{min_lon},{max_lat},{max_lon});
        
        // Get other features
        way["leisure"="park"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["landuse"="grass"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["landuse"="forest"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["landuse"="recreation_ground"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["natural"="wood"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["highway"]["highway"!~"footway|path|pedestrian"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["building"]({min_lat},{min_lon},{max_lat},{max_lon});
        way["amenity"="parking"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    (._;>;);
    out body qt;
    """
    
    response = requests.post(overpass_url, data=overpass_query)
    
    if response.status_code != 200:
        raise Exception(f"Error downloading OSM data: {response.status_code}")
    
    # Cache the response
    cache[cache_key] = response.text
    save_osm_cache(cache)
    
    return response.content

def is_point_in_boundary(point, boundary_coords):
    """Vérifie si un point est à l'intérieur du polygone de la frontière."""
    if not boundary_coords:
        return True
    polygon = Polygon(boundary_coords)
    return polygon.contains(Point(point))

def is_line_in_boundary(points, boundary_coords):
    """Vérifie si une ligne est à l'intérieur du polygone de la frontière."""
    if not boundary_coords:
        return True
    try:
        polygon = Polygon(boundary_coords)
        shape = Polygon(points) if len(points) > 2 else LineString(points)
        
        # Create a small buffer around both the polygon and the shape
        buffered_polygon = polygon.buffer(0.0002)  # About 22 meters at this latitude
        buffered_shape = shape.buffer(0.0002)
        
        # Check for intersection between the buffered geometries
        intersects = buffered_polygon.intersects(buffered_shape)
        
        # For potential allotments (anything between 2.179-2.181, 48.944-48.946), print debug info
        if any(2.179 <= p[0] <= 2.181 and 48.944 <= p[1] <= 48.946 for p in points):
            print(f"Boundary test for feature near allotment area:")
            print(f"- Points: {points[:2]}...")
            print(f"- Intersects with boundary: {intersects}")
            print(f"- Shape type: {'Polygon' if len(points) > 2 else 'LineString'}")
            print(f"- Area overlaps: {buffered_polygon.intersection(buffered_shape).area > 0}")
        
        return intersects
        
    except Exception as e:
        print(f"Warning: Boundary test failed: {e}")
        return True  # If test fails, include the feature rather than exclude it

def get_way_style(tags, is_inside=True):
    """Détermine le style de rendu en fonction des tags OSM et de la position."""
    base_style = None
    
    if "building" in tags:
        base_style = {
            "fill": "#E4E0D8",  # Beige clair pour les bâtiments
            "stroke": "#D4D0C8",
            "stroke-width": 1,
            "opacity": 0.9,
            "type": "polygon"
        }
    
    elif "amenity" in tags and tags["amenity"] == "parking":
        base_style = {
            "fill": "#F0F0F0",  # Gris très clair pour les parkings
            "stroke": "#D0D0D0",
            "stroke-width": 1,
            "opacity": 0.8,
            "type": "polygon",
            "symbol": "P"
        }
    
    elif "highway" in tags:
        highway_type = tags["highway"]
        style = {
            "type": "road",
            "casing": True
        }
        
        if highway_type in ["footway", "path", "pedestrian"]:
            style.update({
                "stroke": "#FFFFFF",  # Blanc pour les chemins piétons
                "stroke-width": 2,
                "casing-color": "#E0E0E0",
                "casing-width": 3,
                "opacity": 0.8,
                "is_path": True
            })
        elif highway_type in ["motorway", "trunk"]:
            style.update({
                "stroke": "#FFA07A",
                "stroke-width": 6,
                "casing-color": "#FF8C69",
                "casing-width": 8,
                "opacity": 1
            })
        elif highway_type in ["primary"]:
            style.update({
                "stroke": "#FCD68A",
                "stroke-width": 5,
                "casing-color": "#F4BC6C",
                "casing-width": 7,
                "opacity": 1
            })
        elif highway_type in ["secondary"]:
            style.update({
                "stroke": "#FAFAFA",
                "stroke-width": 4,
                "casing-color": "#E0E0E0",
                "casing-width": 6,
                "opacity": 1
            })
        else:
            style.update({
                "stroke": "#FFFFFF",
                "stroke-width": 2.5,
                "casing-color": "#E0E0E0",
                "casing-width": 3.5,
                "opacity": 0.8
            })
        base_style = style
    
    elif "waterway" in tags or tags.get("natural") == "water":
        base_style = {
            "fill": "#B3D1FF",
            "stroke": "#A1C3FF",
            "stroke-width": 1,
            "opacity": 0.6,
            "type": "polygon"
        }
    
    elif any(tag in tags for tag in ["leisure", "landuse", "natural"]):
        if tags.get("landuse") in ["allotment", "allotments"]:  # Handle both singular and plural
            base_style = {
                "fill": "#E8F4D9",  # Vert pâle pour les jardins/allotments
                "stroke": "#76A32D",  # Contour plus foncé et plus visible
                "stroke-width": 2,    # Border plus épais
                "opacity": 0.9,       # Opacité augmentée
                "type": "polygon"
            }
        elif tags.get("leisure") in ["park", "garden"] or tags.get("landuse") == "grass":
            base_style = {
                "fill": "#90EE90",  # Vert clair pour les espaces verts
                "stroke": "#7BE37B",
                "stroke-width": 1,
                "opacity": 0.7,
                "type": "polygon"
            }
        elif tags.get("natural") == "wood" or tags.get("landuse") in ["forest", "recreation_ground"]:
            base_style = {
                "fill": "#C6DFB3",  # Vert foncé pour les forêts
                "stroke": "#B5CE9F",
                "stroke-width": 1,
                "opacity": 0.6,
                "type": "polygon"
            }
    
    if base_style and not is_inside:
        if base_style.get("type") == "road":
            if "is_path" not in base_style:  # Keep footpaths visible
                base_style["stroke"] = "#CCCCCC"
                base_style["casing-color"] = "#BBBBBB"
                base_style["opacity"] = 0.5
        else:
            base_style["fill"] = "#EEEEEE"
            base_style["stroke"] = "#DDDDDD"
            base_style["opacity"] = 0.3
    
    return base_style

def lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height):
    """Convert geographic coordinates to SVG coordinates with improved aspect ratio handling."""
    min_lon, min_lat, max_lon, max_lat = bbox
    
    # Calculate width/height ratio to maintain proportions
    lon_range = max_lon - min_lon
    lat_range = max_lat - min_lat
    
    if lon_range == 0 or lat_range == 0:
        raise ValueError("Invalid bounding box dimensions: zero range")
    
    # Add padding to prevent features from touching the edges
    padding = 0.05  # 5% padding
    effective_width = svg_width * (1 - 2 * padding)
    effective_height = svg_height * (1 - 2 * padding)
    
    # Calculate scales that would preserve the aspect ratio in both directions
    scale_x = effective_width / lon_range
    scale_y = effective_height / lat_range
    
    # Use the smaller scale to ensure the map fits in both dimensions
    scale = min(scale_x, scale_y)
    
    # Calculate centered offsets
    x_offset = (svg_width - (lon_range * scale)) / 2
    y_offset = (svg_height - (lat_range * scale)) / 2
    
    # Transform coordinates
    x = x_offset + (lon - min_lon) * scale
    y = y_offset + (max_lat - lat) * scale  # Invert Y axis
    
    print(f"Transformed coordinates: ({lon}, {lat}) -> ({x}, {y})")
    return x, y

def calculate_label_corners(x, y, width, height, angle, buffer=5):
    """Calculate label corners with buffer."""
    cos_a = math.cos(math.radians(angle))
    sin_a = math.sin(math.radians(angle))
    w2 = (width/2 + buffer)
    h2 = (height/2 + buffer)
    return [
        (x - w2*cos_a + h2*sin_a, y - w2*sin_a - h2*cos_a),
        (x + w2*cos_a + h2*sin_a, y + w2*sin_a - h2*cos_a),
        (x + w2*cos_a - h2*sin_a, y + w2*sin_a + h2*cos_a),
        (x - w2*cos_a - h2*sin_a, y - w2*sin_a + h2*cos_a)
    ]

def project_point_to_line(point, line_start, line_end):
    """Project a point onto a line segment, returning the projected point."""
    px, py = point
    ax, ay = line_start
    bx, by = line_end
    apx = px - ax
    apy = py - ay
    abx = bx - ax
    aby = by - ay
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return line_start
    t = max(0, min(1, (apx * abx + apy * aby) / ab2))
    return (ax + t * abx, ay + t * aby)

def create_svg_map(osm_data, boundary_coords, output_file, svg_width=800, svg_height=600):
    """Crée un fichier SVG de la carte."""
    bbox = get_bounding_box(boundary_coords)
    
    # Initialize SVG with white background
    dwg = svgwrite.Drawing(output_file, (svg_width, svg_height))
    dwg.add(dwg.rect(insert=(0, 0), size=(svg_width, svg_height), fill='white'))
    
    # Create groups for different layers
    natural_group = dwg.g(id='natural-features')
    landuse_group = dwg.g(id='landuse')
    building_group = dwg.g(id='buildings')
    road_group = dwg.g(id='roads')
    path_group = dwg.g(id='paths')
    parking_group = dwg.g(id='parking')  # New group for parking
    text_group = dwg.g(id='text')
    
    # Initialize set to track added street names
    added_names = set()

    # Parse XML
    root = ET.fromstring(osm_data)
    nodes = {n.attrib['id']: (float(n.attrib['lat']), float(n.attrib['lon'])) 
             for n in root.findall('node')}
    
    # Collection pour regrouper les segments de routes par nom
    roads_by_name = {}
    
    # Premier passage : collecter toutes les routes
    for way in root.findall('way'):
        way_nodes = []
        tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall('tag')}
        road_name = tags.get('name')
        if 'highway' in tags and road_name:
            # Get coordinates for way
            for nd in way.findall('nd'):
                if nd.attrib['ref'] in nodes:
                    lat, lon = nodes[nd.attrib['ref']]
                    way_nodes.append((lon, lat))
            
            if way_nodes:
                if road_name not in roads_by_name:
                    roads_by_name[road_name] = {'segments': [], 'tags': tags, 'inside_segments': []}
                
                # Check if this segment is inside the boundary
                is_inside = is_line_in_boundary(way_nodes, boundary_coords)
                roads_by_name[road_name]['segments'].append(way_nodes)
                if is_inside:
                    roads_by_name[road_name]['inside_segments'].append(way_nodes)
    
    # Track label positions to prevent overlaps
    used_label_areas = []
    
    def check_label_collision(x, y, width, height, angle, buffer_distance=20):
        """Check if a label area collides with existing labels, with increased buffer"""
        # Create points for the four corners of the label area with buffer
        cos_a = math.cos(math.radians(angle))
        sin_a = math.sin(math.radians(angle))
        w2 = (width/2 + buffer_distance)
        h2 = (height/2 + buffer_distance)
        corners = [
            (x - w2*cos_a + h2*sin_a, y - w2*sin_a - h2*cos_a),
            (x + w2*cos_a + h2*sin_a, y + w2*sin_a - h2*cos_a),
            (x + w2*cos_a - h2*sin_a, y + w2*sin_a + h2*cos_a),
            (x - w2*cos_a - h2*sin_a, y - w2*sin_a + h2*cos_a)
        ]
        new_box = Polygon(corners)

        # Check collision with existing labels
        for existing_area in used_label_areas:
            if new_box.intersects(existing_area):
                return True
        return False

    # Ajouter les noms de rues pour tous les segments qui croisent la zone (pas seulement ceux entièrement à l'intérieur)
    for road_name, road_data in roads_by_name.items():
        if not road_data['segments']:
            continue
        
        # Merge all segments (not just inside ones)
        all_lines = [LineString(seg) for seg in road_data['segments'] if len(seg) > 1]
        if not all_lines:
            continue
        
        merged = linemerge(all_lines)
        
        # Clip to KML boundary with a buffer to ensure roads that touch the boundary are included
        boundary_poly = Polygon(boundary_coords).buffer(0.0005)  # Add small buffer
        
        if merged.is_empty:
            continue
            
        if merged.geom_type == 'MultiLineString':
            # Instead of taking just the longest segment, try to label each major segment
            segments_to_label = []
            for line in merged.geoms:
                if line.length > 0.0005:  # Only label segments of reasonable length
                    clipped = line.intersection(boundary_poly)
                    if not clipped.is_empty and clipped.length > 0:
                        segments_to_label.append(clipped)
        else:
            clipped = merged.intersection(boundary_poly)
            if not clipped.is_empty and clipped.length > 0:
                segments_to_label = [clipped]
        
        if not segments_to_label:
            continue
            
        # Try to label each segment
        for i, clipped in enumerate(segments_to_label):
            if clipped.is_empty or clipped.length == 0:
                continue
                
            # Skip if this is a repeat segment and we already labeled this road
            # Only allow multiple labels for the same road if they're sufficiently far apart
            if road_name in added_names and i > 0 and len(segments_to_label) < 3:
                continue
                
            # Find center point of clipped line
            center_geo = list(clipped.interpolate(0.5, normalized=True).coords)[0]
            center_x, center_y = lat_lon_to_xy(center_geo[1], center_geo[0], bbox, svg_width, svg_height)
            
            # Find angle at center
            if clipped.geom_type == 'LineString':
                svg_points = [lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height) for lon, lat in clipped.coords]
            else:
                # Handle other geometry types if needed
                continue
                
            min_dist = float('inf')
            best_angle = 0
            
            for i in range(len(svg_points) - 1):
                p1, p2 = svg_points[i], svg_points[i + 1]
                proj = project_point_to_line((center_x, center_y), p1, p2)
                dist = ((center_x - proj[0])**2 + (center_y - proj[1])**2)**0.5
                if dist < min_dist:
                    min_dist = dist
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    angle = math.degrees(math.atan2(dy, dx))
                    if angle < -90 or angle > 90:
                        dx = -dx
                        dy = -dy
                        angle = math.degrees(math.atan2(dy, dx))
                    best_angle = angle
            
            text_width = len(road_name) * 6
            text_height = 12
            
            # Try multiple positions along the road if center position has collision
            positions_to_try = [0.5, 0.3, 0.7, 0.2, 0.8]
            
            for pos in positions_to_try:
                alt_center_geo = list(clipped.interpolate(pos, normalized=True).coords)[0]
                alt_center_x, alt_center_y = lat_lon_to_xy(alt_center_geo[1], alt_center_geo[0], bbox, svg_width, svg_height)
                
                if not check_label_collision(alt_center_x, alt_center_y, text_width, text_height, best_angle):
                    text = dwg.text(road_name)
                    text['x'] = alt_center_x
                    text['y'] = alt_center_y
                    text['font-family'] = 'Arial, sans-serif'
                    text['font-size'] = '12px'
                    text['text-anchor'] = 'middle'
                    text['fill'] = '#333333'
                    if best_angle != 0:
                        text['transform'] = f'rotate({best_angle} {alt_center_x} {alt_center_y})'
                    text_group.add(text)
                    corners = calculate_label_corners(alt_center_x, alt_center_y, text_width, text_height, best_angle)
                    used_label_areas.append(Polygon(corners))
                    added_names.add(road_name)
                    break  # Found a good position, stop trying

    # Process ways for drawing roads and other features
    for way in root.findall('way'):
        way_nodes = []
        tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall('tag')}
        
        for nd in way.findall('nd'):
            if nd.attrib['ref'] in nodes:
                lat, lon = nodes[nd.attrib['ref']]
                way_nodes.append((lon, lat))
        
        if not way_nodes:
            continue
            
        is_inside = is_line_in_boundary(way_nodes, boundary_coords)
        style = get_way_style(tags, is_inside)
        if not style:
            continue
            
        svg_points = []
        for lon, lat in way_nodes:
            x, y = lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height)
            svg_points.append((x, y))
            
        if len(svg_points) < 2:
            continue
            
        if style.get('type') == 'road':
            if style.get('casing'):
                path = dwg.path(d=f'M {svg_points[0][0]},{svg_points[0][1]}')
                for x, y in svg_points[1:]:
                    path.push(f'L {x},{y}')
                path['stroke'] = style.get('casing-color', '#000000')
                path['stroke-width'] = style.get('casing-width', 1)
                path['fill'] = 'none'
                road_group.add(path)
            
            path = dwg.path(d=f'M {svg_points[0][0]},{svg_points[0][1]}')
            for x, y in svg_points[1:]:
                path.push(f'L {x},{y}')
            path['stroke'] = style.get('stroke', '#000000')
            path['stroke-width'] = style.get('stroke-width', 1)
            path['fill'] = 'none'
            path['stroke-opacity'] = style.get('opacity', 1)
            
            if style.get('is_path'):
                path_group.add(path)
            else:
                road_group.add(path)
                
        elif style.get('type') == 'polygon':
            poly_path = f'M {svg_points[0][0]},{svg_points[0][1]}'
            for x, y in svg_points[1:]:
                poly_path += f' L {x},{y}'
            poly_path += ' Z'
            
            path = dwg.path(d=poly_path)
            path['fill'] = style.get('fill', '#000000')
            path['stroke'] = style.get('stroke', 'none')
            path['stroke-width'] = style.get('stroke-width', 1)
            path['fill-opacity'] = style.get('opacity', 1)
            path['stroke-opacity'] = style.get('opacity', 1)
            
            if 'natural' in tags or tags.get('waterway'):
                natural_group.add(path)
            elif 'landuse' in tags or 'leisure' in tags:
                landuse_group.add(path)
            elif 'building' in tags:
                building_group.add(path)
            elif tags.get('amenity') == 'parking':
                parking_group.add(path)
                # Add parking symbol
                center_x = sum(p[0] for p in svg_points) / len(svg_points)
                center_y = sum(p[1] for p in svg_points) / len(svg_points)
                parking_text = dwg.text("P", insert=(center_x, center_y))
                parking_text['font-family'] = 'Arial, sans-serif'
                parking_text['font-size'] = '14px'
                parking_text['text-anchor'] = 'middle'
                parking_text['dominant-baseline'] = 'middle'
                parking_text['font-weight'] = 'bold'
                parking_text['fill'] = '#666666'
                parking_group.add(parking_text)
    
    # Add groups to SVG in correct order
    dwg.add(natural_group)
    dwg.add(landuse_group)
    dwg.add(parking_group)  # Add parking before buildings
    dwg.add(building_group)
    dwg.add(road_group)
    dwg.add(path_group)
    dwg.add(text_group)
      # Save the SVG file
    dwg.save()

def _original_main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Générateur de carte SVG à partir d'un fichier KML")
    parser.add_argument("-k", "--kml", required=True, help="Chemin vers le fichier KML d'entrée")
    parser.add_argument("-o", "--output", default="carte_generee.svg", help="Chemin vers le fichier SVG de sortie (défaut: carte_generee.svg)")
    
    args = parser.parse_args()
    
    kml_file = args.kml
    output_file = args.output
    
    try:
        # Extraire le polygone du fichier KML
        boundary_coords = parse_kml(kml_file)
        
        # Calculer la boîte englobante
        bbox = get_bounding_box(boundary_coords)
        
        # Télécharger les données OSM
        osm_data = download_osm_data(bbox)
        
        # Créer le SVG
        create_svg_map(osm_data, boundary_coords, output_file)
        
    except Exception as e:
        print(f"Erreur: {e}")
        sys.exit(1)

def main():
    """
    New main function that uses the modular implementation.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="SVG Map Generator from KML files")
    parser.add_argument("-k", "--kml", required=True, help="Path to input KML file")
    parser.add_argument("-o", "--output", default="carte_generee.svg", help="Path to output SVG file (default: carte_generee.svg)")
    
    args = parser.parse_args()
    
    kml_file = args.kml
    output_file = args.output
    
    try:
        # Extract polygon from KML file
        print(f"Parsing KML file: {kml_file}")
        boundary_coords = parse_kml(kml_file)
        
        # Calculate bounding box
        print("Calculating bounding box...")
        bbox = get_bounding_box(boundary_coords)
        
        # Download OSM data
        print("Downloading or retrieving cached OSM data...")
        osm_data = download_osm_data(bbox)
        
        # Create SVG
        print(f"Generating SVG map: {output_file}")
        create_svg_map(osm_data, boundary_coords, output_file)
        
        print(f"SVG map created successfully: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
