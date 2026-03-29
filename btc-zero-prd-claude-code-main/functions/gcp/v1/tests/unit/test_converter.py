"""Unit tests for TIFF-to-PNG converter.

Tests image conversion logic including multi-page handling,
resizing, and format validation.
"""

import io

import pytest
from PIL import Image

from functions.tiff_to_png.converter import (
    ConversionResult,
    convert_tiff_to_png,
    convert_tiff_to_png_detailed,
)


class TestConvertTiffToPng:
    """Tests for convert_tiff_to_png function."""

    def test_single_page_conversion(self, sample_tiff_data):
        """Test converting a single-page TIFF."""
        result = convert_tiff_to_png(sample_tiff_data)

        assert len(result) == 1
        assert isinstance(result[0], bytes)

        img = Image.open(io.BytesIO(result[0]))
        assert img.format == "PNG"

    def test_multipage_conversion(self, sample_multipage_tiff_data):
        """Test converting a multi-page TIFF."""
        result = convert_tiff_to_png(sample_multipage_tiff_data)

        assert len(result) == 3

        for png_data in result:
            img = Image.open(io.BytesIO(png_data))
            assert img.format == "PNG"

    def test_invalid_image_raises_error(self):
        """Test that invalid data raises ValueError."""
        invalid_data = b"not an image"

        with pytest.raises(ValueError, match="Cannot identify"):
            convert_tiff_to_png(invalid_data)

    def test_non_tiff_raises_error(self, sample_png_data):
        """Test that non-TIFF images raise ValueError."""
        with pytest.raises(ValueError, match="Expected TIFF"):
            convert_tiff_to_png(sample_png_data)

    def test_resize_large_image(self):
        """Test that large images are resized."""
        large_img = Image.new("RGB", (5000, 3000), color="white")
        buffer = io.BytesIO()
        large_img.save(buffer, format="TIFF")
        large_tiff = buffer.getvalue()

        result = convert_tiff_to_png(large_tiff, max_dimension=2048)

        assert len(result) == 1

        output_img = Image.open(io.BytesIO(result[0]))
        width, height = output_img.size
        assert max(width, height) <= 2048

    def test_no_resize_small_image(self, sample_tiff_data):
        """Test that small images are not resized."""
        result = convert_tiff_to_png(sample_tiff_data, max_dimension=4096)

        assert len(result) == 1

        input_img = Image.open(io.BytesIO(sample_tiff_data))
        output_img = Image.open(io.BytesIO(result[0]))

        assert input_img.size == output_img.size

    def test_disable_resize(self):
        """Test max_dimension=None disables resizing."""
        large_img = Image.new("RGB", (5000, 3000), color="white")
        buffer = io.BytesIO()
        large_img.save(buffer, format="TIFF")
        large_tiff = buffer.getvalue()

        result = convert_tiff_to_png(large_tiff, max_dimension=None)

        output_img = Image.open(io.BytesIO(result[0]))
        assert output_img.size == (5000, 3000)

    def test_rgba_to_rgb_conversion(self):
        """Test RGBA images are converted to RGB."""
        rgba_img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        rgba_img.save(buffer, format="TIFF")
        rgba_tiff = buffer.getvalue()

        result = convert_tiff_to_png(rgba_tiff)

        output_img = Image.open(io.BytesIO(result[0]))
        assert output_img.mode == "RGB"

    def test_grayscale_to_rgb_conversion(self):
        """Test grayscale images are converted to RGB."""
        gray_img = Image.new("L", (100, 100), color=128)
        buffer = io.BytesIO()
        gray_img.save(buffer, format="TIFF")
        gray_tiff = buffer.getvalue()

        result = convert_tiff_to_png(gray_tiff)

        output_img = Image.open(io.BytesIO(result[0]))
        assert output_img.mode == "RGB"


class TestConvertTiffToPngDetailed:
    """Tests for convert_tiff_to_png_detailed function."""

    def test_returns_conversion_result(self, sample_tiff_data):
        """Test function returns ConversionResult dataclass."""
        result = convert_tiff_to_png_detailed(sample_tiff_data)

        assert isinstance(result, ConversionResult)
        assert result.page_count == 1
        assert result.original_size_bytes == len(sample_tiff_data)
        assert result.total_output_bytes > 0

    def test_multipage_metrics(self, sample_multipage_tiff_data):
        """Test metrics are correct for multi-page TIFF."""
        result = convert_tiff_to_png_detailed(sample_multipage_tiff_data)

        assert result.page_count == 3
        assert len(result.pages) == 3
        assert result.total_output_bytes == sum(len(p) for p in result.pages)

    def test_original_size_tracked(self, sample_tiff_data):
        """Test original file size is tracked."""
        result = convert_tiff_to_png_detailed(sample_tiff_data)

        assert result.original_size_bytes == len(sample_tiff_data)
