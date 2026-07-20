import os
import json
import pandas as pd
import geopandas as gpd
import rasterio
 
from fastapi import UploadFile
 
from schemas.feature_schema import FeatureCreate
from services.feature_service import create_feature
from services.case_service import create_untitled_case
from services.layer_service import create_layer
 
 
# ===================================================
# UPLOAD FOLDER
# ===================================================
 
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
 
 
# ===================================================
# PROCESS UPLOADED FILE
# ===================================================
 
async def process_upload(case_id: int, file: UploadFile):
 
    file_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )
 
    with open(file_path, "wb") as f:
        f.write(await file.read())
 
    extension = file.filename.split(".")[-1].lower()
 
    # -------------------------------------------------
 
    if extension == "csv":
 
        data = extract_csv(file_path)
 
    elif extension == "kml":
 
        data = extract_kml(
            case_id=case_id,
            file_path=file_path,
            filename=file.filename
        )
 
    elif extension in ["tif", "tiff"]:
 
        data = extract_tiff(file_path)
 
    else:
 
        return {
            "success": False,
            "message": f"Unsupported file type : {extension}"
        }
 
    return {
        "success": True,
        "case_id": case_id,
        "filename": file.filename,
        "file_type": extension,
        "data": data
    }
 
 
# ===================================================
# CSV
# ===================================================
 
def extract_csv(file_path):
 
    df = pd.read_csv(file_path)
 
    return {
        "columns": list(df.columns),
        "total_rows": len(df),
        "rows": df.to_dict(orient="records")
    }
 
 
def strip_point(point):
    return point[:2]
 
 
def remove_z_coordinates(geometry):
 
    geometry = geometry.copy()
 
    geom_type = geometry["type"]
 
    if geom_type == "Point":
        geometry["coordinates"] = strip_point(geometry["coordinates"])
 
    elif geom_type == "LineString":
        geometry["coordinates"] = [
            strip_point(point)
            for point in geometry["coordinates"]
        ]
 
    elif geom_type == "Polygon":
        geometry["coordinates"] = [
            [
                strip_point(point)
                for point in ring
            ]
            for ring in geometry["coordinates"]
        ]
 
    elif geom_type == "MultiPoint":
        geometry["coordinates"] = [
            strip_point(point)
            for point in geometry["coordinates"]
        ]
 
    elif geom_type == "MultiLineString":
        geometry["coordinates"] = [
            [
                strip_point(point)
                for point in line
            ]
            for line in geometry["coordinates"]
        ]
 
    elif geom_type == "MultiPolygon":
        geometry["coordinates"] = [
            [
                [
                    strip_point(point)
                    for point in ring
                ]
                for ring in polygon
            ]
            for polygon in geometry["coordinates"]
        ]
 
    return geometry
 
# ===================================================
# KML IMPORT
# ===================================================
 
def extract_kml(case_id, file_path, filename):
 
    try:
 
        gdf = gpd.read_file(file_path)
 
        # ---------------------------------------------
        # Always use default case if frontend sends null
        # ---------------------------------------------
 
        if case_id is None:
            case_id = create_untitled_case()
 
        # ---------------------------------------------
        # Create ONE layer for this uploaded file
        # ---------------------------------------------
 
        layer = {
            "case_id": case_id,
            "name": os.path.splitext(filename)[0],
            "layer_type": "import",
            "visible": True
        }
 
        layer_response = create_layer(layer)
 
        layer_id = layer_response["layer_id"]
 
        imported = 0
 
                # ---------------------------------------------
        # Import every geometry
        # ---------------------------------------------
 
        for _, row in gdf.iterrows():
 
            if row.geometry is None:
                continue
 
            geometry = remove_z_coordinates(
                row.geometry.__geo_interface__
            )
 
            feature = FeatureCreate(
                case_id=case_id,
                layer_id=layer_id,
                name=row.get("Name") or row.get("name") or f"Feature {imported + 1}",
                geometry=geometry,
                geometry_type=geometry["type"],
                properties=row.drop(labels="geometry").fillna("").to_dict(),
                created_by=None
            )
 
            create_feature(feature)
 
            imported += 1
 
        return {
            "success": True,
            "layer_id": layer_id,
            "layer_name": layer["name"],
            "imported_features": imported
        }
 
    except Exception as e:
 
        return {
            "success": False,
            "error": str(e)
        }
 
# ===================================================
# TIFF
# ===================================================
 
def extract_tiff(file_path):
 
    try:
 
        with rasterio.open(file_path) as src:
 
            bounds = src.bounds
 
            return {
 
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "crs": str(src.crs),
 
                "bounds": {
 
                    "left": bounds.left,
                    "bottom": bounds.bottom,
                    "right": bounds.right,
                    "top": bounds.top
                }
 
            }
 
    except Exception as e:
 
        return {
            "success": False,
            "error": str(e)
        }