"""Unit tests for Pydantic schemas.

Tests validation rules, computed fields, and edge cases
for ExtractedInvoice and related models.
"""

from datetime import date
from decimal import Decimal

import pytest

from shared.schemas.invoice import ExtractedInvoice, LineItem, VendorType
from shared.schemas.messages import (
    InvoiceClassifiedMessage,
    InvoiceConvertedMessage,
    InvoiceExtractedMessage,
    InvoiceUploadedMessage,
)


class TestLineItem:
    """Tests for LineItem model."""

    def test_line_item_creation(self):
        """Test basic line item creation."""
        item = LineItem(
            description="Order Sales",
            quantity=1,
            unit_price=Decimal("100.00"),
        )

        assert item.description == "Order Sales"
        assert item.quantity == 1
        assert item.unit_price == Decimal("100.00")

    def test_line_item_computed_amount(self):
        """Test amount is computed from quantity * unit_price."""
        item = LineItem(
            description="Items",
            quantity=3,
            unit_price=Decimal("25.00"),
        )

        assert item.amount == Decimal("75.00")

    def test_line_item_negative_amount_rejected(self):
        """Test line items with negative unit_price are rejected.

        Schema enforces unit_price >= 0 for data integrity.
        Discounts should be modeled separately, not as negative prices.
        """
        with pytest.raises(ValueError):
            LineItem(
                description="Discount",
                quantity=1,
                unit_price=Decimal("-50.00"),
            )

    def test_line_item_default_quantity(self):
        """Test quantity defaults to 1."""
        item = LineItem(
            description="Single Item",
            unit_price=Decimal("100.00"),
        )

        assert item.quantity == 1
        assert item.amount == Decimal("100.00")


class TestExtractedInvoice:
    """Tests for ExtractedInvoice model."""

    def test_valid_invoice_creation(self, sample_invoice_dict):
        """Test creating a valid invoice from dict."""
        invoice = ExtractedInvoice.model_validate(sample_invoice_dict)

        assert invoice.invoice_id == "UE-2026-001234"
        assert invoice.vendor_type == VendorType.UBEREATS
        assert invoice.currency == "USD"
        assert len(invoice.line_items) == 2  # Order Sales + Delivery Fees

    def test_invoice_id_validation(self):
        """Test invoice_id can be various formats."""
        base_data = {
            "invoice_id": "ABC-123",
            "vendor_name": "Test",
            "vendor_type": "other",
            "invoice_date": "2026-01-15",
            "due_date": "2026-01-29",
            "currency": "USD",
            "line_items": [{"description": "Test", "unit_price": "100.00"}],
            "subtotal": "100.00",
            "tax_amount": "0.00",
            "commission_rate": "0.10",
            "commission_amount": "10.00",
            "total_amount": "90.00",
        }

        for invoice_id in ["UE-2026-001234", "DD-123", "simple123", "X"]:
            data = {**base_data, "invoice_id": invoice_id}
            invoice = ExtractedInvoice.model_validate(data)
            assert invoice.invoice_id == invoice_id

    def test_vendor_type_enum(self):
        """Test all vendor types are valid."""
        valid_types = ["ubereats", "doordash", "grubhub", "ifood", "rappi", "other"]

        for vtype in valid_types:
            assert VendorType(vtype) is not None

    def test_currency_validation(self):
        """Test supported currencies."""
        valid_currencies = ["BRL", "USD", "EUR", "GBP", "CAD", "AUD", "MXN", "COP"]

        for curr in valid_currencies:
            assert curr in ExtractedInvoice.model_fields["currency"].annotation.__args__

    def test_date_parsing(self):
        """Test date fields parse ISO format correctly."""
        data = {
            "invoice_id": "TEST-001",
            "vendor_name": "Test",
            "vendor_type": "other",
            "invoice_date": "2026-01-15",
            "due_date": "2026-01-29",
            "currency": "USD",
            "line_items": [{"description": "Test", "unit_price": "100.00"}],
            "subtotal": "100.00",
            "tax_amount": "0.00",
            "commission_rate": "0.10",
            "commission_amount": "10.00",
            "total_amount": "90.00",
        }

        invoice = ExtractedInvoice.model_validate(data)

        assert invoice.invoice_date == date(2026, 1, 15)
        assert invoice.due_date == date(2026, 1, 29)

    def test_decimal_precision(self):
        """Test decimal fields maintain precision."""
        data = {
            "invoice_id": "TEST-001",
            "vendor_name": "Test",
            "vendor_type": "other",
            "invoice_date": "2026-01-15",
            "due_date": "2026-01-29",
            "currency": "USD",
            "line_items": [{"description": "Test", "unit_price": "123.456"}],
            "subtotal": "1234.56",
            "tax_amount": "123.45",
            "commission_rate": "0.15",
            "commission_amount": "185.18",
            "total_amount": "1049.38",
        }

        invoice = ExtractedInvoice.model_validate(data)

        assert invoice.subtotal == Decimal("1234.56")
        assert invoice.commission_rate == Decimal("0.15")

    def test_invalid_commission_rate(self):
        """Test commission rate must be between 0 and 1."""
        data = {
            "invoice_id": "TEST-001",
            "vendor_name": "Test",
            "vendor_type": "other",
            "invoice_date": "2026-01-15",
            "due_date": "2026-01-29",
            "currency": "USD",
            "line_items": [{"description": "Test", "unit_price": "100.00"}],
            "subtotal": "100.00",
            "tax_amount": "0.00",
            "commission_rate": "1.5",  # > 1.0 is invalid
            "commission_amount": "150.00",
            "total_amount": "-50.00",
        }

        with pytest.raises(ValueError):
            ExtractedInvoice.model_validate(data)


class TestMessageSchemas:
    """Tests for Pub/Sub message schemas."""

    def test_invoice_uploaded_message(self):
        """Test InvoiceUploadedMessage creation."""
        msg = InvoiceUploadedMessage(
            bucket="test-bucket",
            name="invoices/test.tiff",
        )

        assert msg.bucket == "test-bucket"
        assert msg.name == "invoices/test.tiff"
        assert msg.event_time is not None

    def test_invoice_converted_message(self):
        """Test InvoiceConvertedMessage creation."""
        msg = InvoiceConvertedMessage(
            source_file="gs://input/test.tiff",
            converted_files=["gs://processed/test_page1.png"],
            page_count=1,
        )

        assert msg.source_file == "gs://input/test.tiff"
        assert len(msg.converted_files) == 1
        assert msg.page_count == 1

    def test_invoice_classified_message(self):
        """Test InvoiceClassifiedMessage creation."""
        msg = InvoiceClassifiedMessage(
            source_file="gs://input/test.tiff",
            converted_files=["gs://processed/test_page1.png"],
            vendor_type=VendorType.UBEREATS,
            quality_score=0.95,
            archived_to="gs://archive/test.tiff",
        )

        assert msg.vendor_type == VendorType.UBEREATS
        assert msg.quality_score == 0.95

    def test_invoice_extracted_message(self):
        """Test InvoiceExtractedMessage creation."""
        msg = InvoiceExtractedMessage(
            source_file="gs://input/test.tiff",
            vendor_type=VendorType.UBEREATS,
            extraction_model="gemini-2.5-flash",
            extraction_latency_ms=500,
            confidence_score=0.95,
            extracted_data={"invoice_id": "TEST-001"},
        )

        assert msg.extraction_model == "gemini-2.5-flash"
        assert msg.extraction_latency_ms == 500
        assert msg.extracted_data["invoice_id"] == "TEST-001"

    def test_message_serialization(self):
        """Test messages can be serialized to JSON."""
        msg = InvoiceConvertedMessage(
            source_file="gs://input/test.tiff",
            converted_files=["gs://processed/test_page1.png"],
            page_count=1,
        )

        json_data = msg.model_dump(mode="json")

        assert isinstance(json_data, dict)
        assert "source_file" in json_data
        assert "event_time" in json_data
