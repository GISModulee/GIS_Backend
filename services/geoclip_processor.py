import hashlib
import io
import os
import tempfile

from PIL import Image, ExifTags

from services.geoclip_model import geo_model
from utils.logger import logger

class FileUtils:
    @staticmethod
    def get_file_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

class ExifExtractor:
    @staticmethod
    def _dms_to_decimal(dms, ref: str) -> float:
        degrees = float(dms[0])
        minutes = float(dms[1]) / 60.0
        seconds = float(dms[2]) / 3600.0
        decimal = degrees + minutes + seconds
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal

    @staticmethod
    def extract_from_bytes(content: bytes) -> dict | None:
        try:
            img = Image.open(io.BytesIO(content))
            exif_data = img._getexif()
            if not exif_data:
                logger.debug("No EXIF data found in image bytes.")
                return None

            exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_data.items()}
            gps_info = exif.get("GPSInfo")
            if not gps_info:
                logger.debug("No GPS tag in EXIF.")
                return None

            gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info.items()}
            lat = ExifExtractor._dms_to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
            lon = ExifExtractor._dms_to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])

            logger.info(f"EXIF GPS extracted: lat={lat:.6f}, lon={lon:.6f}")
            return {"lat": lat, "lon": lon, "score": 1.0}

        except KeyError as e:
            logger.warning(f"Missing GPS EXIF key: {e}")
            return None
        except Exception as e:
            logger.warning(f"EXIF extraction failed, falling back to GeoCLIP: {e}", exc_info=True)
            return None

class ImageProcessor:
    @staticmethod
    def process_and_predict(content: bytes, extension: str, top_k: int | None = None) -> dict:
        exif_gps = ExifExtractor.extract_from_bytes(content)
        if exif_gps:
            logger.info("Using EXIF source.")
            return {"source": "exif", "predictions": [exif_gps]}

        logger.info(f"No EXIF GPS — falling back to GeoCLIP model | top_k={top_k}")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            predictions = geo_model.predict(tmp_path, top_k=top_k)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.debug(f"Temp file cleaned up: {tmp_path}")

        cleaned = [
            {"lat": float(p["lat"]), "lon": float(p["lon"]), "score": float(p["score"])}
            for p in predictions
        ]
        logger.info(f"GeoCLIP returned {len(cleaned)} predictions.")
        return {"source": "model", "predictions": cleaned}
