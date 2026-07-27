import magic

from utils.logger import logger
from utils.exceptions import BadRequestError, PayloadTooLargeError, UnsupportedMediaTypeError


ALLOWED_MIME_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
    "image/heic": ".heic",
    "image/heif": ".heic",
}

ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".heic"}


class FileValidator:
    @staticmethod
    def validate_extension(filename: str) -> str:
        if not filename:
            logger.warning("File validation rejected: filename missing")
            raise BadRequestError("Filename is missing.")

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning(f"File validation rejected: extension '{ext}' not allowed | filename={filename}")
            raise BadRequestError(
                f"Extension '{ext}' is not allowed. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            )
        return ext

    @staticmethod
    def validate_magic_bytes(content: bytes, filename: str) -> tuple[str, str]:
        try:
            detected_mime = magic.from_buffer(content, mime=True)
        except Exception as e:
            logger.error(f"Magic byte detection failed for '{filename}': {e}", exc_info=True)
            raise UnsupportedMediaTypeError("Unable to determine file type from content.") from e

        logger.debug(f"Detected MIME type '{detected_mime}' for file '{filename}'")

        if detected_mime not in ALLOWED_MIME_TYPES:
            logger.warning(f"File validation rejected: content type '{detected_mime}' not allowed | filename={filename}")
            raise UnsupportedMediaTypeError(
                f"File content is '{detected_mime}', which is not an allowed image type. "
                f"Rename attacks (e.g. .docx -> .jpg) are rejected."
            )

        return ALLOWED_MIME_TYPES[detected_mime], detected_mime

    @staticmethod
    def validate_size(content: bytes, max_bytes: int):
        if len(content) == 0:
            logger.warning("File validation rejected: uploaded file is empty")
            raise PayloadTooLargeError("Uploaded file is empty.")
        if len(content) > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            logger.warning(f"File validation rejected: file too large | size={len(content)} | max_mb={max_mb}")
            raise PayloadTooLargeError(f"File too large. Maximum allowed size is {max_mb} MB.")
