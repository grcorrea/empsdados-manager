"""Data extractor Cloud Run function.

Extracts structured invoice data using Gemini 2.5 Flash with
vendor-specific prompt templates. Validates output with Pydantic
and handles fallback to OpenRouter on primary LLM failure.
"""

from functions.data_extractor.extractor import (
    InvoiceExtractionResult,
    extract_invoice,
    load_prompt_template,
)

__all__ = ["extract_invoice", "load_prompt_template", "InvoiceExtractionResult"]
