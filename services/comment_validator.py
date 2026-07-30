import magic

from utils.logger import logger
from utils.exceptions import BadRequestError, PayloadTooLargeError, UnsupportedMediaTypeError


ALLOWED_ATTACHMENT_MIME_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}

ALLOWED_ATTACHMENT_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".pdf", ".docx", ".txt"
}


class CommentAttachmentValidator:
    @staticmethod
    def validate_extension(filename: str) -> str:
        if not filename:
            logger.warning("Attachment validation rejected: filename missing")
            raise BadRequestError("Filename is missing.")

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            logger.warning(f"Attachment validation rejected: extension '{ext}' not allowed | filename={filename}")
            raise UnsupportedMediaTypeError("Unsupported media type")
        return ext

    @staticmethod
    def validate_magic_bytes(content: bytes, filename: str) -> tuple[str, str]:
        """
        Inspects the actual file bytes (not just the extension) to
        determine the real MIME type — same rename-attack protection
        as geoclip_validator.py (e.g. a .exe renamed to report.pdf
        gets rejected here even though its extension looks fine).
        """
        try:
            detected_mime = magic.from_buffer(content, mime=True)
        except Exception as e:
            logger.error(f"Magic byte detection failed for '{filename}': {e}", exc_info=True)
            raise UnsupportedMediaTypeError("Unsupported media type") from e

        logger.debug(f"Detected MIME type '{detected_mime}' for attachment '{filename}'")

        # .docx files are ZIP archives internally — libmagic sometimes
        # reports them as the generic "application/zip" rather than the
        # full Office Open XML MIME type. Accept that specifically when
        # the extension is .docx, rather than rejecting valid Word docs.
        if detected_mime == "application/zip" and filename.lower().endswith(".docx"):
            detected_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        if detected_mime not in ALLOWED_ATTACHMENT_MIME_TYPES:
            logger.warning(
                f"Attachment validation rejected: content type '{detected_mime}' not allowed | filename={filename}"
            )
            raise UnsupportedMediaTypeError("Unsupported media type")

        return ALLOWED_ATTACHMENT_MIME_TYPES[detected_mime], detected_mime

    @staticmethod
    def validate_size(content: bytes, max_bytes: int):
        if len(content) == 0:
            logger.warning("Attachment validation rejected: uploaded file is empty")
            raise BadRequestError("Uploaded file is empty.")
        if len(content) > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            logger.warning(f"Attachment validation rejected: file too large | size={len(content)} | max_mb={max_mb}")
            raise PayloadTooLargeError(f"File too large. Maximum allowed size is {max_mb} MB.")
