"""
PaddleOCR Optical Character Recognition Adapter (PaddlePaddle/PaddleOCR).
Extracts text and bounding boxes from images and scanned documents with confidence scoring.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OCRBoundingBox(BaseModel):
    text: str
    confidence: float
    box_coordinates: List[List[int]] = Field(default_factory=list)


class OCRResult(BaseModel):
    full_text: str
    elements: List[OCRBoundingBox]
    confidence_mean: float


class PaddleOCRAdapter:
    """
    OCR adapter providing text and layout extraction from image data.
    """

    def process_image_simulated(self, image_path: str, simulated_lines: Optional[List[str]] = None) -> OCRResult:
        lines = simulated_lines or ["Invoice #1042", "Total Amount: $450.00", "Date: 2026-10-25"]
        elements = [
            OCRBoundingBox(
                text=line,
                confidence=0.98,
                box_coordinates=[[10, i * 30], [200, i * 30], [200, i * 30 + 25], [10, i * 30 + 25]],
            )
            for i, line in enumerate(lines)
        ]
        return OCRResult(
            full_text="\n".join(lines),
            elements=elements,
            confidence_mean=0.98,
        )
