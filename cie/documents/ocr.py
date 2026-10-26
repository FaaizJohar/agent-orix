"""
Optional OCR provider abstraction for CIE Document Intelligence.
Guarantees zero memory footprint by default. OCR is disabled unless explicitly enabled.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger("cie.documents.ocr")


class DocumentOcrProvider:
    """
    Manages optional OCR execution.
    By default, enable_ocr is False, ensuring no OCR models or subprocesses consume host RAM.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    @staticmethod
    def is_ocr_backend_installed() -> bool:
        """Checks if pytesseract and Pillow are available without loading large weights."""
        try:
            import importlib.util
            return importlib.util.find_spec("pytesseract") is not None and importlib.util.find_spec("PIL") is not None
        except Exception:
            return False

    def process_image(self, image_data: bytes) -> Tuple[str, bool, Optional[str]]:
        """
        Attempts OCR on image bytes if enabled.
        Returns: (extracted_text, ocr_applied, error_or_notice)
        """
        if not self.enabled:
            return (
                "",
                False,
                "OCR is disabled by default to preserve system RAM (6GB host constraint). "
                "Enable 'enable_ocr=True' to process scanned documents or images."
            )

        if not self.is_ocr_backend_installed():
            return (
                "",
                False,
                "OCR was requested, but 'pytesseract' is not installed or configured on this system."
            )

        try:
            import io
            from PIL import Image
            import pytesseract

            img = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(img)
            return text.strip(), True, None
        except Exception as e:
            logger.warning(f"OCR execution failed: {e}")
            return "", False, f"OCR processing failed: {str(e)}"
