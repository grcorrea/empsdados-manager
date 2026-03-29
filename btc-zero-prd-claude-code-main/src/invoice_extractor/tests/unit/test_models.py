"""Tests for Pydantic models in invoice_extractor.models."""

import json
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...models import (
    ExtractionResult,
    ExtractionSource,
    ExtractedInvoice,
    FinancialSummary,
    InvoiceHeader,
    LineItem,
    ValidationResult,
    VendorType,
    get_extraction_schema_json,
)


# =============================================================================
# ENUM TESTS
# =============================================================================

def test_vendor_type_enum():
    """Test VendorType enum values."""
    assert VendorType.UBEREATS.value == "ubereats"
    assert VendorType.DOORDASH.value == "doordash"
    assert VendorType.GRUBHUB.value == "grubhub"
    assert VendorType.IFOOD.value == "ifood"
    assert VendorType.RAPPI.value == "rappi"
    assert VendorType.OTHER.value == "other"
    assert len(VendorType) == 6


def test_extraction_source_enum():
    """Test ExtractionSource enum values."""
    assert ExtractionSource.GEMINI.value == "gemini"
    assert ExtractionSource.OPENROUTER.value == "openrouter"
    assert ExtractionSource.MANUAL.value == "manual"
    assert len(ExtractionSource) == 3


# =============================================================================
# LINE ITEM TESTS
# =============================================================================

def test_line_item_valid():
    """Test valid LineItem creation."""
    item = LineItem(
        description="Delivery Service Fee",
        quantity=1,
        unit_price=Decimal("15.00")
    )
    assert item.description == "Delivery Service Fee"
    assert item.quantity == 1
    assert item.unit_price == Decimal("15.00")
    assert item.amount == Decimal("15.00")


def test_line_item_computed_amount():
    """Test LineItem computed amount calculation."""
    item = LineItem(
        description="Product",
        quantity=3,
        unit_price=Decimal("10.50")
    )
    assert item.amount == Decimal("31.50")


def test_line_item_invalid_description():
    """Test LineItem with empty description fails."""
    with pytest.raises(ValidationError) as exc_info:
        LineItem(description="", unit_price=Decimal("10.00"))
    assert "description" in str(exc_info.value)


def test_line_item_negative_price():
    """Test LineItem with negative price fails."""
    with pytest.raises(ValidationError) as exc_info:
        LineItem(description="Test", unit_price=Decimal("-10.00"))
    assert "unit_price" in str(exc_info.value)


# =============================================================================
# INVOICE HEADER TESTS
# =============================================================================

def test_invoice_header_valid():
    """Test valid InvoiceHeader creation."""
    header = InvoiceHeader(
        invoice_id="UE-2025-001234",
        vendor_name="Test Restaurant",
        vendor_type=VendorType.UBEREATS,
        invoice_date=date(2025, 1, 15),
        due_date=date(2025, 2, 15),
        currency="BRL"
    )
    assert header.invoice_id == "UE-2025-001234"
    assert header.vendor_type == VendorType.UBEREATS


def test_invoice_header_date_validation_fails():
    """Test InvoiceHeader with due_date before invoice_date fails."""
    with pytest.raises(ValidationError) as exc_info:
        InvoiceHeader(
            invoice_id="UE-2025-001234",
            vendor_name="Test Restaurant",
            invoice_date=date(2025, 2, 15),
            due_date=date(2025, 1, 15),  # Before invoice_date
        )
    assert "due_date" in str(exc_info.value)


def test_invoice_header_invalid_id_pattern():
    """Test InvoiceHeader with invalid ID pattern fails."""
    with pytest.raises(ValidationError) as exc_info:
        InvoiceHeader(
            invoice_id="INVALID",
            vendor_name="Test Restaurant",
            invoice_date=date(2025, 1, 15),
            due_date=date(2025, 2, 15),
        )
    assert "invoice_id" in str(exc_info.value)


# =============================================================================
# FINANCIAL SUMMARY TESTS
# =============================================================================

def test_financial_summary_valid():
    """Test valid FinancialSummary creation."""
    summary = FinancialSummary(
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("100.00"),
        commission_rate=Decimal("0.15"),
        commission_amount=Decimal("150.00"),
        total_amount=Decimal("1100.00")
    )
    assert summary.subtotal == Decimal("1000.00")
    assert summary.commission_amount == Decimal("150.00")


def test_financial_summary_commission_validation():
    """Test FinancialSummary commission calculation validation."""
    with pytest.raises(ValidationError) as exc_info:
        FinancialSummary(
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("100.00"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("200.00"),  # Should be 150.00
            total_amount=Decimal("1100.00")
        )
    assert "commission_amount" in str(exc_info.value)


def test_financial_summary_negative_amounts():
    """Test FinancialSummary with negative amounts fails."""
    with pytest.raises(ValidationError):
        FinancialSummary(
            subtotal=Decimal("-100.00"),
            tax_amount=Decimal("10.00"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("15.00"),
            total_amount=Decimal("110.00")
        )


# =============================================================================
# EXTRACTED INVOICE TESTS
# =============================================================================

def test_extracted_invoice_valid():
    """Test valid ExtractedInvoice creation."""
    invoice = ExtractedInvoice(
        invoice_id="UE-2025-001234",
        vendor_name="Test Restaurant",
        vendor_type=VendorType.UBEREATS,
        invoice_date=date(2025, 1, 15),
        due_date=date(2025, 2, 15),
        currency="BRL",
        line_items=[
            LineItem(description="Food Sales", quantity=1, unit_price=Decimal("1000.00"))
        ],
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("50.00"),
        commission_rate=Decimal("0.15"),
        commission_amount=Decimal("150.00"),
        total_amount=Decimal("1050.00")
    )
    assert invoice.invoice_id == "UE-2025-001234"
    assert invoice.line_item_count == 1
    assert invoice.expected_commission == Decimal("150.00")


def test_extracted_invoice_date_validation():
    """Test ExtractedInvoice date validation."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractedInvoice(
            invoice_id="UE-2025-001234",
            vendor_name="Test Restaurant",
            invoice_date=date(2025, 2, 15),
            due_date=date(2025, 1, 15),  # Before invoice_date
            subtotal=Decimal("1000.00"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("150.00"),
            total_amount=Decimal("1050.00")
        )
    assert "due_date" in str(exc_info.value)


def test_extracted_invoice_computed_fields():
    """Test ExtractedInvoice computed fields."""
    invoice = ExtractedInvoice(
        invoice_id="UE-2025-001234",
        vendor_name="Test Restaurant",
        invoice_date=date(2025, 1, 15),
        due_date=date(2025, 2, 15),
        line_items=[
            LineItem(description="Item 1", quantity=1, unit_price=Decimal("100.00")),
            LineItem(description="Item 2", quantity=2, unit_price=Decimal("50.00"))
        ],
        subtotal=Decimal("200.00"),
        commission_rate=Decimal("0.10"),
        commission_amount=Decimal("20.00"),
        total_amount=Decimal("200.00")
    )
    assert invoice.line_item_count == 2
    assert invoice.expected_commission == Decimal("20.00")


# =============================================================================
# EXTRACTION RESULT TESTS
# =============================================================================

def test_extraction_result_success():
    """Test successful ExtractionResult."""
    invoice = ExtractedInvoice(
        invoice_id="UE-2025-001234",
        vendor_name="Test Restaurant",
        invoice_date=date(2025, 1, 15),
        due_date=date(2025, 2, 15),
        subtotal=Decimal("1000.00"),
        commission_rate=Decimal("0.15"),
        commission_amount=Decimal("150.00"),
        total_amount=Decimal("1000.00")
    )
    result = ExtractionResult(
        invoice=invoice,
        success=True,
        source=ExtractionSource.GEMINI,
        confidence=0.95,
        latency_ms=1500
    )
    assert result.success is True
    assert result.invoice is not None
    assert result.source == ExtractionSource.GEMINI
    assert result.confidence == 0.95


def test_extraction_result_failure():
    """Test failed ExtractionResult."""
    result = ExtractionResult(
        invoice=None,
        success=False,
        source=ExtractionSource.GEMINI,
        errors=["Failed to parse JSON response"],
        latency_ms=1200
    )
    assert result.success is False
    assert result.invoice is None
    assert len(result.errors) == 1


# =============================================================================
# VALIDATION RESULT TESTS
# =============================================================================

def test_validation_result_valid():
    """Test valid ValidationResult."""
    result = ValidationResult(
        is_valid=True,
        schema_valid=True,
        business_rules_valid=True,
        confidence_score=0.95
    )
    assert result.is_valid is True
    assert result.schema_valid is True
    assert result.business_rules_valid is True


def test_validation_result_with_errors():
    """Test ValidationResult with errors."""
    result = ValidationResult(
        is_valid=False,
        schema_valid=False,
        business_rules_valid=True,
        confidence_score=0.5,
        schema_errors=["Missing required field: invoice_id"],
        warnings=["Invoice ID format unusual"]
    )
    assert result.is_valid is False
    assert len(result.schema_errors) == 1
    assert len(result.warnings) == 1


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

def test_get_extraction_schema_json():
    """Test get_extraction_schema_json utility."""
    schema_json = get_extraction_schema_json()

    # Verify it's valid JSON
    schema = json.loads(schema_json)

    # Verify it contains expected fields
    assert "properties" in schema
    assert "invoice_id" in schema["properties"]
    assert "vendor_name" in schema["properties"]
    assert "line_items" in schema["properties"]
    assert "subtotal" in schema["properties"]


def test_get_extraction_schema_json_format():
    """Test get_extraction_schema_json returns properly formatted JSON."""
    schema_json = get_extraction_schema_json()

    # Should be indented (formatted)
    assert "\n" in schema_json
    assert "  " in schema_json  # 2-space indentation

    # Should be valid JSON
    schema = json.loads(schema_json)
    assert isinstance(schema, dict)
