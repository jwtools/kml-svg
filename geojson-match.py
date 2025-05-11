import argparse
import gzip
import os
import shutil
import requests
import yaml
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from shapely.ops import nearest_points

# === Chargement configuration YAML ===
def load_config(config_file="config/config.yaml"):
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# === Téléchargement Cadastre si nécessaire ===
def download_cadastre_departements(departements, cache_dir, config):
    base_url = config["base_url"]
    file_template = config["file_template"]
    
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    for dept in departements:
        file_name = file_template.replace("{dep}", dept)
        file_url = f"{base_url}/{file_name}"
        local_gz_path = Path(cache_dir) / file_name
        local_json_path = local_gz_path.with_suffix('')  # .json sans .gz

        if local_json_path.exists():
            print(f"✅ {local_json_path} déjà présent.")
            continue

        if not local_gz_path.exists():
            print(f"⬇️ Téléchargement de {file_url}...")
            response = requests.get(file_url, stream=True)
            if response.status_code == 200:
                with open(local_gz_path, "wb") as f:
                    shutil.copyfileobj(response.raw, f)
                print(f"✅ Téléchargé : {local_gz_path}")
            else:
                print(f"❌ Impossible de télécharger {file_url} (HTTP {response.status_code})")
                continue

        # Décompression du .gz
        print(f"🛠 Décompression de {local_gz_path}...")
        with gzip.open(local_gz_path, 'rb') as f_in:
            with open(local_json_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"✅ Décompressé : {local_json_path}")

# === Chargement fichiers sources ===
def load_osm_data(osm_file):
    print(f"📥 Chargement OSM depuis {osm_file}")
    return gpd.read_file(osm_file)

def load_cadastre_data(cadastre_files):
    print(f"📥 Chargement Cadastre depuis {len(cadastre_files)} fichiers...")
    cadastres = [gpd.read_file(f) for f in cadastre_files]
    return gpd.GeoDataFrame(pd.concat(cadastres, ignore_index=True), crs=cadastres[0].crs)

def load_kml_bounding_box(kml_file):
    print(f"📦 Lecture de la bounding box depuis {kml_file}...")
    kml_gdf = gpd.read_file(kml_file)
    bbox = kml_gdf.total_bounds  # [minx, miny, maxx, maxy]
    return box(*bbox)

# === Filtrage sur une bbox
def filter_gdf_by_bbox(gdf, bbox_geom):
    bbox_gdf = gpd.GeoDataFrame(geometry=[bbox_geom], crs=gdf.crs)
    clipped = gpd.overlay(gdf, bbox_gdf, how="intersection")
    print(f"✂️ Réduit à {len(clipped)} entités après filtrage par BBOX")
    return clipped

# === Alignement géométrique
def align_geometries(new_gdf, reference_gdf, tolerance_m=2):
    print(f"🔧 Alignement géométrique des nouveaux bâtiments (tolérance {tolerance_m}m)...")
    
    # S'assurer que tout est en projection métrique (ex: EPSG:2154 pour France)
    if reference_gdf.crs.to_epsg() != 2154:
        reference_gdf = reference_gdf.to_crs(2154)
    if new_gdf.crs.to_epsg() != 2154:
        new_gdf = new_gdf.to_crs(2154)

    # Index spatial pour accélérer la recherche
    reference_sindex = reference_gdf.sindex

    def snap_geometry(geom):
        possible_matches_index = list(reference_sindex.intersection(geom.bounds))
        possible_matches = reference_gdf.iloc[possible_matches_index]

        nearest_geom = None
        min_distance = float("inf")
        
        for _, ref_geom in possible_matches.iterrows():
            dist = geom.distance(ref_geom.geometry)
            if dist < min_distance and dist < tolerance_m:
                nearest_geom = ref_geom.geometry
                min_distance = dist
        
        if nearest_geom is not None:
            # Snap to the nearest geometry (approximate center alignment)
            p1, p2 = nearest_points(geom.centroid, nearest_geom.centroid)
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            return shapely.affinity.translate(geom, xoff=dx, yoff=dy)
        else:
            return geom

    # Application alignement
    new_gdf["geometry"] = new_gdf["geometry"].apply(snap_geometry)
    return new_gdf

# === Fusion intelligente ===
def merge_osm_cadastre(osm_gdf, cadastre_gdf, bbox_geom=None, align=False, align_tolerance=2):
    print("🔄 Fusion des bâtiments OSM + Cadastre...")

    # Normalisation CRS
    if osm_gdf.crs != cadastre_gdf.crs:
        cadastre_gdf = cadastre_gdf.to_crs(osm_gdf.crs)

    # Option filtrage par bbox
    if bbox_geom:
        osm_gdf = filter_gdf_by_bbox(osm_gdf, bbox_geom)
        cadastre_gdf = filter_gdf_by_bbox(cadastre_gdf, bbox_geom)

    # Spatial join pour trouver les manquants
    joined = gpd.sjoin(cadastre_gdf, osm_gdf, how="left", predicate="intersects")

    missing_cadastre = joined[joined.index_right.isna()].drop(columns=["index_right"])

    print(f"✅ Bâtiments trouvés dans Cadastre non présents dans OSM : {len(missing_cadastre)}")
    
    # Alignement si demandé
    if align:
        missing_cadastre = align_geometries(missing_cadastre, osm_gdf, tolerance_m=align_tolerance)

    # Fusion
    merged = pd.concat([osm_gdf, missing_cadastre], ignore_index=True)
    return gpd.GeoDataFrame(merged, crs=osm_gdf.crs)

# === Export final ===
def export_data(gdf, output_file, export_format):
    if export_format.lower() == "geojson":
        gdf.to_file(output_file, driver="GeoJSON")
    elif export_format.lower() == "kml":
        gdf.to_file(output_file, driver="KML")
    else:
        raise ValueError(f"Format {export_format} non supporté")
    print(f"📦 Exporté dans {output_file}")

# === Parsing CLI ===
def parse_args():
    parser = argparse.ArgumentParser(description="Téléchargement, fusion et export des bâtiments OSM + Cadastre")
    parser.add_argument("--departements", type=str, required=True,
                        help="Liste des départements séparés par des virgules, ex: 78,95,92")
    parser.add_argument("--osm-file", type=str, required=True,
                        help="Chemin vers le fichier OSM (GeoJSON ou autre)")
    parser.add_argument("--output", type=str, required=True,
                        help="Nom du fichier de sortie final")
    parser.add_argument("--export-format", type=str, choices=["geojson", "kml"], required=True,
                        help="Format d'export : geojson ou kml")
    parser.add_argument("--cache-dir", type=str, default="./cache",
                        help="Répertoire de cache pour stocker les fichiers téléchargés")
    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Chemin vers le fichier de configuration YAML")
    parser.add_argument("--territory-kml", type=str,
                        help="Fichier KML pour limiter à une zone précise")
    parser.add_argument("--align", action="store_true",
                        help="Aligner les nouveaux bâtiments proches")
    parser.add_argument("--align-tolerance", type=float, default=2.0,
                        help="Tolérance d'alignement en mètres")
    return parser.parse_args()

# === Main principal ===
def main():
    args = parse_args()
    config = load_config(args.config)

    departements = [dep.strip() for dep in args.departements.split(",")]
    download_cadastre_departements(departements, args.cache_dir, config)

    # Chargement des fichiers
    cadastre_files = [Path(args.cache_dir) / f"cadastre-{dep}-batiments.json" for dep in departements]
    osm_gdf = load_osm_data(args.osm_file)
    cadastre_gdf = load_cadastre_data(cadastre_files)

    # Option bbox si fournie
    bbox_geom = None
    if args.territory_kml:
        bbox_geom = load_kml_bounding_box(args.territory_kml)

    # Fusion
    merged_gdf = merge_osm_cadastre(osm_gdf, cadastre_gdf, bbox_geom=bbox_geom,
                                    align=args.align, align_tolerance=args.align_tolerance)

    # Export
    export_data(merged_gdf, args.output, args.export_format)

if __name__ == "__main__":
    main()
