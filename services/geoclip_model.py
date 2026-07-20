import threading
from geoclip import GeoCLIP
from utils.config import settings
from utils.logger import logger


class GeoCLIPService:
    def __init__(self):
        self.model = None
        self._loaded = False
        self._lock = threading.Lock()

    def load_model(self):
        """
        Load GeoCLIP model at startup. Called once from main.py lifespan.
        predict() will raise RuntimeError if called before this.
        """
        if self._loaded:
            logger.warning("GeoCLIP model already loaded — skipping.")
            return

        logger.info("Loading GeoCLIP model...")
        try:
            self.model = GeoCLIP()
            self._loaded = True
            logger.info("GeoCLIP model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load GeoCLIP model: {e}", exc_info=True)
            raise RuntimeError("GeoCLIP model initialization failed.") from e

    def predict(self, image_path: str) -> list[dict]:
        """
        Run inference. top_k is read from settings.
        Raises RuntimeError if model not loaded or inference fails.
        """
        if not self._loaded or self.model is None:
            raise RuntimeError(
                "GeoCLIP model is not loaded. Ensure load_model() is called at startup."
            )

        logger.info(f"Running GeoCLIP inference | path={image_path} | top_k={settings.GEOCLIP_TOP_K}")
        try:
            with self._lock:
                top_pred_gps, top_pred_prob = self.model.predict(
                    image_path, top_k=settings.GEOCLIP_TOP_K
                )
        except Exception as e:
            logger.error(f"GeoCLIP inference failed: {e}", exc_info=True)
            raise RuntimeError("GeoCLIP inference failed.") from e

        predictions = [
            {
                "lat": float(top_pred_gps[i][0]),
                "lon": float(top_pred_gps[i][1]),
                "score": float(top_pred_prob[i]),
            }
            for i in range(len(top_pred_gps))
        ]

        logger.info(f"GeoCLIP returned {len(predictions)} predictions.")
        return predictions

geo_model = GeoCLIPService()
