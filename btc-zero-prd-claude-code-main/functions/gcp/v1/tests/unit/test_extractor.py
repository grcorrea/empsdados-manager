"""Unit tests for data extractor.

Tests LLM extraction orchestration with mocked adapters.
No actual LLM calls are made during unit tests.
"""

import json

import pytest

from functions.data_extractor.extractor import (
    InvoiceExtractionResult,
    _parse_and_validate,
    extract_invoice,
    get_available_prompts,
    load_prompt_template,
)
from shared.adapters.llm import LLMResponse
from shared.schemas.invoice import VendorType
from tests.fixtures.sample_invoices import SAMPLE_UBEREATS_INVOICE


class TestExtractInvoice:
    """Tests for extract_invoice function."""

    def test_successful_extraction(self, mock_llm_adapter, sample_png_data):
        """Test successful extraction with mocked LLM."""
        result = extract_invoice(
            images_data=[sample_png_data],
            vendor_type=VendorType.UBEREATS,
            llm_adapter=mock_llm_adapter,
        )

        assert isinstance(result, InvoiceExtractionResult)
        assert result.success
        assert result.invoice is not None
        assert result.invoice.invoice_id == "UE-2026-001234"
        assert result.provider == "gemini"

    def test_extraction_failure_with_fallback(
        self, mock_llm_adapter_failure, mock_llm_adapter, sample_png_data
    ):
        """Test fallback to secondary adapter on failure."""
        result = extract_invoice(
            images_data=[sample_png_data],
            vendor_type=VendorType.UBEREATS,
            llm_adapter=mock_llm_adapter_failure,
            fallback_adapter=mock_llm_adapter,
        )

        assert result.success
        assert result.invoice is not None

    def test_extraction_failure_no_fallback(
        self, mock_llm_adapter_failure, sample_png_data
    ):
        """Test failure is returned when no fallback available."""
        result = extract_invoice(
            images_data=[sample_png_data],
            vendor_type=VendorType.UBEREATS,
            llm_adapter=mock_llm_adapter_failure,
        )

        assert not result.success
        assert result.error is not None

    def test_both_adapters_fail(
        self, mock_llm_adapter_failure, sample_png_data
    ):
        """Test error details when both adapters fail."""
        result = extract_invoice(
            images_data=[sample_png_data],
            vendor_type=VendorType.UBEREATS,
            llm_adapter=mock_llm_adapter_failure,
            fallback_adapter=mock_llm_adapter_failure,
        )

        assert not result.success
        assert "Both providers failed" in result.error

    def test_latency_is_tracked(self, mock_llm_adapter, sample_png_data):
        """Test extraction latency is recorded."""
        result = extract_invoice(
            images_data=[sample_png_data],
            vendor_type=VendorType.UBEREATS,
            llm_adapter=mock_llm_adapter,
        )

        assert result.latency_ms > 0


class TestLoadPromptTemplate:
    """Tests for load_prompt_template function."""

    def test_ubereats_prompt_exists(self):
        """Test UberEats prompt template can be loaded."""
        prompt = load_prompt_template(VendorType.UBEREATS)

        assert "UberEats" in prompt or "Uber" in prompt
        assert "{" in prompt  # Contains schema placeholder filled

    def test_generic_fallback(self):
        """Test generic prompt is used for OTHER vendor type."""
        prompt = load_prompt_template(VendorType.OTHER)

        assert len(prompt) > 0

    def test_all_vendor_prompts_loadable(self):
        """Test all vendor types have loadable prompts."""
        for vendor_type in VendorType:
            prompt = load_prompt_template(vendor_type)
            assert len(prompt) > 100  # Prompt should be substantial

    def test_schema_is_embedded(self):
        """Test JSON schema is embedded in prompt."""
        prompt = load_prompt_template(VendorType.UBEREATS)

        assert "invoice_id" in prompt
        assert "vendor_name" in prompt
        assert "line_items" in prompt


class TestParseAndValidate:
    """Tests for _parse_and_validate function."""

    def test_valid_json_parsing(self):
        """Test valid JSON is parsed correctly."""
        content = json.dumps(SAMPLE_UBEREATS_INVOICE)

        invoice = _parse_and_validate(content)

        assert invoice.invoice_id == "UE-2026-001234"

    def test_markdown_code_block_handling(self):
        """Test markdown code blocks are stripped."""
        content = f"```json\n{json.dumps(SAMPLE_UBEREATS_INVOICE)}\n```"

        invoice = _parse_and_validate(content)

        assert invoice.invoice_id == "UE-2026-001234"

    def test_whitespace_handling(self):
        """Test leading/trailing whitespace is stripped."""
        content = f"\n\n  {json.dumps(SAMPLE_UBEREATS_INVOICE)}  \n\n"

        invoice = _parse_and_validate(content)

        assert invoice.invoice_id == "UE-2026-001234"

    def test_invalid_json_raises_error(self):
        """Test invalid JSON raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            _parse_and_validate("not valid json")

    def test_invalid_schema_raises_error(self):
        """Test JSON that doesn't match schema raises ValueError."""
        invalid_data = {"invalid": "structure"}

        with pytest.raises(ValueError, match="validation failed"):
            _parse_and_validate(json.dumps(invalid_data))


class TestGetAvailablePrompts:
    """Tests for get_available_prompts function."""

    def test_returns_list(self):
        """Test function returns a list of prompt names."""
        prompts = get_available_prompts()

        assert isinstance(prompts, list)
        assert len(prompts) > 0

    def test_includes_all_vendors(self):
        """Test all vendor prompts are available."""
        prompts = get_available_prompts()

        assert "ubereats" in prompts
        assert "doordash" in prompts
        assert "generic" in prompts
