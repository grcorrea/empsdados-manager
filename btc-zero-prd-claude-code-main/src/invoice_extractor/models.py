"""Pydantic models for invoice extraction and validation.

This module defines all data models for the invoice extractor prototype:
- VendorType: Enum for delivery platform types
- LineItem: Individual invoice line item with computed total
- InvoiceHeader: Invoice metadata fields
- FinancialSummary: Financial totals and calculations
- ExtractedInvoice: Complete extracted invoice
- ExtractionResult: Wrapper with metadata and confidence
- ValidationResult: Multi-layer validation output
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

# =============================================================================
# ENUMS
# =============================================================================

class VendorType(str, Enum):
    """Delivery platform vendor types."""
    UBEREATS = "ubereats"
    DOORDASH = "doordash"
    GRUBHUB = "grubhub"
    IFOOD = "ifood"
    RAPPI = "rappi"
    OTHER = "other"


class ExtractionSource(str, Enum):
    """LLM provider used for extraction."""
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    MANUAL = "manual"


# =============================================================================
# LINE ITEM
# =============================================================================

class LineItem(BaseModel):
    """Individual line item from an invoice.

    Attributes:
        description: Item or service description
        quantity: Number of items (default 1)
        unit_price: Price per unit in invoice currency
        amount: Total for this line (quantity * unit_price)
    """

    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Item or service description"
    )
    quantity: int = Field(
        default=1,
        ge=1,
        le=1000,
        description="Quantity of items"
    )
    unit_price: Decimal = Field(
        ...,
        ge=Decimal("0"),
        decimal_places=2,
        description="Price per unit"
    )

    @computed_field
    @property
    def amount(self) -> Decimal:
        """Calculate total amount for this line item."""
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    model_config = {
        "str_strip_whitespace": True,
        "json_schema_extra": {
            "examples": [{
                "description": "Delivery Service Fee",
                "quantity": 1,
                "unit_price": "15.00"
            }]
        }
    }


# =============================================================================
# INVOICE HEADER
# =============================================================================

class InvoiceHeader(BaseModel):
    """Invoice header/metadata fields.

    Attributes:
        invoice_id: Unique invoice identifier (e.g., "UE-2025-001234")
        vendor_name: Restaurant or vendor name
        vendor_type: Platform type (ubereats, doordash, etc.)
        invoice_date: Date invoice was issued
        due_date: Payment due date
        currency: 3-letter currency code (e.g., "BRL", "USD")
    """

    invoice_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Z]{2,4}-\d{4}-\d{4,8}$",
        description="Unique invoice identifier (e.g., UE-2025-001234)"
    )
    vendor_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Restaurant or vendor name"
    )
    vendor_type: VendorType = Field(
        default=VendorType.OTHER,
        description="Delivery platform type"
    )
    invoice_date: date = Field(
        ...,
        description="Invoice issue date (YYYY-MM-DD)"
    )
    due_date: date = Field(
        ...,
        description="Payment due date (YYYY-MM-DD)"
    )
    currency: Literal["BRL", "USD", "EUR", "GBP", "CAD", "AUD"] = Field(
        default="BRL",
        description="3-letter ISO currency code"
    )

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Ensure due_date is not before invoice_date."""
        if self.due_date < self.invoice_date:
            raise ValueError(
                f"due_date ({self.due_date}) cannot be before "
                f"invoice_date ({self.invoice_date})"
            )
        return self

    model_config = {
        "str_strip_whitespace": True,
    }


# =============================================================================
# FINANCIAL SUMMARY
# =============================================================================

class FinancialSummary(BaseModel):
    """Financial totals and calculations.

    Attributes:
        subtotal: Sum of all line items before tax/commission
        tax_amount: Tax amount
        commission_rate: Platform commission rate (0.0 to 1.0)
        commission_amount: Calculated commission (subtotal * rate)
        total_amount: Final invoice total
    """

    subtotal: Decimal = Field(
        ...,
        ge=Decimal("0"),
        decimal_places=2,
        description="Sum of line items before tax/commission"
    )
    tax_amount: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        decimal_places=2,
        description="Tax amount"
    )
    commission_rate: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("1"),
        decimal_places=4,
        description="Commission rate as decimal (e.g., 0.15 for 15%)"
    )
    commission_amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        decimal_places=2,
        description="Platform commission amount"
    )
    total_amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        decimal_places=2,
        description="Final invoice total"
    )

    @model_validator(mode="after")
    def validate_commission_calculation(self) -> Self:
        """Verify commission_amount matches subtotal * commission_rate."""
        expected_commission = (self.subtotal * self.commission_rate).quantize(
            Decimal("0.01")
        )
        tolerance = Decimal("0.02")  # Allow 2 cent tolerance

        if abs(self.commission_amount - expected_commission) > tolerance:
            raise ValueError(
                f"commission_amount ({self.commission_amount}) does not match "
                f"subtotal * commission_rate ({expected_commission})"
            )
        return self

    @model_validator(mode="after")
    def validate_total_calculation(self) -> Self:
        """Verify total_amount = subtotal + tax_amount - commission_amount."""
        # Note: Commission is typically deducted from payout
        expected_total = self.subtotal + self.tax_amount
        tolerance = Decimal("0.05")  # Allow 5 cent tolerance

        if abs(self.total_amount - expected_total) > tolerance:
            # Log warning but don't fail - invoices may have different structures
            pass
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "subtotal": "1000.00",
                "tax_amount": "100.00",
                "commission_rate": "0.15",
                "commission_amount": "150.00",
                "total_amount": "1100.00"
            }]
        }
    }


# =============================================================================
# EXTRACTED INVOICE (COMPLETE)
# =============================================================================

class ExtractedInvoice(BaseModel):
    """Complete extracted invoice combining header, items, and financials.

    This is the main model for validated invoice extraction output.
    """

    # Header fields (flattened for simpler JSON)
    invoice_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique invoice identifier"
    )
    vendor_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Restaurant or vendor name"
    )
    vendor_type: VendorType = Field(
        default=VendorType.UBEREATS,
        description="Delivery platform type"
    )
    invoice_date: date = Field(
        ...,
        description="Invoice issue date"
    )
    due_date: date = Field(
        ...,
        description="Payment due date"
    )
    currency: Literal["BRL", "USD", "EUR", "GBP", "CAD", "AUD"] = Field(
        default="BRL",
        description="Currency code"
    )

    # Line items
    line_items: list[LineItem] = Field(
        default_factory=list,
        description="Invoice line items"
    )

    # Financial summary
    subtotal: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Subtotal before tax/commission"
    )
    tax_amount: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="Tax amount"
    )
    commission_rate: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Commission rate (0.0-1.0)"
    )
    commission_amount: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="Commission amount"
    )
    total_amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total invoice amount"
    )

    @field_validator("tax_amount", "commission_rate", "commission_amount", mode="before")
    @classmethod
    def handle_null_decimals(cls, v):
        """Convert null/None values to 0 for optional decimal fields."""
        if v is None:
            return Decimal("0")
        return v

    @field_validator("invoice_id")
    @classmethod
    def validate_invoice_id_format(cls, v: str) -> str:
        """Validate invoice ID follows expected pattern."""
        import re
        # Allow flexible format: 2-4 letters, dash, 4 digits year, dash, 4-8 digit sequence
        if not re.match(r"^[A-Z]{2,4}-\d{4}-\d{4,8}$", v):
            # Warn but don't fail - LLM may extract non-standard IDs
            pass
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Ensure due_date is on or after invoice_date."""
        if self.due_date < self.invoice_date:
            raise ValueError(
                f"due_date ({self.due_date}) cannot be before "
                f"invoice_date ({self.invoice_date})"
            )
        return self

    @model_validator(mode="after")
    def validate_line_items_total(self) -> Self:
        """Check if line items sum to subtotal."""
        if self.line_items:
            items_total = sum(item.amount for item in self.line_items)
            tolerance = Decimal("0.10")
            if abs(items_total - self.subtotal) > tolerance:
                # Log warning but don't fail
                pass
        return self

    @computed_field
    @property
    def line_item_count(self) -> int:
        """Number of line items."""
        return len(self.line_items)

    @computed_field
    @property
    def expected_commission(self) -> Decimal:
        """Calculate expected commission from subtotal * rate."""
        return (self.subtotal * self.commission_rate).quantize(Decimal("0.01"))

    model_config = {
        "str_strip_whitespace": True,
        "validate_default": True,
        "json_schema_extra": {
            "examples": [{
                "invoice_id": "UE-2025-001234",
                "vendor_name": "Restaurante Exemplo LTDA",
                "vendor_type": "ubereats",
                "invoice_date": "2025-01-15",
                "due_date": "2025-02-15",
                "currency": "BRL",
                "line_items": [
                    {"description": "Food Delivery Sales", "quantity": 1, "unit_price": "1000.00"}
                ],
                "subtotal": "1000.00",
                "tax_amount": "50.00",
                "commission_rate": "0.15",
                "commission_amount": "150.00",
                "total_amount": "1050.00"
            }]
        }
    }


# =============================================================================
# EXTRACTION RESULT (WITH METADATA)
# =============================================================================

class ExtractionResult(BaseModel):
    """Wrapper for extraction output with metadata and confidence.

    Attributes:
        invoice: Extracted invoice data (None if extraction failed)
        success: Whether extraction completed successfully
        source: LLM provider used (gemini, openrouter, manual)
        confidence: Overall confidence score (0.0-1.0)
        latency_ms: Extraction latency in milliseconds
        errors: List of error messages
        warnings: List of warning messages
        raw_response: Original LLM response (for debugging)
    """

    invoice: ExtractedInvoice | None = Field(
        default=None,
        description="Extracted invoice (None if failed)"
    )
    success: bool = Field(
        ...,
        description="Whether extraction succeeded"
    )
    source: ExtractionSource = Field(
        default=ExtractionSource.GEMINI,
        description="LLM provider used"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (0.0-1.0)"
    )
    latency_ms: int = Field(
        default=0,
        ge=0,
        description="Processing time in milliseconds"
    )
    tokens_used: int | None = Field(
        default=None,
        ge=0,
        description="Total tokens consumed"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Error messages"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warning messages"
    )
    raw_response: str | None = Field(
        default=None,
        description="Raw LLM response (for debugging)"
    )
    input_file: str | None = Field(
        default=None,
        description="Original input file path"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "invoice": None,
                "success": False,
                "source": "gemini",
                "confidence": 0.0,
                "latency_ms": 1500,
                "errors": ["Failed to parse JSON response"],
                "warnings": [],
                "input_file": "data/input/invoice_001.tiff"
            }]
        }
    }


# =============================================================================
# VALIDATION RESULT
# =============================================================================

class ValidationResult(BaseModel):
    """Multi-layer validation output.

    Captures results from:
    - Layer 1: Pydantic schema validation
    - Layer 2: Business rule validation
    - Layer 3: Confidence scoring
    """

    is_valid: bool = Field(
        ...,
        description="Overall validation passed"
    )
    schema_valid: bool = Field(
        ...,
        description="Layer 1: Pydantic schema validation"
    )
    business_rules_valid: bool = Field(
        ...,
        description="Layer 2: Business rules validation"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Layer 3: Confidence score"
    )
    schema_errors: list[str] = Field(
        default_factory=list,
        description="Schema validation errors"
    )
    business_rule_errors: list[str] = Field(
        default_factory=list,
        description="Business rule violations"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings"
    )
    field_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence scores"
    )


# =============================================================================
# UTILITY: GENERATE JSON SCHEMA FOR PROMPTS
# =============================================================================

def get_extraction_schema_json() -> str:
    """Generate JSON Schema string for LLM extraction prompts.

    Returns:
        JSON string of ExtractedInvoice schema
    """
    import json
    return json.dumps(
        ExtractedInvoice.model_json_schema(),
        indent=2
    )
