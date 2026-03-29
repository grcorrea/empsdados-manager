"""Integration tests for invoice processing pipeline.

Tests end-to-end flows with mocked external services.
These tests verify the interaction between functions.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from shared.schemas.invoice import VendorType
from shared.schemas.messages import (
    InvoiceClassifiedMessage,
    InvoiceConvertedMessage,
    InvoiceExtractedMessage,
    InvoiceUploadedMessage,
)
from tests.fixtures.sample_invoices import (
    SAMPLE_EXTRACTED_INVOICE,
    SAMPLE_UBEREATS_INVOICE,
    create_minimal_tiff,
)


class TestPipelineMessageFlow:
    """Test message flow between pipeline stages."""

    def test_uploaded_to_converted_message_compatibility(self):
        """Test message format compatibility between stages 1-2."""
        uploaded_msg = InvoiceUploadedMessage(
            bucket="input-bucket",
            name="invoices/test.tiff",
        )

        json_data = uploaded_msg.model_dump(mode="json")

        reconstructed = InvoiceUploadedMessage.model_validate(json_data)
        assert reconstructed.bucket == uploaded_msg.bucket
        assert reconstructed.name == uploaded_msg.name

    def test_converted_to_classified_message_compatibility(self):
        """Test message format compatibility between stages 2-3."""
        converted_msg = InvoiceConvertedMessage(
            source_file="gs://input/test.tiff",
            converted_files=[
                "gs://processed/test_page1.png",
                "gs://processed/test_page2.png",
            ],
            page_count=2,
        )

        json_data = converted_msg.model_dump(mode="json")

        reconstructed = InvoiceConvertedMessage.model_validate(json_data)
        assert reconstructed.source_file == converted_msg.source_file
        assert reconstructed.page_count == 2

    def test_classified_to_extracted_message_compatibility(self):
        """Test message format compatibility between stages 3-4."""
        classified_msg = InvoiceClassifiedMessage(
            source_file="gs://input/test.tiff",
            converted_files=["gs://processed/test_page1.png"],
            vendor_type=VendorType.UBEREATS,
            quality_score=0.95,
            archived_to="gs://archive/test.tiff",
        )

        json_data = classified_msg.model_dump(mode="json")

        reconstructed = InvoiceClassifiedMessage.model_validate(json_data)
        assert reconstructed.vendor_type == VendorType.UBEREATS
        assert reconstructed.quality_score == 0.95

    def test_extracted_to_writer_message_compatibility(self):
        """Test message format compatibility between stages 4-5."""
        extracted_msg = InvoiceExtractedMessage(
            source_file="gs://input/test.tiff",
            vendor_type=VendorType.UBEREATS,
            extraction_model="gemini-2.5-flash",
            extraction_latency_ms=500,
            confidence_score=0.95,
            extracted_data=SAMPLE_UBEREATS_INVOICE,
        )

        json_data = extracted_msg.model_dump(mode="json")

        reconstructed = InvoiceExtractedMessage.model_validate(json_data)
        assert reconstructed.extraction_model == "gemini-2.5-flash"
        assert "invoice_id" in reconstructed.extracted_data


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    def test_happy_path_data_transformation(self):
        """Test data transforms correctly through all stages."""
        tiff_data = create_minimal_tiff()
        assert len(tiff_data) > 0

        from functions.tiff_to_png.converter import convert_tiff_to_png

        png_pages = convert_tiff_to_png(tiff_data)
        assert len(png_pages) == 1

        from functions.invoice_classifier.classifier import (
            classify_vendor,
            validate_image_quality,
        )

        classification = classify_vendor("ubereats_invoice_2026.tiff")
        assert classification.vendor_type == VendorType.UBEREATS

        quality = validate_image_quality(png_pages[0])
        assert quality.width > 0
        assert quality.height > 0

    def test_vendor_classification_flows_to_extraction(self):
        """Test vendor type is preserved through classification to extraction."""
        from functions.invoice_classifier.classifier import classify_vendor

        for vendor in ["ubereats", "doordash", "ifood"]:
            classification = classify_vendor(f"{vendor}_invoice.tiff")

            classified_msg = InvoiceClassifiedMessage(
                source_file=f"gs://input/{vendor}.tiff",
                converted_files=[f"gs://processed/{vendor}_page1.png"],
                vendor_type=classification.vendor_type,
                quality_score=0.95,
                archived_to=f"gs://archive/{vendor}.tiff",
            )

            json_data = classified_msg.model_dump(mode="json")
            reconstructed = InvoiceClassifiedMessage.model_validate(json_data)

            assert reconstructed.vendor_type.value == vendor

    def test_extraction_result_compatible_with_bigquery(self):
        """Test extracted invoice can be prepared for BigQuery."""
        from functions.bigquery_writer.writer import (
            _prepare_invoice_row,
            _prepare_line_item_rows,
        )

        invoice = SAMPLE_EXTRACTED_INVOICE

        invoice_row = _prepare_invoice_row(invoice)
        line_items = _prepare_line_item_rows(invoice)

        assert isinstance(invoice_row["subtotal"], float)
        assert isinstance(invoice_row["invoice_date"], str)
        assert len(line_items) == len(invoice.line_items)


class TestErrorHandling:
    """Test error handling across pipeline stages."""

    def test_invalid_tiff_handled_gracefully(self):
        """Test invalid TIFF data raises appropriate error."""
        from functions.tiff_to_png.converter import convert_tiff_to_png

        with pytest.raises(ValueError):
            convert_tiff_to_png(b"not a valid tiff")

    def test_unknown_vendor_uses_generic_prompt(self):
        """Test unknown vendors fall back to generic prompt."""
        from functions.data_extractor.extractor import load_prompt_template

        prompt = load_prompt_template(VendorType.OTHER)

        assert len(prompt) > 100
        assert "invoice_id" in prompt

    def test_message_validation_catches_missing_fields(self):
        """Test Pydantic catches missing required fields."""
        incomplete_data = {"source_file": "gs://bucket/file.tiff"}

        with pytest.raises(Exception):
            InvoiceConvertedMessage.model_validate(incomplete_data)


class TestConcurrencyConsiderations:
    """Test scenarios related to concurrent processing."""

    def test_invoice_id_uniqueness_per_vendor(self):
        """Test different vendors can have same invoice ID patterns."""
        from tests.fixtures.sample_invoices import create_sample_invoice

        ue_invoice = create_sample_invoice(
            VendorType.UBEREATS, invoice_id="INV-001"
        )
        dd_invoice = create_sample_invoice(
            VendorType.DOORDASH, invoice_id="INV-001"
        )

        assert ue_invoice.invoice_id == dd_invoice.invoice_id
        assert ue_invoice.vendor_type != dd_invoice.vendor_type

    def test_multipage_invoice_all_pages_processed(self):
        """Test multi-page invoices have all pages converted."""
        from functions.tiff_to_png.converter import convert_tiff_to_png
        from tests.fixtures.sample_invoices import create_multipage_tiff

        multipage_tiff = create_multipage_tiff(pages=5)

        png_pages = convert_tiff_to_png(multipage_tiff)

        assert len(png_pages) == 5
