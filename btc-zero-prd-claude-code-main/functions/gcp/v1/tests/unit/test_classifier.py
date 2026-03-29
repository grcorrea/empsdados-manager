"""Unit tests for invoice classifier.

Tests vendor detection patterns and image quality validation.
"""

import io

import pytest
from PIL import Image

from functions.invoice_classifier.classifier import (
    ClassificationResult,
    QualityResult,
    classify_vendor,
    validate_all_images,
    validate_image_quality,
)
from shared.schemas.invoice import VendorType


class TestClassifyVendor:
    """Tests for classify_vendor function."""

    @pytest.mark.parametrize(
        "filename,expected_vendor",
        [
            ("uber_eats_invoice_2026.tiff", VendorType.UBEREATS),
            ("UE-2026-001234.tiff", VendorType.UBEREATS),
            ("ubereats_statement.tiff", VendorType.UBEREATS),
            ("doordash_payment_2026.tiff", VendorType.DOORDASH),
            ("DD-2026-789012.tiff", VendorType.DOORDASH),
            ("door-dash-invoice.tiff", VendorType.DOORDASH),
            ("grubhub_partner_statement.tiff", VendorType.GRUBHUB),
            ("GH-2026-345678.tiff", VendorType.GRUBHUB),
            ("grub_hub_2026.tiff", VendorType.GRUBHUB),
            ("ifood_fatura_jan.tiff", VendorType.IFOOD),
            ("IF-2026-123456.tiff", VendorType.IFOOD),
            ("i-food-extrato.tiff", VendorType.IFOOD),
            ("rappi_factura_enero.tiff", VendorType.RAPPI),
            ("RP-2026-567890.tiff", VendorType.RAPPI),
            ("rappi_statement.tiff", VendorType.RAPPI),
        ],
    )
    def test_vendor_detection_from_filename(self, filename, expected_vendor):
        """Test vendor detection from various filename patterns."""
        result = classify_vendor(filename)

        assert result.vendor_type == expected_vendor
        assert result.detection_method == "filename"
        assert result.confidence >= 0.9

    def test_unknown_vendor_defaults_to_other(self):
        """Test unknown filenames default to 'other'."""
        result = classify_vendor("random_invoice_123.tiff")

        assert result.vendor_type == VendorType.OTHER
        assert result.detection_method == "default"
        assert result.confidence < 0.9

    def test_gcs_uri_parsing(self):
        """Test vendor detection from full GCS URIs."""
        result = classify_vendor("gs://invoices-input/partners/uber_eats_2026.tiff")

        assert result.vendor_type == VendorType.UBEREATS

    def test_case_insensitive_matching(self):
        """Test patterns match regardless of case."""
        for filename in ["UBEREATS_invoice.tiff", "UberEats_Statement.tiff", "uBerEaTs.tiff"]:
            result = classify_vendor(filename)
            assert result.vendor_type == VendorType.UBEREATS

    def test_returns_classification_result(self):
        """Test function returns ClassificationResult dataclass."""
        result = classify_vendor("uber_eats.tiff")

        assert isinstance(result, ClassificationResult)
        assert hasattr(result, "vendor_type")
        assert hasattr(result, "confidence")
        assert hasattr(result, "detection_method")
        assert hasattr(result, "matched_pattern")


class TestValidateImageQuality:
    """Tests for validate_image_quality function."""

    def test_valid_image(self, sample_png_data):
        """Test valid images pass quality check."""
        result = validate_image_quality(sample_png_data)

        assert isinstance(result, QualityResult)
        assert result.width > 0
        assert result.height > 0

    def test_small_image_fails(self):
        """Test images below minimum dimensions are flagged."""
        small_img = Image.new("RGB", (400, 300), color="white")
        buffer = io.BytesIO()
        small_img.save(buffer, format="PNG")
        small_data = buffer.getvalue()

        result = validate_image_quality(small_data)

        assert not result.is_valid
        assert len(result.issues) > 0
        assert any("below minimum" in issue for issue in result.issues)

    def test_corrupt_image_fails(self):
        """Test corrupt image data is detected."""
        corrupt_data = b"not a valid image"

        result = validate_image_quality(corrupt_data)

        assert not result.is_valid
        assert result.quality_score == 0.0
        assert any("Cannot open" in issue for issue in result.issues)

    def test_very_small_file_flagged(self):
        """Test very small files are flagged as potentially blank."""
        tiny_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        result = validate_image_quality(tiny_data)

        assert not result.is_valid

    def test_quality_score_calculation(self):
        """Test quality score is between 0 and 1."""
        good_img = Image.new("RGB", (1500, 1500), color="white")
        buffer = io.BytesIO()
        good_img.save(buffer, format="PNG")
        good_data = buffer.getvalue()

        result = validate_image_quality(good_data)

        assert 0.0 <= result.quality_score <= 1.0


class TestValidateAllImages:
    """Tests for validate_all_images function."""

    def test_all_valid_images(self, sample_png_data):
        """Test all valid images return success."""
        images = [sample_png_data, sample_png_data, sample_png_data]

        all_valid, avg_score, issues = validate_all_images(images)

        assert all_valid
        assert avg_score > 0
        assert len(issues) == 0

    def test_mixed_quality_images(self, sample_png_data):
        """Test mixed quality returns combined issues."""
        small_img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        small_img.save(buffer, format="PNG")
        small_data = buffer.getvalue()

        images = [sample_png_data, small_data]

        all_valid, avg_score, issues = validate_all_images(images)

        assert len(issues) > 0

    def test_empty_list_fails(self):
        """Test empty image list returns failure."""
        all_valid, avg_score, issues = validate_all_images([])

        assert not all_valid
        assert avg_score == 0.0
        assert "No images" in issues[0]

    def test_issues_include_page_numbers(self, sample_png_data):
        """Test issues include page references."""
        small_img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        small_img.save(buffer, format="PNG")
        small_data = buffer.getvalue()

        images = [sample_png_data, small_data]

        all_valid, avg_score, issues = validate_all_images(images)

        assert any("Page 2:" in issue for issue in issues)
