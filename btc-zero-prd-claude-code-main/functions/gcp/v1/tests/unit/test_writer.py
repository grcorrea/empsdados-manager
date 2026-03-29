"""Unit tests for BigQuery writer.

Tests invoice persistence logic with mocked BigQuery adapter.
No actual BigQuery calls are made during unit tests.
"""

import pytest

from functions.bigquery_writer.writer import (
    WriteResult,
    _prepare_invoice_row,
    _prepare_line_item_rows,
    write_extraction_metrics,
    write_invoice_to_bigquery,
)
from shared.schemas.invoice import VendorType


class TestWriteInvoiceToBigQuery:
    """Tests for write_invoice_to_bigquery function."""

    def test_successful_write(self, mock_bigquery_adapter, sample_invoice):
        """Test successful invoice write."""
        result = write_invoice_to_bigquery(
            invoice=sample_invoice,
            bq_adapter=mock_bigquery_adapter,
            dataset="test_dataset",
            invoices_table="invoices",
            line_items_table="line_items",
        )

        assert isinstance(result, WriteResult)
        assert result.success
        assert result.invoice_id == sample_invoice.invoice_id
        assert not result.is_duplicate
        assert result.rows_written > 0

    def test_duplicate_detection(self, mock_bigquery_adapter_duplicate, sample_invoice):
        """Test duplicate invoice is detected and skipped."""
        result = write_invoice_to_bigquery(
            invoice=sample_invoice,
            bq_adapter=mock_bigquery_adapter_duplicate,
            dataset="test_dataset",
            invoices_table="invoices",
            line_items_table="line_items",
        )

        assert result.success
        assert result.is_duplicate
        assert result.rows_written == 0

    def test_write_calls_adapter_methods(self, mock_bigquery_adapter, sample_invoice):
        """Test all adapter methods are called correctly."""
        write_invoice_to_bigquery(
            invoice=sample_invoice,
            bq_adapter=mock_bigquery_adapter,
            dataset="test_dataset",
            invoices_table="invoices",
            line_items_table="line_items",
        )

        mock_bigquery_adapter.invoice_exists.assert_called_once()
        mock_bigquery_adapter.write_invoice_row.assert_called_once()
        mock_bigquery_adapter.write_line_item_rows.assert_called_once()

    def test_metadata_included_in_write(self, mock_bigquery_adapter, sample_invoice):
        """Test metadata is included in invoice row."""
        write_invoice_to_bigquery(
            invoice=sample_invoice,
            bq_adapter=mock_bigquery_adapter,
            dataset="test_dataset",
            invoices_table="invoices",
            line_items_table="line_items",
            source_file="gs://bucket/file.tiff",
            extraction_model="gemini-2.5-flash",
            extraction_latency_ms=500,
            confidence_score=0.95,
        )

        call_args = mock_bigquery_adapter.write_invoice_row.call_args
        invoice_row = call_args[0][2]

        assert invoice_row["source_file"] == "gs://bucket/file.tiff"
        assert invoice_row["extraction_model"] == "gemini-2.5-flash"
        assert invoice_row["extraction_latency_ms"] == 500
        assert invoice_row["confidence_score"] == 0.95

    def test_error_handling(self, mock_bigquery_adapter, sample_invoice):
        """Test errors are captured in result."""
        mock_bigquery_adapter.write_invoice_row.side_effect = Exception("BQ Error")

        result = write_invoice_to_bigquery(
            invoice=sample_invoice,
            bq_adapter=mock_bigquery_adapter,
            dataset="test_dataset",
            invoices_table="invoices",
            line_items_table="line_items",
        )

        assert not result.success
        assert "BQ Error" in result.error


class TestPrepareInvoiceRow:
    """Tests for _prepare_invoice_row function."""

    def test_all_fields_present(self, sample_invoice):
        """Test all required fields are in row dict."""
        row = _prepare_invoice_row(sample_invoice)

        required_fields = [
            "invoice_id",
            "vendor_name",
            "vendor_type",
            "invoice_date",
            "due_date",
            "currency",
            "subtotal",
            "tax_amount",
            "commission_rate",
            "commission_amount",
            "total_amount",
            "line_items_count",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            assert field in row

    def test_decimal_to_float_conversion(self, sample_invoice):
        """Test Decimal fields are converted to float."""
        row = _prepare_invoice_row(sample_invoice)

        assert isinstance(row["subtotal"], float)
        assert isinstance(row["commission_rate"], float)
        assert isinstance(row["total_amount"], float)

    def test_date_to_iso_conversion(self, sample_invoice):
        """Test date fields are converted to ISO strings."""
        row = _prepare_invoice_row(sample_invoice)

        assert isinstance(row["invoice_date"], str)
        assert isinstance(row["due_date"], str)
        assert "-" in row["invoice_date"]

    def test_vendor_type_as_string(self, sample_invoice):
        """Test vendor type is converted to string value."""
        row = _prepare_invoice_row(sample_invoice)

        assert isinstance(row["vendor_type"], str)
        assert row["vendor_type"] == "ubereats"


class TestPrepareLineItemRows:
    """Tests for _prepare_line_item_rows function."""

    def test_correct_number_of_rows(self, sample_invoice):
        """Test one row per line item."""
        rows = _prepare_line_item_rows(sample_invoice)

        assert len(rows) == len(sample_invoice.line_items)

    def test_line_numbers_sequential(self, sample_invoice):
        """Test line numbers are sequential starting at 1."""
        rows = _prepare_line_item_rows(sample_invoice)

        for i, row in enumerate(rows):
            assert row["line_number"] == i + 1

    def test_invoice_id_linked(self, sample_invoice):
        """Test all rows link to parent invoice."""
        rows = _prepare_line_item_rows(sample_invoice)

        for row in rows:
            assert row["invoice_id"] == sample_invoice.invoice_id

    def test_amounts_as_float(self, sample_invoice):
        """Test decimal amounts are converted to float."""
        rows = _prepare_line_item_rows(sample_invoice)

        for row in rows:
            assert isinstance(row["unit_price"], float)
            assert isinstance(row["amount"], float)


class TestWriteExtractionMetrics:
    """Tests for write_extraction_metrics function."""

    def test_successful_metrics_write(self, mock_bigquery_adapter):
        """Test metrics are written successfully."""
        result = write_extraction_metrics(
            bq_adapter=mock_bigquery_adapter,
            dataset="test_dataset",
            metrics_table="metrics",
            invoice_id="TEST-001",
            vendor_type=VendorType.UBEREATS,
            source_file="gs://bucket/file.tiff",
            extraction_model="gemini-2.5-flash",
            extraction_latency_ms=500,
            confidence_score=0.95,
            success=True,
        )

        assert result is True
        mock_bigquery_adapter.write_metrics.assert_called_once()

    def test_failure_metrics_include_error(self, mock_bigquery_adapter):
        """Test failed extractions include error message."""
        write_extraction_metrics(
            bq_adapter=mock_bigquery_adapter,
            dataset="test_dataset",
            metrics_table="metrics",
            invoice_id="TEST-001",
            vendor_type=VendorType.UBEREATS,
            source_file="gs://bucket/file.tiff",
            extraction_model="gemini-2.5-flash",
            extraction_latency_ms=0,
            confidence_score=0.0,
            success=False,
            error_message="LLM timeout",
        )

        call_args = mock_bigquery_adapter.write_metrics.call_args
        metrics_row = call_args[0][2]

        assert metrics_row["success"] is False
        assert metrics_row["error_message"] == "LLM timeout"

    def test_metrics_write_error_handled(self, mock_bigquery_adapter):
        """Test metrics write errors don't raise exceptions."""
        mock_bigquery_adapter.write_metrics.side_effect = Exception("BQ Error")

        result = write_extraction_metrics(
            bq_adapter=mock_bigquery_adapter,
            dataset="test_dataset",
            metrics_table="metrics",
            invoice_id="TEST-001",
            vendor_type=VendorType.UBEREATS,
            source_file="gs://bucket/file.tiff",
            extraction_model="gemini-2.5-flash",
            extraction_latency_ms=500,
            confidence_score=0.95,
            success=True,
        )

        assert result is False
