import threading
from geoclip import GeoCLIP
from utils.config import settings
from utils.logger import logger


class GeoCLIPService:
    def __init__(self):
        self.model = None
        self._loaded = False
        self._lock = threading.Lock()

    def _apply_transformers_compatibility(self):
        """Normalize CLIP image features across Transformers 4 and 5."""
        clip_model = self.model.image_encoder.CLIP
        original_get_image_features = clip_model.get_image_features

        def get_image_features_tensor(*args, **kwargs):
            output = original_get_image_features(*args, **kwargs)
            return getattr(output, "pooler_output", output)

        clip_model.get_image_features = get_image_features_tensor

    def load_model(self):
        if self._loaded:
            logger.warning("GeoCLIP model already loaded — skipping.")
            return

        logger.info("Loading GeoCLIP model...")
        try:
            self.model = GeoCLIP()
            self._apply_transformers_compatibility()
            self._loaded = True
            logger.info("GeoCLIP model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load GeoCLIP model: {e}", exc_info=True)
            raise RuntimeError("GeoCLIP model initialization failed.") from e

    def predict(self, image_path: str, top_k: int | None = None) -> list[dict]:
        if not self._loaded or self.model is None:
            raise RuntimeError(
                "GeoCLIP model is not loaded. Ensure load_model() is called at startup."
            )

        effective_top_k = top_k if top_k is not None else settings.GEOCLIP_TOP_K

        logger.info(f"Running GeoCLIP inference | path={image_path} | top_k={effective_top_k}")
        try:
            with self._lock:
                top_pred_gps, top_pred_prob = self.model.predict(
                    image_path, top_k=effective_top_k
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
