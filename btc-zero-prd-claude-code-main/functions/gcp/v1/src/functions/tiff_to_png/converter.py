"""TIFF to PNG conversion logic.

Handles multi-page TIFF files commonly used for invoice documents.
Uses Pillow for image processing with optimization for LLM readability.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageSequence


@dataclass
class ConversionResult:
    """Result of TIFF to PNG conversion.

    Attributes:
        pages: List of PNG byte data, one per page
        page_count: Total number of pages converted
        original_size_bytes: Size of input TIFF
        total_output_bytes: Combined size of all PNGs
    """

    pages: list[bytes]
    page_count: int
    original_size_bytes: int
    total_output_bytes: int


def convert_tiff_to_png(
    tiff_data: bytes,
    *,
    optimize: bool = True,
    max_dimension: int | None = 4096,
) -> list[bytes]:
    """Convert TIFF image to PNG format.

    Handles multi-page TIFF files by extracting each page as a separate PNG.
    Optionally resizes large images to fit within max_dimension while
    preserving aspect ratio.

    Args:
        tiff_data: Raw TIFF file bytes
        optimize: Whether to optimize PNG compression (default: True)
        max_dimension: Maximum width or height in pixels (default: 4096).
            Set to None to disable resizing. LLMs work best with
            reasonably sized images.

    Returns:
        List of PNG byte data, one element per page in the TIFF.
        Single-page TIFFs return a list with one element.

    Raises:
        ValueError: If input is not a valid TIFF image
        IOError: If image processing fails
    """
    png_pages: list[bytes] = []

    try:
        with Image.open(io.BytesIO(tiff_data)) as img:
            if img.format not in ("TIFF", "MPO"):
                raise ValueError(f"Expected TIFF format, got {img.format}")

            for page_num, page in enumerate(ImageSequence.Iterator(img)):
                page_rgb = _ensure_rgb(page)

                if max_dimension:
                    page_rgb = _resize_if_needed(page_rgb, max_dimension)

                png_bytes = _to_png_bytes(page_rgb, optimize=optimize)
                png_pages.append(png_bytes)

    except Image.UnidentifiedImageError as e:
        raise ValueError(f"Cannot identify image format: {e}") from e

    return png_pages


def convert_tiff_to_png_detailed(
    tiff_data: bytes,
    *,
    optimize: bool = True,
    max_dimension: int | None = 4096,
) -> ConversionResult:
    """Convert TIFF to PNG with detailed metrics.

    Same as convert_tiff_to_png but returns a ConversionResult
    with additional metadata useful for logging and monitoring.

    Args:
        tiff_data: Raw TIFF file bytes
        optimize: Whether to optimize PNG compression
        max_dimension: Maximum width or height in pixels

    Returns:
        ConversionResult with pages and metrics
    """
    pages = convert_tiff_to_png(
        tiff_data, optimize=optimize, max_dimension=max_dimension
    )

    return ConversionResult(
        pages=pages,
        page_count=len(pages),
        original_size_bytes=len(tiff_data),
        total_output_bytes=sum(len(p) for p in pages),
    )


def _ensure_rgb(image: Image.Image) -> Image.Image:
    """Convert image to RGB mode if needed.

    TIFF images may be in various modes (L, LA, P, RGBA, CMYK, etc.).
    PNG output for LLM processing should be RGB.

    Args:
        image: PIL Image in any mode

    Returns:
        PIL Image in RGB mode
    """
    if image.mode == "RGB":
        return image

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background

    if image.mode in ("L", "LA", "P"):
        return image.convert("RGB")

    if image.mode == "CMYK":
        return image.convert("RGB")

    return image.convert("RGB")


def _resize_if_needed(image: Image.Image, max_dimension: int) -> Image.Image:
    """Resize image if either dimension exceeds max_dimension.

    Preserves aspect ratio by scaling both dimensions proportionally.
    Uses LANCZOS resampling for high quality downscaling.

    Args:
        image: PIL Image to potentially resize
        max_dimension: Maximum allowed width or height

    Returns:
        Original image if within bounds, resized image otherwise
    """
    width, height = image.size

    if width <= max_dimension and height <= max_dimension:
        return image

    if width > height:
        new_width = max_dimension
        new_height = int(height * (max_dimension / width))
    else:
        new_height = max_dimension
        new_width = int(width * (max_dimension / height))

    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def _to_png_bytes(image: Image.Image, *, optimize: bool = True) -> bytes:
    """Convert PIL Image to PNG bytes.

    Args:
        image: PIL Image in RGB mode
        optimize: Whether to optimize PNG compression

    Returns:
        PNG file as bytes
    """
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=optimize)
    return buffer.getvalue()
