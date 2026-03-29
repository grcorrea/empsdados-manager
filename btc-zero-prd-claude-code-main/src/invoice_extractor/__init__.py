"""Invoice Extractor - AI-powered invoice data extraction.

This package provides tools for extracting structured data from delivery
platform invoices using Gemini 2.0 Flash with OpenRouter fallback.

Usage:
    import sys
    sys.path.insert(0, "src")
    from invoice_extractor import extract_invoice, ExtractedInvoice
    from invoice_extractor import GeminiConfig, OpenRouterConfig

    result = extract_invoice(
        input_path=Path("invoice.tiff"),
        output_dir=Path("output"),
        processed_dir=Path("processed"),
        errors_dir=Path("errors"),
        gemini_config=GeminiConfig(),
        openrouter_config=OpenRouterConfig(api_key="sk-...")
    )
"""

__version__ = "0.1.0"

# Core extraction functions
from .extractor import (
    extract_invoice,
    batch_extract,
    save_result,
)

# Data models
from .models import (
    ExtractedInvoice,
    ExtractionResult,
    ExtractionSource,
    LineItem,
    ValidationResult,
    VendorType,
)

# Configuration
from .llm_gateway import (
    GeminiConfig,
    OpenRouterConfig,
)

# Validation
from .validator import validate_extraction

__all__ = [
    # Version
    "__version__",
    # Core functions
    "extract_invoice",
    "batch_extract",
    "save_result",
    "validate_extraction",
    # Models
    "ExtractedInvoice",
    "ExtractionResult",
    "ExtractionSource",
    "LineItem",
    "ValidationResult",
    "VendorType",
    # Configuration
    "GeminiConfig",
    "OpenRouterConfig",
]
