"""Shared library for Invoice Processing Pipeline.

This package contains shared components used across all Cloud Run functions:
- schemas: Pydantic models for data validation
- adapters: Protocol interfaces for GCP services
- utils: Logging, configuration, and helpers
"""

from shared.schemas import (
    ExtractedInvoice,
    ExtractionResult,
    ExtractionSource,
    LineItem,
    ValidationResult,
    VendorType,
)
from shared.utils.config import Config, get_config
from shared.utils.logging import configure_logging

__all__ = [
    "ExtractedInvoice",
    "ExtractionResult",
    "ExtractionSource",
    "LineItem",
    "ValidationResult",
    "VendorType",
    "Config",
    "get_config",
    "configure_logging",
]
