#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OSM Data Module

This module handles fetching and caching OpenStreetMap data.
"""

import os
import json
import requests
from config_parser import load_config

# Load configuration
config = load_config()
OSM_CONFIG = config.get('osm', {})

def get_cache_key(bbox):
    """
    Generate a cache key from bounding box coordinates.
    
    Args:
        bbox (tuple): (min_lon, min_lat, max_lon, max_lat)
        
    Returns:
        str: Cache key string
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    return f"{min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}"

def load_osm_cache():
    """
    Load cached OSM data from file.
    
    Returns:
        dict: Dictionary of cached OSM data
    """
    cache_dir = OSM_CONFIG.get('cache_dir', 'osm-cache')
    cache_file = OSM_CONFIG.get('cache_file', 'osmdata.json')
    
    try:
        cache_path = os.path.join(cache_dir, cache_file)
        with open(cache_path, 'r') as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_osm_cache(cache):
    """
    Save OSM data to cache file.
    
    Args:
        cache (dict): Dictionary of OSM data to cache
    """
    cache_dir = OSM_CONFIG.get('cache_dir', 'osm-cache')
    cache_file = OSM_CONFIG.get('cache_file', 'osmdata.json')
    
    # Ensure the cache directory exists
    os.makedirs(cache_dir, exist_ok=True)
    
    cache_path = os.path.join(cache_dir, cache_file)
    with open(cache_path, 'w') as f:
        json.dump(cache, f, indent=2)

def download_osm_data(bbox):
    """
    Download OSM data for the specified area, using cache when available.
    
    Args:
        bbox (tuple): (min_lon, min_lat, max_lon, max_lat)
        
    Returns:
        bytes: OSM XML data
        
    Raises:
        ValueError: If bounding box coordinates are invalid
        Exception: If OSM data download fails
    """
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
    overpass_url = OSM_CONFIG.get('overpass_url', 'https://overpass-api.de/api/interpreter')
    timeout = OSM_CONFIG.get('timeout', 30)
    
    overpass_query = f"""
    [out:xml][timeout:{timeout}];
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
