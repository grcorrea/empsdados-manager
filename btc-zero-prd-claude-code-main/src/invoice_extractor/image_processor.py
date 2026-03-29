"""Image processing utilities for invoice extraction.

Handles TIFF/PNG image conversion, multi-page splitting, and optimization
for LLM processing.
"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class ProcessingResult:
    """Result of image processing operations.

    Attributes:
        success: Whether processing completed successfully
        output_paths: List of processed image paths
        page_count: Number of pages processed
        original_path: Original input file path
        error_message: Error message if processing failed
    """
    success: bool
    output_paths: list[Path]
    page_count: int
    original_path: Path
    error_message: str | None = None


# =============================================================================
# IMAGE LOADING
# =============================================================================

def load_image(file_path: Path) -> Image.Image | None:
    """Load image from TIFF or PNG file.

    Args:
        file_path: Path to TIFF or PNG file

    Returns:
        PIL Image object if successful, None otherwise

    Note:
        For multi-page TIFF files, returns only the first page.
        Use split_multipage_tiff() to extract all pages.
    """
    try:
        img = Image.open(file_path)
        return img
    except Exception as e:
        print(f"Error loading image {file_path}: {e}")
        return None


# =============================================================================
# TIFF HANDLING
# =============================================================================

def split_multipage_tiff(tiff_path: Path, output_dir: Path) -> list[Path]:
    """Split multi-page TIFF into separate PNG files.

    Args:
        tiff_path: Path to multi-page TIFF file
        output_dir: Directory to save split PNG files

    Returns:
        List of paths to extracted PNG files

    Example:
        >>> tiff_path = Path("data/input/invoice.tiff")
        >>> output_paths = split_multipage_tiff(tiff_path, Path("data/processed"))
        >>> # Creates: invoice_p1.png, invoice_p2.png, ...
    """
    output_paths = []
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(tiff_path) as img:
            # Get base filename without extension
            base_name = tiff_path.stem

            # Get number of pages
            page_count = getattr(img, 'n_frames', 1)

            for page_num in range(page_count):
                # Seek to page
                img.seek(page_num)

                # Convert and save
                output_path = output_dir / f"{base_name}_p{page_num + 1}.png"
                rgb_img = convert_to_rgb_png(img)
                resized_img = resize_for_llm(rgb_img)
                resized_img.save(output_path, "PNG")

                output_paths.append(output_path)

    except Exception as e:
        print(f"Error splitting TIFF {tiff_path}: {e}")
        return []

    return output_paths


# =============================================================================
# IMAGE CONVERSION
# =============================================================================

def convert_to_rgb_png(image: Image.Image) -> Image.Image:
    """Convert image to RGB mode.

    Args:
        image: PIL Image in any mode

    Returns:
        Image converted to RGB mode

    Note:
        Required for images in CMYK, L (grayscale), or P (palette) modes.
    """
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def resize_for_llm(image: Image.Image, max_size: int = 4096) -> Image.Image:
    """Resize image to fit within LLM input limits while preserving aspect ratio.

    Args:
        image: PIL Image to resize
        max_size: Maximum dimension (width or height) in pixels

    Returns:
        Resized image if original exceeded max_size, otherwise original

    Example:
        >>> img = Image.open("large_invoice.png")  # 6000x8000
        >>> resized = resize_for_llm(img, max_size=4096)
        >>> # Result: 3072x4096 (aspect ratio preserved)
    """
    width, height = image.size

    # Check if resizing needed
    if width <= max_size and height <= max_size:
        return image

    # Calculate scaling factor
    if width > height:
        new_width = max_size
        new_height = int(height * (max_size / width))
    else:
        new_height = max_size
        new_width = int(width * (max_size / height))

    # Resize using high-quality Lanczos resampling
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


# =============================================================================
# PIPELINE ORCHESTRATION
# =============================================================================

def process_invoice_image(
    input_path: Path,
    output_dir: Path
) -> ProcessingResult:
    """Full processing pipeline: load, split (if TIFF), convert, resize, save.

    Args:
        input_path: Path to input TIFF or PNG file
        output_dir: Directory to save processed images

    Returns:
        ProcessingResult with success status and output paths

    Pipeline Steps:
        1. Detect file format (TIFF or PNG)
        2. If multi-page TIFF: split into separate pages
        3. Convert each image to RGB
        4. Resize to fit LLM limits (max 4096px)
        5. Save as PNG

    Example:
        >>> result = process_invoice_image(
        ...     Path("data/input/invoice.tiff"),
        ...     Path("data/processed")
        ... )
        >>> if result.success:
        ...     print(f"Processed {result.page_count} pages")
        ...     for path in result.output_paths:
        ...         print(f"  - {path}")
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Check file extension
        suffix = input_path.suffix.lower()

        if suffix in ['.tif', '.tiff']:
            # Handle TIFF (potentially multi-page)
            output_paths = split_multipage_tiff(input_path, output_dir)

            if not output_paths:
                return ProcessingResult(
                    success=False,
                    output_paths=[],
                    page_count=0,
                    original_path=input_path,
                    error_message="Failed to split TIFF file"
                )

            return ProcessingResult(
                success=True,
                output_paths=output_paths,
                page_count=len(output_paths),
                original_path=input_path
            )

        elif suffix in ['.png', '.jpg', '.jpeg']:
            # Handle single-page image
            img = load_image(input_path)

            if img is None:
                return ProcessingResult(
                    success=False,
                    output_paths=[],
                    page_count=0,
                    original_path=input_path,
                    error_message=f"Failed to load image {input_path}"
                )

            # Convert and resize
            rgb_img = convert_to_rgb_png(img)
            resized_img = resize_for_llm(rgb_img)

            # Save
            output_path = output_dir / f"{input_path.stem}_processed.png"
            resized_img.save(output_path, "PNG")

            return ProcessingResult(
                success=True,
                output_paths=[output_path],
                page_count=1,
                original_path=input_path
            )

        else:
            return ProcessingResult(
                success=False,
                output_paths=[],
                page_count=0,
                original_path=input_path,
                error_message=f"Unsupported file format: {suffix}"
            )

    except Exception as e:
        return ProcessingResult(
            success=False,
            output_paths=[],
            page_count=0,
            original_path=input_path,
            error_message=f"Processing error: {str(e)}"
        )
