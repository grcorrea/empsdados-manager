# Invoice Extractor - Technical Design Document

> **Version:** 1.0.0
> **Status:** APPROVED
> **Created:** January 29, 2026
> **Scope:** Local Python prototype for invoice data extraction

---

## Document Overview

| Attribute | Value |
|-----------|-------|
| **Prototype Name** | Invoice Extractor |
| **Purpose** | Extract structured data from UberEats invoices using Gemini 2.0 Flash |
| **Primary LLM** | Gemini 2.0 Flash via Vertex AI |
| **Fallback LLM** | OpenRouter (Claude 3.5 Sonnet) |
| **Output Format** | Validated JSON via Pydantic |
| **Target Accuracy** | >= 90% per field |

---

## 1. ARCHITECTURE

### 1.1 High-Level Data Flow

```
================================================================================
                    INVOICE EXTRACTOR - LOCAL PIPELINE
================================================================================

INPUT                  PROCESSING                              OUTPUT
-----                  ----------                              ------

  +---------+     +-----------+     +----------+     +----------+     +--------+
  |  TIFF/  |     |   IMAGE   |     |   LLM    |     |          |     |  JSON  |
  |   PNG   |---->| PROCESSOR |---->| GATEWAY  |---->|VALIDATOR |---->| OUTPUT |
  |  Files  |     |           |     |          |     |          |     |        |
  +---------+     +-----------+     +----------+     +----------+     +--------+
       |               |                 |                |               |
       |               |                 |                |               |
       v               v                 v                v               v
  data/input/    data/processed/   (API Calls)    (Pydantic)      data/output/
  *.tiff, *.png   *.png (RGB)                                      *.json


================================================================================
                         DETAILED STEP-BY-STEP FLOW
================================================================================

STEP 1: File Discovery
+-------------------+
| data/input/       |
| +---------------+ |
| | invoice.tiff  | |-----> Scan directory for TIFF/PNG files
| | invoice.pdf   | |       Supported: *.tiff, *.tif, *.png
| | invoice.png   | |
| +---------------+ |
+-------------------+

STEP 2: Image Processing
+-------------------+       +-------------------+
| image_processor   |       | data/processed/   |
|-------------------|       |-------------------|
| - Load TIFF/PNG   |       | invoice_p1.png    |
| - Split pages     |------>| invoice_p2.png    |
| - Convert to RGB  |       | invoice_p3.png    |
| - Optimize size   |       | (max 4096x4096)   |
+-------------------+       +-------------------+
         |
         v (Error?)
+-------------------+
| data/errors/      |
| processing_err.log|
+-------------------+

STEP 3: LLM Gateway
+-------------------+       +-------------------+
| llm_gateway       |       | API Response      |
|-------------------|       |-------------------|
| 1. Try Gemini     |       | {                 |
|    Flash 2.0      |       |   "invoice_id":   |
| 2. On failure:    |------>|   "vendor_name":  |
|    OpenRouter     |       |   "total_amount": |
| 3. Retry logic    |       |   ...             |
+-------------------+       | }                 |
         |                  +-------------------+
         v (All failed?)
+-------------------+
| data/errors/      |
| llm_error.json    |
+-------------------+

STEP 4: Validation
+-------------------+       +-------------------+
| validator         |       | Validation Result |
|-------------------|       |-------------------|
| L1: Schema valid? |       | - is_valid: bool  |
| L2: Business OK?  |------>| - confidence: 0.95|
| L3: Confidence?   |       | - errors: []      |
|                   |       | - warnings: []    |
+-------------------+       +-------------------+
         |
         v (Invalid?)
+-------------------+
| data/errors/      |
| validation_err.json|
+-------------------+

STEP 5: Output
+-------------------+       +-------------------+
| data/output/      |       | Final JSON        |
|-------------------|       |-------------------|
| UE-2025-001.json  |       | {                 |
| UE-2025-002.json  |<------| "invoice": {...}, |
| UE-2025-003.json  |       | "metadata": {...},|
|                   |       | "confidence": 0.95|
+-------------------+       | }                 |
                            +-------------------+


================================================================================
                           ERROR FLOW & FALLBACK
================================================================================

                    +-------------------+
                    |   Gemini 2.0      |
                    |   Flash (Primary) |
                    +-------------------+
                            |
                            v
                    +-------+-------+
                    | Success?      |
                    +-------+-------+
                      |           |
                     YES          NO
                      |           |
                      v           v
              +----------+   +-----------+
              | Parse    |   | Retry     |
              | Response |   | (max 2)   |
              +----------+   +-----------+
                                  |
                                  v
                          +-------+-------+
                          | Still Failed? |
                          +-------+-------+
                            |           |
                           NO          YES
                            |           |
                            v           v
                    +----------+   +-----------+
                    | Continue |   | OpenRouter|
                    |          |   | Fallback  |
                    +----------+   +-----------+
                                        |
                                        v
                                +-------+-------+
                                | Success?      |
                                +-------+-------+
                                  |           |
                                 YES          NO
                                  |           |
                                  v           v
                          +----------+   +-----------+
                          | Continue |   | Write to  |
                          |          |   | errors/   |
                          +----------+   +-----------+
```

### 1.2 Component Interaction Diagram

```
================================================================================
                         MODULE DEPENDENCIES
================================================================================

                          +-------------+
                          |   cli.py    |
                          |   (entry)   |
                          +------+------+
                                 |
                                 v
                          +-------------+
                          | extractor.py|
                          | (orchestrate)|
                          +------+------+
                                 |
          +----------------------+----------------------+
          |                      |                      |
          v                      v                      v
  +---------------+      +-------------+       +---------------+
  |image_processor|      | llm_gateway |       |   validator   |
  |     .py       |      |    .py      |       |     .py       |
  +---------------+      +-------------+       +---------------+
          |                      |                      |
          v                      v                      v
     +--------+            +----------+           +---------+
     | Pillow |            | Gemini   |           | Pydantic|
     +--------+            | OpenRouter|          +---------+
                           +----------+


================================================================================
                         DATA MODEL IMPORTS
================================================================================

  models.py
  +--------------------------------------------------+
  | - VendorType (Enum)                              |
  | - LineItem (BaseModel)                           |
  | - InvoiceHeader (BaseModel)                      |
  | - FinancialSummary (BaseModel)                   |
  | - ExtractedInvoice (BaseModel)                   |
  | - ExtractionResult (BaseModel)                   |
  | - ValidationResult (BaseModel)                   |
  +--------------------------------------------------+
          ^           ^           ^            ^
          |           |           |            |
  +-------+   +-------+   +-------+    +-------+
  |extractor| |validator| |llm_gateway| |cli    |
  +---------+ +---------+ +-----------+ +-------+
```

---

## 2. COMPONENTS

### 2.1 image_processor.py

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Convert TIFF/PDF images to optimized PNG format for LLM processing |
| **Dependencies** | `Pillow>=10.0.0` |
| **Error Handling** | Returns `ProcessingResult` with success/failure status and error details |

**Key Functions:**

```python
def load_image(file_path: Path) -> Image.Image | None:
    """Load image from TIFF/PNG file, handling multi-page TIFF."""

def split_multipage_tiff(tiff_path: Path, output_dir: Path) -> list[Path]:
    """Split multi-page TIFF into separate PNG files."""

def convert_to_rgb_png(image: Image.Image) -> Image.Image:
    """Convert image to RGB mode and optimize for LLM processing."""

def resize_for_llm(image: Image.Image, max_size: int = 4096) -> Image.Image:
    """Resize image to fit within LLM input limits while preserving aspect ratio."""

def process_invoice_image(
    input_path: Path,
    output_dir: Path
) -> ProcessingResult:
    """Full processing pipeline: load, split, convert, resize, save."""
```

**ProcessingResult Model:**

```python
@dataclass
class ProcessingResult:
    success: bool
    output_paths: list[Path]
    page_count: int
    original_path: Path
    error_message: str | None = None
```

---

### 2.2 llm_gateway.py

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Manage LLM API calls with Gemini primary and OpenRouter fallback |
| **Dependencies** | `google-generativeai>=0.8.0`, `openai>=1.0.0` (for OpenRouter) |
| **Error Handling** | Retry with exponential backoff, fallback chain, detailed error logging |

**Key Functions:**

```python
def call_gemini(
    prompt: str,
    image_paths: list[Path],
    config: GeminiConfig
) -> LLMResponse:
    """Call Gemini 2.0 Flash with image(s) and extraction prompt."""

def call_openrouter(
    prompt: str,
    image_paths: list[Path],
    config: OpenRouterConfig
) -> LLMResponse:
    """Fallback call to OpenRouter (Claude 3.5 Sonnet)."""

def extract_with_fallback(
    prompt: str,
    image_paths: list[Path],
    gemini_config: GeminiConfig,
    openrouter_config: OpenRouterConfig
) -> LLMResponse:
    """Try Gemini first, fallback to OpenRouter on failure."""

def encode_image_base64(image_path: Path) -> str:
    """Encode image to base64 for API transmission."""
```

**Configuration Models:**

```python
@dataclass
class GeminiConfig:
    model: str = "gemini-2.0-flash"
    project_id: str | None = None
    region: str = "us-central1"
    max_retries: int = 2
    timeout: int = 30

@dataclass
class OpenRouterConfig:
    api_key: str
    model: str = "anthropic/claude-3.5-sonnet"
    max_retries: int = 2
    timeout: int = 30

@dataclass
class LLMResponse:
    success: bool
    content: str | None
    provider: Literal["gemini", "openrouter"]
    latency_ms: int
    tokens_used: int | None = None
    error_message: str | None = None
```

---

### 2.3 extractor.py

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Orchestrate extraction pipeline with prompt management |
| **Dependencies** | `image_processor`, `llm_gateway`, `validator`, `models` |
| **Error Handling** | Aggregates errors from all components, writes to errors directory |

**Key Functions:**

```python
def load_prompt_template(vendor_type: str = "ubereats") -> str:
    """Load vendor-specific prompt template from prompts/ directory."""

def build_extraction_prompt(template: str, schema_json: str) -> str:
    """Combine prompt template with JSON schema for LLM."""

def extract_invoice(
    input_path: Path,
    output_dir: Path,
    processed_dir: Path,
    errors_dir: Path
) -> ExtractionResult:
    """Full extraction pipeline: process -> extract -> validate -> save."""

def batch_extract(
    input_dir: Path,
    output_dir: Path,
    processed_dir: Path,
    errors_dir: Path
) -> list[ExtractionResult]:
    """Process multiple invoices with progress tracking."""

def save_result(result: ExtractionResult, output_path: Path) -> None:
    """Save extraction result as JSON."""
```

**Pipeline Flow:**

```
1. Check for duplicate invoice_id
2. Process image(s) with image_processor
3. Load prompt template for vendor type
4. Call LLM gateway with image(s) and prompt
5. Parse JSON response from LLM
6. Validate with Pydantic schema
7. Run business rule validation
8. Calculate confidence score
9. Save to output or errors directory
```

---

### 2.4 validator.py

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Multi-layer validation: schema, business rules, confidence scoring |
| **Dependencies** | `models`, `pydantic` |
| **Error Handling** | Returns ValidationResult with all errors and warnings collected |

**Key Functions:**

```python
def validate_schema(data: dict) -> tuple[ExtractedInvoice | None, list[str]]:
    """Layer 1: Validate against Pydantic schema."""

def validate_business_rules(invoice: ExtractedInvoice) -> list[str]:
    """Layer 2: Cross-field consistency checks."""

def calculate_confidence(
    invoice: ExtractedInvoice,
    llm_confidence: float | None
) -> float:
    """Layer 3: Calculate overall extraction confidence."""

def validate_extraction(
    raw_json: str,
    llm_confidence: float | None = None
) -> ValidationResult:
    """Full validation pipeline combining all layers."""
```

**Business Rules Implemented:**

| Rule | Description |
|------|-------------|
| BR-001 | `total_amount` must equal `subtotal + tax_amount - commission_amount` (within tolerance) |
| BR-002 | `due_date` must be >= `invoice_date` |
| BR-003 | `commission_amount` must equal `subtotal * commission_rate` (within tolerance) |
| BR-004 | Sum of `line_items[].amount` must equal `subtotal` (within tolerance) |
| BR-005 | All amounts must be non-negative |
| BR-006 | `invoice_id` must match expected format (e.g., "UE-YYYY-NNNNNN") |

---

### 2.5 models.py

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Define all Pydantic schemas for extraction and validation |
| **Dependencies** | `pydantic>=2.0.0` |
| **Error Handling** | Pydantic validation errors with detailed field-level messages |

**Models Defined:**

| Model | Purpose |
|-------|---------|
| `VendorType` | Enum for platform types |
| `LineItem` | Individual line item with computed amount |
| `InvoiceHeader` | Header fields (ID, vendor, dates, currency) |
| `FinancialSummary` | Financial totals and calculations |
| `ExtractedInvoice` | Complete invoice combining all components |
| `ExtractionResult` | Wrapper with metadata, confidence, errors |
| `ValidationResult` | Multi-layer validation output |
| `ProcessingResult` | Image processing output |
| `LLMResponse` | LLM API response wrapper |

---

## 3. SCHEMAS (Pydantic Models)

### 3.1 Complete models.py Implementation

```python
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
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator
from typing_extensions import Self


# =============================================================================
# ENUMS
# =============================================================================

class VendorType(str, Enum):
    """Delivery platform vendor types."""
    UBEREATS = "ubereats"
    DOORDASH = "doordash"
    GRUBHUB = "grubhub"
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
        ...,
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Commission rate (0.0-1.0)"
    )
    commission_amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Commission amount"
    )
    total_amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total invoice amount"
    )

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
```

---

## 4. VALIDATION STRATEGY

### 4.1 Three-Layer Validation

```
================================================================================
                         VALIDATION LAYERS
================================================================================

                    +------------------------------------------+
                    |          LAYER 1: SCHEMA VALIDATION      |
                    |          (Pydantic v2)                   |
                    +------------------------------------------+
                    | - Type checking (str, int, Decimal, date)|
                    | - Required field presence                 |
                    | - Field constraints (min, max, pattern)   |
                    | - Enum value validation                   |
                    +------------------------------------------+
                                      |
                                      v (Pass?)
                    +------------------------------------------+
                    |          LAYER 2: BUSINESS RULES         |
                    |          (Cross-field validation)        |
                    +------------------------------------------+
                    | BR-001: total = subtotal + tax - commission|
                    | BR-002: due_date >= invoice_date          |
                    | BR-003: commission = subtotal * rate      |
                    | BR-004: line_items sum = subtotal         |
                    | BR-005: All amounts >= 0                  |
                    | BR-006: invoice_id format valid           |
                    +------------------------------------------+
                                      |
                                      v (Pass?)
                    +------------------------------------------+
                    |          LAYER 3: CONFIDENCE SCORING     |
                    |          (Quality assessment)            |
                    +------------------------------------------+
                    | - LLM-reported confidence (if available) |
                    | - Field completeness score               |
                    | - Consistency score (rules passed)       |
                    | - Final weighted confidence              |
                    +------------------------------------------+
                                      |
                                      v
                    +------------------------------------------+
                    |          VALIDATION RESULT               |
                    +------------------------------------------+
                    | {                                        |
                    |   "is_valid": true/false,                |
                    |   "schema_valid": true/false,            |
                    |   "business_rules_valid": true/false,    |
                    |   "confidence_score": 0.95,              |
                    |   "schema_errors": [...],                |
                    |   "business_rule_errors": [...],         |
                    |   "warnings": [...],                     |
                    |   "field_confidence": {...}              |
                    | }                                        |
                    +------------------------------------------+
```

### 4.2 Business Rules Detail

| Rule ID | Rule | Tolerance | Severity |
|---------|------|-----------|----------|
| BR-001 | `total_amount = subtotal + tax_amount` | +/- 0.05 | ERROR |
| BR-002 | `due_date >= invoice_date` | N/A | ERROR |
| BR-003 | `commission_amount = subtotal * commission_rate` | +/- 0.02 | ERROR |
| BR-004 | `sum(line_items.amount) = subtotal` | +/- 0.10 | WARNING |
| BR-005 | All monetary fields >= 0 | N/A | ERROR |
| BR-006 | `invoice_id` matches `^[A-Z]{2,4}-\d{4}-\d{4,8}$` | N/A | WARNING |

### 4.3 Confidence Scoring Algorithm

```python
def calculate_confidence(
    invoice: ExtractedInvoice,
    llm_confidence: float | None,
    business_rules_passed: int,
    business_rules_total: int
) -> float:
    """
    Calculate overall extraction confidence.

    Formula:
    confidence = (
        0.40 * completeness_score +
        0.30 * consistency_score +
        0.30 * llm_confidence
    )

    Where:
    - completeness_score: % of non-null required fields
    - consistency_score: % of business rules passed
    - llm_confidence: LLM-reported confidence (default 0.8)
    """
    # Completeness: Required fields present
    required_fields = [
        "invoice_id", "vendor_name", "invoice_date",
        "due_date", "subtotal", "total_amount"
    ]
    present = sum(1 for f in required_fields if getattr(invoice, f, None))
    completeness = present / len(required_fields)

    # Consistency: Business rules passed
    consistency = business_rules_passed / business_rules_total if business_rules_total > 0 else 1.0

    # LLM confidence (default if not provided)
    llm_conf = llm_confidence if llm_confidence is not None else 0.80

    # Weighted combination
    return (0.40 * completeness) + (0.30 * consistency) + (0.30 * llm_conf)
```

---

## 5. FILE STRUCTURE

### 5.1 Source Code Structure

```
src/invoice_extractor/
|
+-- __init__.py              # Package initialization, version, exports
|
+-- models.py                # All Pydantic schemas
|                            # - VendorType (Enum)
|                            # - LineItem, InvoiceHeader, FinancialSummary
|                            # - ExtractedInvoice, ExtractionResult
|                            # - ValidationResult
|                            # - get_extraction_schema_json()
|
+-- image_processor.py       # Image processing utilities
|                            # - load_image()
|                            # - split_multipage_tiff()
|                            # - convert_to_rgb_png()
|                            # - resize_for_llm()
|                            # - process_invoice_image()
|
+-- llm_gateway.py           # LLM API abstraction
|                            # - GeminiConfig, OpenRouterConfig
|                            # - call_gemini()
|                            # - call_openrouter()
|                            # - extract_with_fallback()
|
+-- extractor.py             # Extraction orchestration
|                            # - load_prompt_template()
|                            # - build_extraction_prompt()
|                            # - extract_invoice()
|                            # - batch_extract()
|
+-- validator.py             # Multi-layer validation
|                            # - validate_schema()
|                            # - validate_business_rules()
|                            # - calculate_confidence()
|                            # - validate_extraction()
|
+-- prompts/
|   +-- ubereats.txt         # UberEats extraction prompt template
|   +-- doordash.txt         # (future) DoorDash template
|   +-- grubhub.txt          # (future) Grubhub template
|
+-- cli.py                   # Command-line interface
                             # - extract (single file)
                             # - batch (directory)
                             # - validate (check JSON)
```

### 5.2 Data Directory Structure

```
data/
|
+-- input/                   # Raw input files
|   +-- invoice_001.tiff     # Multi-page TIFF
|   +-- invoice_002.png      # Single page PNG
|   +-- invoice_003.pdf      # PDF (future support)
|
+-- processed/               # Converted PNG files
|   +-- invoice_001_p1.png   # Page 1 from TIFF
|   +-- invoice_001_p2.png   # Page 2 from TIFF
|   +-- invoice_002.png      # Converted PNG
|
+-- output/                  # Extraction results
|   +-- UE-2025-001234.json  # Successful extraction
|   +-- UE-2025-001235.json  # Named by invoice_id
|
+-- errors/                  # Failed extractions
    +-- invoice_001_error.json    # Processing failure
    +-- invoice_003_error.json    # Validation failure
```

### 5.3 Project Root Structure

```
btc-zero-prd-claude-code/
|
+-- src/
|   +-- invoice_extractor/   # Main package (see 5.1)
|
+-- tests/
|   +-- __init__.py
|   +-- conftest.py          # Pytest fixtures
|   +-- test_models.py       # Schema unit tests
|   +-- test_image_processor.py
|   +-- test_llm_gateway.py
|   +-- test_validator.py
|   +-- test_extractor.py    # Integration tests
|   +-- fixtures/
|       +-- sample_invoice.tiff
|       +-- expected_output.json
|
+-- data/                    # Data directories (see 5.2)
|
+-- design/
|   +-- invoice-extractor-requirements.md
|   +-- invoice-extractor-design.md   # This document
|
+-- pyproject.toml           # Package configuration
+-- README.md                # Usage documentation
```

### 5.4 pyproject.toml Configuration

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "invoice-extractor"
version = "0.1.0"
description = "AI-powered invoice data extraction using Gemini 2.0 Flash"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
authors = [
    { name = "Data Engineering Team" }
]

dependencies = [
    "pydantic>=2.0.0",
    "pillow>=10.0.0",
    "google-generativeai>=0.8.0",
    "openai>=1.0.0",
    "click>=8.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
]

[project.scripts]
invoice-extract = "invoice_extractor.cli:main"

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

---

## 6. IMPLEMENTATION CHECKLIST

### Phase 1: Foundation (Setup)

| # | Task | Component | Dependencies | Status |
|---|------|-----------|--------------|--------|
| 1.1 | Create project structure with pyproject.toml | setup | None | [ ] |
| 1.2 | Create data/ directories (input, processed, output, errors) | setup | 1.1 | [ ] |
| 1.3 | Implement VendorType enum and ExtractionSource enum | models.py | 1.1 | [ ] |
| 1.4 | Implement LineItem model with computed amount | models.py | 1.3 | [ ] |
| 1.5 | Implement InvoiceHeader model with date validator | models.py | 1.3 | [ ] |
| 1.6 | Implement FinancialSummary model with calculation validators | models.py | 1.3 | [ ] |
| 1.7 | Implement ExtractedInvoice model combining all components | models.py | 1.4-1.6 | [ ] |
| 1.8 | Implement ExtractionResult and ValidationResult models | models.py | 1.7 | [ ] |
| 1.9 | Add get_extraction_schema_json() utility function | models.py | 1.7 | [ ] |
| 1.10 | Create basic CLI skeleton with Click | cli.py | 1.1 | [ ] |
| 1.11 | Write unit tests for all models | tests/test_models.py | 1.3-1.9 | [ ] |

**Phase 1 Exit Criteria:**
- All Pydantic models pass validation tests
- CLI skeleton runs: `invoice-extract --help`
- `get_extraction_schema_json()` produces valid JSON schema

---

### Phase 2: Core Pipeline

| # | Task | Component | Dependencies | Status |
|---|------|-----------|--------------|--------|
| 2.1 | Implement load_image() for TIFF and PNG | image_processor.py | Phase 1 | [ ] |
| 2.2 | Implement split_multipage_tiff() | image_processor.py | 2.1 | [ ] |
| 2.3 | Implement convert_to_rgb_png() and resize_for_llm() | image_processor.py | 2.1 | [ ] |
| 2.4 | Implement process_invoice_image() orchestration | image_processor.py | 2.1-2.3 | [ ] |
| 2.5 | Create GeminiConfig and OpenRouterConfig dataclasses | llm_gateway.py | Phase 1 | [ ] |
| 2.6 | Implement call_gemini() with retry logic | llm_gateway.py | 2.5 | [ ] |
| 2.7 | Implement call_openrouter() with retry logic | llm_gateway.py | 2.5 | [ ] |
| 2.8 | Implement extract_with_fallback() | llm_gateway.py | 2.6-2.7 | [ ] |
| 2.9 | Create UberEats prompt template | prompts/ubereats.txt | Phase 1 | [ ] |
| 2.10 | Implement load_prompt_template() | extractor.py | 2.9 | [ ] |
| 2.11 | Implement build_extraction_prompt() | extractor.py | 2.10 | [ ] |
| 2.12 | Implement validate_schema() | validator.py | Phase 1 | [ ] |
| 2.13 | Implement validate_business_rules() (BR-001 to BR-006) | validator.py | 2.12 | [ ] |
| 2.14 | Implement calculate_confidence() | validator.py | 2.12 | [ ] |
| 2.15 | Implement validate_extraction() orchestration | validator.py | 2.12-2.14 | [ ] |
| 2.16 | Implement extract_invoice() full pipeline | extractor.py | 2.4, 2.8, 2.11, 2.15 | [ ] |

**Phase 2 Exit Criteria:**
- Image processor converts TIFF to PNG correctly
- LLM gateway calls Gemini successfully with test image
- Validator catches all 6 business rule violations
- Full extraction pipeline works end-to-end with sample invoice

---

### Phase 3: Testing and Polish

| # | Task | Component | Dependencies | Status |
|---|------|-----------|--------------|--------|
| 3.1 | Write unit tests for image_processor | tests/test_image_processor.py | 2.1-2.4 | [ ] |
| 3.2 | Write unit tests for llm_gateway (with mocks) | tests/test_llm_gateway.py | 2.5-2.8 | [ ] |
| 3.3 | Write unit tests for validator | tests/test_validator.py | 2.12-2.15 | [ ] |
| 3.4 | Write integration tests with sample invoice | tests/test_extractor.py | 2.16 | [ ] |
| 3.5 | Add error handling for corrupt image files | image_processor.py | 3.1 | [ ] |
| 3.6 | Add error handling for API timeouts | llm_gateway.py | 3.2 | [ ] |
| 3.7 | Add error handling for malformed JSON responses | extractor.py | 3.4 | [ ] |
| 3.8 | Implement CLI `extract` command for single file | cli.py | 2.16 | [ ] |
| 3.9 | Implement CLI `batch` command for directory | cli.py | 3.8 | [ ] |
| 3.10 | Implement CLI `validate` command for JSON files | cli.py | 2.15 | [ ] |
| 3.11 | Add progress bar for batch processing | cli.py | 3.9 | [ ] |
| 3.12 | Add verbose logging option | cli.py | 3.8-3.10 | [ ] |
| 3.13 | Create pytest fixtures with sample data | tests/conftest.py | 3.1-3.4 | [ ] |
| 3.14 | Run Ruff linting and fix issues | all | 3.1-3.12 | [ ] |
| 3.15 | Verify >= 80% test coverage | all | 3.1-3.4 | [ ] |
| 3.16 | Write CLI usage documentation | README.md | 3.8-3.12 | [ ] |

**Phase 3 Exit Criteria:**
- All tests pass with >= 80% coverage
- Ruff reports no errors
- CLI commands work: `invoice-extract extract`, `invoice-extract batch`, `invoice-extract validate`
- Sample invoice extracts with >= 90% field accuracy

---

## Implementation Timeline

| Phase | Estimated Duration | Dependencies |
|-------|-------------------|--------------|
| Phase 1: Foundation | 1-2 days | None |
| Phase 2: Core Pipeline | 3-4 days | Phase 1 complete |
| Phase 3: Testing & Polish | 2-3 days | Phase 2 complete |
| **Total** | **6-9 days** | - |

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Gemini API rate limits | Medium | Medium | OpenRouter fallback, exponential backoff |
| Low extraction accuracy | Medium | High | Iterate on prompt, validate with ground truth |
| Multi-page TIFF handling | Low | Medium | Test with multi-page samples early |
| JSON parsing failures | Medium | Medium | Robust error handling, raw response logging |

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Extraction accuracy (per field) | >= 90% | Compare to ground truth |
| Processing latency P95 | < 5 seconds | CLI timing output |
| Validation failure rate | < 5% | Error directory count |
| Test coverage | >= 80% | pytest-cov report |

---

## Document Metadata

| Field | Value |
|-------|-------|
| **Version** | 1.0.0 |
| **Author** | the-planner |
| **Created** | 2026-01-29 |
| **Status** | APPROVED |
| **Confidence** | 0.95 (HIGH) |
| **Sources** | design/invoice-extractor-requirements.md, notes/summary-requirements.md, .claude/kb/pydantic/, .claude/kb/gemini/, .claude/kb/openrouter/ |

---

> **Next Step:** Execute `/dev` with this design document to begin Phase 1 implementation.
