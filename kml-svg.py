#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import math
import xml.etree.ElementTree as ET
import requests
import svgwrite
import json
from shapely.geometry import Point, Polygon, LineString
from pykml import parser
from lxml import etree

def parse_kml(kml_file):
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
    polygon = Polygon(boundary_coords)
    line = LineString(points)
    return polygon.intersects(line)

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
        if tags.get("landuse") == "allotment":
            base_style = {
                "fill": "#E8F4D9",  # Vert pâle pour les jardins/allotments
                "stroke": "#D6E6C3",  # Contour plus foncé
                "stroke-width": 1,
                "opacity": 0.7,
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
    """Convert geographic coordinates to SVG coordinates."""
    min_lon, min_lat, max_lon, max_lat = bbox
    
    # Validate input coordinates
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        print(f"Warning: Potentially invalid coordinates: lat={lat}, lon={lon}")
    
    # Calculate width/height ratio to maintain proportions
    lon_range = max_lon - min_lon
    lat_range = max_lat - min_lat
    
    if lon_range == 0 or lat_range == 0:
        raise ValueError("Invalid bounding box dimensions: zero range")
    
    try:
        x = (lon - min_lon) / lon_range * svg_width
        y = (1 - (lat - min_lat) / lat_range) * svg_height
        return x, y
    except Exception as e:
        print(f"Error converting coordinates: lat={lat}, lon={lon}, bbox={bbox}")
        raise ValueError(f"Error converting coordinates: {str(e)}")

def calculate_road_segments(way_nodes, bbox, svg_width, svg_height):
    """Calculate road segments and their angles in SVG coordinates."""
    if len(way_nodes) < 2:
        return 0, [], None
    
    # Convert geographic coordinates to SVG coordinates
    points = []
    for lon, lat in way_nodes:
        x, y = lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height)
        points.append((x, y))
    
    # Calculate the middle segment
    mid_idx = len(points) // 2
    if mid_idx > 0:
        # Use the segment containing the midpoint for angle calculation
        start = points[mid_idx - 1]
        end = points[mid_idx]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        angle = math.degrees(math.atan2(dy, dx))
        
        # Normalize angle to -90 to 90 degrees to avoid upside-down text
        if angle < -90:
            angle += 180
        elif angle > 90:
            angle -= 180
        
        return angle, points, points[mid_idx]
    
    return 0, points, points[0]

def project_point_to_line(point, line_start, line_end):
    """Project a point onto a line segment, returning the projected point."""
    px, py = point
    ax, ay = line_start
    bx, by = line_end
    
    # Vector from line start to point
    apx = px - ax
    apy = py - ay
    
    # Vector from line start to line end
    abx = bx - ax
    aby = by - ay
    
    # Length of line squared
    ab2 = abx * abx + aby * aby
    
    if ab2 == 0:
        return line_start
    
    # Normalized dot product to get projection ratio
    t = max(0, min(1, (apx * abx + apy * aby) / ab2))
    
    return (ax + t * abx, ay + t * aby)

def find_road_center_in_boundary(way_nodes, boundary_coords, bbox, svg_width, svg_height):
    """Find the best center point for road label within the boundary."""
    if len(way_nodes) < 2:
        return None, 0, None
    
    # Convert all points to SVG coordinates and geographic points
    svg_points = []
    geo_points = []
    for lon, lat in way_nodes:
        x, y = lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height)
        svg_points.append((x, y))
        geo_points.append((lon, lat))
    
    # Create boundary polygon and road line
    boundary_poly = Polygon(boundary_coords)
    road_line = LineString(geo_points)
    
    # Get the intersection with the boundary
    if boundary_poly.intersects(road_line):
        intersection = boundary_poly.intersection(road_line)
        
        # Get the center point of the intersection
        center_geo = list(intersection.centroid.coords)[0]
        center_x, center_y = lat_lon_to_xy(center_geo[1], center_geo[0], bbox, svg_width, svg_height)
        center_point = (center_x, center_y)
        
        # Find the segment that's closest to the center point
        min_dist = float('inf')
        best_segment = None
        projected_point = None
        
        for i in range(len(svg_points) - 1):
            p1, p2 = svg_points[i], svg_points[i + 1]
            
            # Project center point onto this segment
            proj = project_point_to_line(center_point, p1, p2)
            
            # Calculate distance from center to projection
            dist = ((center_x - proj[0])**2 + (center_y - proj[1])**2)**0.5
            
            if dist < min_dist:
                min_dist = dist
                best_segment = (p1, p2)
                projected_point = proj
        
        if best_segment and projected_point:
            # Calculate angle from the best segment
            dx = best_segment[1][0] - best_segment[0][0]
            dy = best_segment[1][1] - best_segment[0][1]
            angle = math.degrees(math.atan2(dy, dx))
            
            # Normalize angle to -90 to 90 degrees
            if angle < -90:
                angle += 180
            elif angle > 90:
                angle -= 180
            
            return projected_point, angle, best_segment
    
    return None, 0, None

def create_svg_map(osm_data, boundary_coords, output_file, svg_width=800, svg_height=600):
    """Crée un fichier SVG de la carte."""
    root = ET.fromstring(osm_data)
    
    # Extraire les nœuds et les chemins
    nodes = {}
    ways = []
    
    # Collecter tous les nœuds
    for node in root.findall(".//node"):
        node_id = node.get("id")
        lat = float(node.get("lat"))
        lon = float(node.get("lon"))
        nodes[node_id] = (lon, lat)
    
    # Collecter tous les ways et leurs tags
    for way in root.findall(".//way"):
        way_id = way.get("id")
        way_nodes = []
        tags = {}
        
        for tag in way.findall("./tag"):
            k = tag.get("k")
            v = tag.get("v")
            tags[k] = v
        
        for nd in way.findall("./nd"):
            ref = nd.get("ref")
            if ref in nodes:
                way_nodes.append(nodes[ref])
        
        if way_nodes:
            # Only add ways that are inside or intersect with boundary
            if is_line_in_boundary(way_nodes, boundary_coords):
                ways.append((way_nodes, tags))

    # Calculer la boîte englobante
    bbox = get_bounding_box(boundary_coords)
    
    # Créer le SVG
    dwg = svgwrite.Drawing(output_file, profile='tiny', size=(svg_width, svg_height))
    
    # Créer les groupes pour les différentes couches
    background_group = dwg.g(id="background")
    water_group = dwg.g(id="water")
    landuse_group = dwg.g(id="landuse")
    buildings_group = dwg.g(id="buildings")
    road_casings_group = dwg.g(id="road-casings")
    roads_group = dwg.g(id="roads")
    boundary_group = dwg.g(id="boundary")  # New group for KML boundary
    labels_group = dwg.g(id="labels")
    
    # Fond blanc
    background_group.add(dwg.rect(insert=(0, 0), size=(svg_width, svg_height), fill='#F5F5F5'))
    
    # Trier les ways par type pour un rendu correct
    ways.sort(key=lambda x: (
        "highway" in x[1],  # Routes en dernier
        "building" in x[1],  # Bâtiments avant les routes
        "waterway" in x[1] or "natural" == "water",  # Eau en premier
        "landuse" in x[1] or "leisure" in x[1]  # Utilisation des terres après l'eau
    ))
    
    # Dessiner tous les ways avec leurs styles appropriés
    for way_nodes, tags in ways:
        style = get_way_style(tags, True)  # Always true since we filtered earlier
        
        if style:
            points = [lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height) 
                     for lon, lat in way_nodes]
            
            if style.get("type") == "road":
                if style.get("casing"):
                    casing = dwg.polyline(
                        points=points,
                        fill="none",
                        stroke=style["casing-color"],
                        stroke_width=style["casing-width"],
                        stroke_linecap="round",
                        stroke_linejoin="round",
                        opacity=style["opacity"]
                    )
                    road_casings_group.add(casing)
                
                road = dwg.polyline(
                    points=points,
                    fill="none",
                    stroke=style["stroke"],
                    stroke_width=style["stroke-width"],
                    stroke_linecap="round",
                    stroke_linejoin="round",
                    opacity=style["opacity"]
                )
                roads_group.add(road)
            
            elif style.get("type") == "polygon":
                polygon = dwg.polygon(
                    points=points,
                    fill=style["fill"],
                    stroke=style["stroke"],
                    stroke_width=style["stroke-width"],
                    opacity=style["opacity"]
                )
                
                if style.get("symbol") == "P":
                    # Calculate center point for parking symbol
                    center_x = sum(p[0] for p in points) / len(points)
                    center_y = sum(p[1] for p in points) / len(points)
                    
                    # Add parking symbol
                    parking_symbol = dwg.text(
                        "P",
                        insert=(center_x, center_y + 4),
                        font_size=12,
                        font_family="Arial",
                        font_weight="bold",
                        fill="#666666",
                        text_anchor="middle"
                    )
                    labels_group.add(parking_symbol)
                
                if "building" in tags:
                    buildings_group.add(polygon)
                elif "waterway" in tags or tags.get("natural") == "water":
                    water_group.add(polygon)
                else:
                    landuse_group.add(polygon)
    
    # First, collect all segments for each road
    road_segments = {}
    for way_nodes, tags in ways:
        if "name" in tags and "highway" in tags:
            road_name = tags["name"]
            highway_type = tags["highway"]
            
            if road_name not in road_segments:
                road_segments[road_name] = {
                    'segments': [],
                    'highway_type': highway_type,
                    'priority': 1 if highway_type in ["motorway", "trunk", "primary"] else (
                        2 if highway_type in ["secondary", "tertiary"] else 3
                    )
                }
            
            road_segments[road_name]['segments'].extend(way_nodes)
    
    # Now process each road as a whole
    names_dict = {}
    for road_name, road_info in road_segments.items():
        if road_info['segments']:
            # Find center point for the entire road
            center_point, angle, segment = find_road_center_in_boundary(
                road_info['segments'], boundary_coords, bbox, svg_width, svg_height
            )
            
            if center_point:
                names_dict[road_name] = {
                    'name': road_name,
                    'highway_type': road_info['highway_type'],
                    'priority': road_info['priority'],
                    'angle': angle,
                    'center': center_point,
                    'segment': segment
                }

    # Convert dictionary to list and sort by priority
    names = sorted(names_dict.values(), key=lambda x: x['priority'])
    
    # Add road names
    for name_info in names:
        x, y = name_info['center']
        angle = name_info['angle']
        
        font_size = 10 if name_info['highway_type'] in ["motorway", "trunk", "primary"] else (
            8 if name_info['highway_type'] in ["secondary", "tertiary"] else 7
        )
        
        # Create rotation transform with correct y-coordinate
        transform = f"rotate({angle}, {x}, {y})"
        
        text_bg = dwg.text(
            name_info['name'],
            insert=(x, y),
            font_size=font_size,
            font_family="Arial",
            fill="white",
            stroke="white",
            stroke_width=3,
            text_anchor="middle",
            transform=transform
        )
        
        text = dwg.text(
            name_info['name'],
            insert=(x, y),
            font_size=font_size,
            font_family="Arial",
            fill="#404040",
            text_anchor="middle",
            transform=transform
        )
        
        labels_group.add(text_bg)
        labels_group.add(text)

    # Draw KML boundary with black border
    boundary_points = [lat_lon_to_xy(lat, lon, bbox, svg_width, svg_height) 
                      for lon, lat in boundary_coords]
    boundary = dwg.polygon(
        points=boundary_points,
        fill="none",
        stroke="black",
        stroke_width=2,
        opacity=1
    )
    boundary_group.add(boundary)
    
    # Ajouter les groupes dans l'ordre correct
    dwg.add(background_group)
    dwg.add(water_group)
    dwg.add(landuse_group)
    dwg.add(buildings_group)
    dwg.add(road_casings_group)
    dwg.add(roads_group)
    dwg.add(boundary_group)  # Add boundary after roads but before labels
    dwg.add(labels_group)
    
    # Sauvegarder le SVG
    dwg.save()
    print(f"Carte SVG générée avec succès: {output_file}")

def main():
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

if __name__ == "__main__":
    main()