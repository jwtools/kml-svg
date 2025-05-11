#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration Module

This module handles loading and parsing of configuration settings.
"""

import os
import yaml

# Default configuration values
DEFAULT_CONFIG = {
    'osm': {
        'overpass_url': 'https://overpass-api.de/api/interpreter',
        'timeout': 30,
        'cache_dir': 'osm-cache',
        'cache_file': 'osmdata.json'
    },
    'svg': {
        'width': 800,
        'height': 600,
        'padding': 0.05
    }
}

def load_config(config_path=None):
    """
    Load configuration from YAML file with fallback to default values.
    
    Args:
        config_path (str, optional): Path to configuration YAML file. If None, 
                                     will try to load from default location.
    
    Returns:
        dict: Configuration dictionary
    """
    if config_path is None:
        # Try to find config in standard locations
        locations = [
            os.path.join(os.getcwd(), 'config', 'config.yaml'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yaml')
        ]
        for loc in locations:
            if os.path.exists(loc):
                config_path = loc
                break
    
    config = DEFAULT_CONFIG.copy()
    
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
                
            # Update the default config with values from file
            if yaml_config:
                # Merge nested dictionaries
                for key, value in yaml_config.items():
                    if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                        config[key].update(value)
                    else:
                        config[key] = value
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
    
    return config

def get_style(config, feature_type, subtype=None):
    """
    Get styling for a specific feature type from config.
    
    Args:
        config (dict): Configuration dictionary
        feature_type (str): Type of feature (building, road, landuse, etc.)
        subtype (str, optional): Subtype of feature (primary, secondary, etc.)
    
    Returns:
        dict: Style dictionary or empty dict if not found
    """
    try:
        if 'styles' not in config:
            return {}
            
        if feature_type not in config['styles']:
            return {}
            
        style = config['styles'][feature_type]
        
        if subtype and isinstance(style, dict) and subtype in style:
            return style[subtype]
            
        return style
    except Exception:
        return {}
