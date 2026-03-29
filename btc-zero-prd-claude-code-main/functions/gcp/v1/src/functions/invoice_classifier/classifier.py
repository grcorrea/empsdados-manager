"""Invoice classification and quality validation logic.

Detects vendor type from filename patterns and validates image quality
for downstream LLM extraction. Uses pattern matching for known vendors
with fallback to "other" for unknown formats.
"""

import re
from dataclasses import dataclass

from PIL import Image

from shared.schemas.invoice import VendorType


@dataclass
class ClassificationResult:
    """Result of invoice classification.

    Attributes:
        vendor_type: Detected vendor (UberEats, DoorDash, etc.)
        confidence: Confidence score (0.0 to 1.0)
        detection_method: How vendor was detected (filename, content, default)
        matched_pattern: Pattern that matched (if filename-based)
    """

    vendor_type: VendorType
    confidence: float
    detection_method: str
    matched_pattern: str | None = None


@dataclass
class QualityResult:
    """Result of image quality validation.

    Attributes:
        is_valid: Whether image meets quality requirements
        quality_score: Overall quality score (0.0 to 1.0)
        width: Image width in pixels
        height: Image height in pixels
        issues: List of quality issues found
    """

    is_valid: bool
    quality_score: float
    width: int
    height: int
    issues: list[str]


VENDOR_PATTERNS: dict[VendorType, list[re.Pattern[str]]] = {
    VendorType.UBEREATS: [
        re.compile(r"uber[-_]?eats?", re.IGNORECASE),
        re.compile(r"UE[-_]?\d{4}", re.IGNORECASE),
        re.compile(r"ubereats_invoice", re.IGNORECASE),
    ],
    VendorType.DOORDASH: [
        re.compile(r"door[-_]?dash", re.IGNORECASE),
        re.compile(r"DD[-_]?\d{4}", re.IGNORECASE),
        re.compile(r"doordash_statement", re.IGNORECASE),
    ],
    VendorType.GRUBHUB: [
        re.compile(r"grub[-_]?hub", re.IGNORECASE),
        re.compile(r"GH[-_]?\d{4}", re.IGNORECASE),
        re.compile(r"grubhub_invoice", re.IGNORECASE),
    ],
    VendorType.IFOOD: [
        re.compile(r"i[-_]?food", re.IGNORECASE),
        re.compile(r"IF[-_]?\d{4}", re.IGNORECASE),
        re.compile(r"ifood_fatura", re.IGNORECASE),
    ],
    VendorType.RAPPI: [
        re.compile(r"rappi", re.IGNORECASE),
        re.compile(r"RP[-_]?\d{4}", re.IGNORECASE),
        re.compile(r"rappi_factura", re.IGNORECASE),
    ],
}

MIN_WIDTH = 800
MIN_HEIGHT = 600
MIN_RESOLUTION = 72
IDEAL_MIN_DIMENSION = 1200


def classify_vendor(
    source_file: str,
    png_files: list[str] | None = None,
) -> ClassificationResult:
    """Classify invoice vendor type.

    Uses a tiered approach:
    1. Filename pattern matching (fast, high confidence)
    2. Default to "other" if no patterns match

    Args:
        source_file: Original TIFF filename or GCS URI
        png_files: Optional list of converted PNG URIs (for future content analysis)

    Returns:
        ClassificationResult with vendor type and confidence
    """
    filename = _extract_filename(source_file)

    for vendor_type, patterns in VENDOR_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(filename):
                return ClassificationResult(
                    vendor_type=vendor_type,
                    confidence=0.95,
                    detection_method="filename",
                    matched_pattern=pattern.pattern,
                )

    return ClassificationResult(
        vendor_type=VendorType.OTHER,
        confidence=0.5,
        detection_method="default",
        matched_pattern=None,
    )


def validate_image_quality(image_data: bytes) -> QualityResult:
    """Validate image quality for LLM extraction.

    Checks:
    - Minimum dimensions (800x600)
    - Reasonable file size (not too small = likely blank)
    - Image can be opened (not corrupted)

    Args:
        image_data: PNG image bytes

    Returns:
        QualityResult with validation details
    """
    issues: list[str] = []

    if len(image_data) < 10_000:
        issues.append("File too small (< 10KB), may be blank or corrupted")

    try:
        import io

        with Image.open(io.BytesIO(image_data)) as img:
            width, height = img.size

            if width < MIN_WIDTH:
                issues.append(f"Width {width}px below minimum {MIN_WIDTH}px")

            if height < MIN_HEIGHT:
                issues.append(f"Height {height}px below minimum {MIN_HEIGHT}px")

            quality_score = _calculate_quality_score(width, height, len(image_data))

            return QualityResult(
                is_valid=len(issues) == 0,
                quality_score=quality_score,
                width=width,
                height=height,
                issues=issues,
            )

    except Exception as e:
        return QualityResult(
            is_valid=False,
            quality_score=0.0,
            width=0,
            height=0,
            issues=[f"Cannot open image: {e}"],
        )


def validate_all_images(images_data: list[bytes]) -> tuple[bool, float, list[str]]:
    """Validate quality of all images in a multi-page invoice.

    Args:
        images_data: List of PNG image bytes

    Returns:
        Tuple of (all_valid, average_score, all_issues)
    """
    if not images_data:
        return False, 0.0, ["No images provided"]

    results = [validate_image_quality(img) for img in images_data]

    all_valid = all(r.is_valid for r in results)
    avg_score = sum(r.quality_score for r in results) / len(results)
    all_issues = []
    for i, r in enumerate(results):
        for issue in r.issues:
            all_issues.append(f"Page {i + 1}: {issue}")

    return all_valid, avg_score, all_issues


def _extract_filename(path: str) -> str:
    """Extract filename from path or GCS URI.

    Args:
        path: File path or gs:// URI

    Returns:
        Filename without directory path
    """
    if path.startswith("gs://"):
        path = path.split("/", 3)[-1] if "/" in path else path

    return path.rsplit("/", 1)[-1]


def _calculate_quality_score(width: int, height: int, file_size: int) -> float:
    """Calculate overall image quality score.

    Score based on:
    - Dimensions (larger is better up to a point)
    - File size (indicator of detail/compression)

    Args:
        width: Image width in pixels
        height: Image height in pixels
        file_size: File size in bytes

    Returns:
        Quality score from 0.0 to 1.0
    """
    dimension_score = min(1.0, min(width, height) / IDEAL_MIN_DIMENSION)

    if file_size < 50_000:
        size_score = file_size / 50_000
    elif file_size > 5_000_000:
        size_score = max(0.5, 1.0 - (file_size - 5_000_000) / 10_000_000)
    else:
        size_score = 1.0

    return (dimension_score * 0.7) + (size_score * 0.3)
