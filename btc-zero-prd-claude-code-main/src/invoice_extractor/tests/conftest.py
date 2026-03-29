"""pytest fixtures for invoice_extractor tests.

Provides mock adapters and sample data for unit testing
without requiring GCP credentials or network access.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from ..models import ExtractedInvoice, LineItem, VendorType
from .fixtures.sample_invoices import (
    SAMPLE_EXTRACTED_INVOICE,
    SAMPLE_UBEREATS_INVOICE,
    create_minimal_tiff,
    create_multipage_tiff,
)


@pytest.fixture
def mock_storage_adapter():
    """Mock storage adapter for unit tests."""
    adapter = MagicMock()
    adapter.read.return_value = b"fake image data"
    adapter.write.return_value = "gs://test-bucket/test-path.png"
    adapter.copy.return_value = "gs://archive-bucket/test-path.tiff"
    adapter.delete.return_value = True
    adapter.exists.return_value = True
    return adapter


@pytest.fixture
def mock_messaging_adapter():
    """Mock messaging adapter for unit tests."""
    adapter = MagicMock()
    adapter.publish.return_value = "message-id-123"
    return adapter


@pytest.fixture
def mock_llm_adapter():
    """Mock LLM adapter that returns successful extraction."""
    import json

    adapter = MagicMock()
    # Create a mock response object
    response = MagicMock()
    response.success = True
    response.content = json.dumps(SAMPLE_UBEREATS_INVOICE)
    response.provider = "gemini"
    response.latency_ms = 500
    response.confidence = 0.95
    adapter.extract.return_value = response
    return adapter


@pytest.fixture
def mock_llm_adapter_failure():
    """Mock LLM adapter that returns failure."""
    adapter = MagicMock()
    response = MagicMock()
    response.success = False
    response.content = None
    response.provider = "gemini"
    response.latency_ms = 1000
    response.error = "Model overloaded"
    adapter.extract.return_value = response
    return adapter


@pytest.fixture
def mock_bigquery_adapter():
    """Mock BigQuery adapter for unit tests."""
    adapter = MagicMock()
    adapter.invoice_exists.return_value = False
    adapter.write_invoice.return_value = None
    adapter.write_line_items.return_value = None
    adapter.write_metrics.return_value = None
    return adapter


@pytest.fixture
def mock_bigquery_adapter_duplicate():
    """Mock BigQuery adapter that reports duplicate invoice."""
    adapter = MagicMock()
    adapter.invoice_exists.return_value = True
    return adapter


@pytest.fixture
def sample_invoice() -> ExtractedInvoice:
    """Sample validated invoice for testing."""
    return SAMPLE_EXTRACTED_INVOICE


@pytest.fixture
def sample_invoice_dict() -> dict:
    """Sample invoice as dictionary (JSON-like)."""
    return SAMPLE_UBEREATS_INVOICE


@pytest.fixture
def sample_tiff_data() -> bytes:
    """Sample TIFF image bytes for testing."""
    return create_minimal_tiff()


@pytest.fixture
def sample_multipage_tiff_data() -> bytes:
    """Sample multi-page TIFF image bytes for testing."""
    return create_multipage_tiff(pages=3)


@pytest.fixture
def sample_png_data() -> bytes:
    """Sample PNG image bytes for testing."""
    import io
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = MagicMock()
    config.project_id = "test-project"
    config.region = "us-central1"
    config.input_bucket = "test-input-bucket"
    config.processed_bucket = "test-processed-bucket"
    config.archive_bucket = "test-archive-bucket"
    config.failed_bucket = "test-failed-bucket"
    config.uploaded_topic = "invoice-uploaded"
    config.converted_topic = "invoice-converted"
    config.classified_topic = "invoice-classified"
    config.extracted_topic = "invoice-extracted"
    config.gemini_model = "gemini-2.5-flash"
    config.openrouter_api_key = "test-key"
    config.dataset = "invoices"
    config.invoices_table = "extracted_invoices"
    config.line_items_table = "line_items"
    config.metrics_table = "extraction_metrics"
    return config


@pytest.fixture
def sample_cloud_event_data():
    """Sample CloudEvent data for testing Pub/Sub triggers."""
    import base64
    import json

    message_data = {
        "bucket": "test-input-bucket",
        "name": "invoices/UE-2026-001234.tiff",
    }

    return {
        "message": {
            "data": base64.b64encode(json.dumps(message_data).encode()).decode(),
            "messageId": "123456789",
            "publishTime": datetime.utcnow().isoformat() + "Z",
        }
    }
