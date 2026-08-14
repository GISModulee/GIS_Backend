from services.upload_data.base_extractors import CSVExtractor, TiffExtractor
from services.upload_data.geojson_extractor import GeoJSONExtractor
from services.upload_data.kml_extractor import KMLExtractor

EXTRACTOR_REGISTRY = {
    "csv": CSVExtractor(),
    "kml": KMLExtractor(),
    "json": GeoJSONExtractor(),
    "geojson": GeoJSONExtractor(),
    "tif": TiffExtractor(),
    "tiff": TiffExtractor(),
}
