"""BigQuery write logic for invoice persistence.

Handles writing extracted invoices and line items to BigQuery
with duplicate detection and metrics logging.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from shared.adapters.bigquery import BigQueryAdapter
from shared.schemas.invoice import ExtractedInvoice, VendorType

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    """Result of BigQuery write operation.

    Attributes:
        success: Whether write succeeded
        invoice_id: Invoice ID written
        is_duplicate: Whether invoice was already in BigQuery
        rows_written: Number of rows written (invoice + line items)
        error: Error message if failed
    """

    success: bool
    invoice_id: str
    is_duplicate: bool
    rows_written: int
    error: str | None = None


def write_invoice_to_bigquery(
    invoice: ExtractedInvoice,
    bq_adapter: BigQueryAdapter,
    dataset: str,
    invoices_table: str,
    line_items_table: str,
    *,
    source_file: str | None = None,
    extraction_model: str | None = None,
    extraction_latency_ms: int | None = None,
    confidence_score: float | None = None,
) -> WriteResult:
    """Write extracted invoice to BigQuery.

    Performs duplicate check, writes invoice and line items,
    and logs metrics. Returns result with status details.

    Args:
        invoice: Validated ExtractedInvoice to persist
        bq_adapter: BigQuery adapter for database operations
        dataset: BigQuery dataset name
        invoices_table: Table name for invoices
        line_items_table: Table name for line items
        source_file: Original file URI (for metrics)
        extraction_model: LLM model used (for metrics)
        extraction_latency_ms: Extraction latency (for metrics)
        confidence_score: Extraction confidence (for metrics)

    Returns:
        WriteResult with operation status
    """
    try:
        if bq_adapter.invoice_exists(dataset, invoices_table, invoice.invoice_id):
            logger.warning(
                "Duplicate invoice detected - skipping write",
                extra={
                    "invoice_id": invoice.invoice_id,
                    "vendor_type": invoice.vendor_type.value,
                },
            )
            return WriteResult(
                success=True,
                invoice_id=invoice.invoice_id,
                is_duplicate=True,
                rows_written=0,
            )

        invoice_row = _prepare_invoice_row(
            invoice,
            source_file=source_file,
            extraction_model=extraction_model,
            extraction_latency_ms=extraction_latency_ms,
            confidence_score=confidence_score,
        )

        bq_adapter.write_invoice_row(dataset, invoices_table, invoice_row)

        line_item_rows = _prepare_line_item_rows(invoice)
        if line_item_rows:
            bq_adapter.write_line_item_rows(dataset, line_items_table, line_item_rows)

        total_rows = 1 + len(line_item_rows)

        logger.info(
            "Invoice written to BigQuery",
            extra={
                "invoice_id": invoice.invoice_id,
                "vendor_type": invoice.vendor_type.value,
                "line_items_count": len(line_item_rows),
                "total_rows": total_rows,
            },
        )

        return WriteResult(
            success=True,
            invoice_id=invoice.invoice_id,
            is_duplicate=False,
            rows_written=total_rows,
        )

    except Exception as e:
        logger.exception(
            "BigQuery write failed",
            extra={
                "invoice_id": invoice.invoice_id,
                "error": str(e),
            },
        )
        return WriteResult(
            success=False,
            invoice_id=invoice.invoice_id,
            is_duplicate=False,
            rows_written=0,
            error=str(e),
        )


def _prepare_invoice_row(
    invoice: ExtractedInvoice,
    *,
    source_file: str | None = None,
    extraction_model: str | None = None,
    extraction_latency_ms: int | None = None,
    confidence_score: float | None = None,
) -> dict:
    """Prepare invoice row for BigQuery insert.

    Converts ExtractedInvoice to BigQuery-compatible dict with
    additional metadata fields.

    Args:
        invoice: Validated invoice data
        source_file: Original file URI
        extraction_model: LLM model used
        extraction_latency_ms: Processing time
        confidence_score: Extraction confidence

    Returns:
        Dict ready for BigQuery insert
    """
    now = datetime.now(timezone.utc)

    return {
        "invoice_id": invoice.invoice_id,
        "vendor_name": invoice.vendor_name,
        "vendor_type": invoice.vendor_type.value,
        "invoice_date": invoice.invoice_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "currency": invoice.currency,
        "subtotal": float(invoice.subtotal),
        "tax_amount": float(invoice.tax_amount),
        "commission_rate": float(invoice.commission_rate),
        "commission_amount": float(invoice.commission_amount),
        "total_amount": float(invoice.total_amount),
        "line_items_count": len(invoice.line_items),
        "source_file": source_file,
        "extraction_model": extraction_model,
        "extraction_latency_ms": extraction_latency_ms,
        "confidence_score": confidence_score,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


def _prepare_line_item_rows(invoice: ExtractedInvoice) -> list[dict]:
    """Prepare line item rows for BigQuery insert.

    Each line item is linked to the parent invoice by invoice_id.

    Args:
        invoice: Invoice containing line items

    Returns:
        List of dicts ready for BigQuery insert
    """
    now = datetime.now(timezone.utc)
    rows = []

    for idx, item in enumerate(invoice.line_items):
        rows.append({
            "invoice_id": invoice.invoice_id,
            "line_number": idx + 1,
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "amount": float(item.amount),
            "created_at": now.isoformat(),
        })

    return rows


def write_extraction_metrics(
    bq_adapter: BigQueryAdapter,
    dataset: str,
    metrics_table: str,
    *,
    invoice_id: str,
    vendor_type: VendorType,
    source_file: str,
    extraction_model: str,
    extraction_latency_ms: int,
    confidence_score: float,
    success: bool,
    error_message: str | None = None,
) -> bool:
    """Write extraction metrics to BigQuery for monitoring.

    Logs each extraction attempt for performance tracking
    and accuracy analysis.

    Args:
        bq_adapter: BigQuery adapter
        dataset: Dataset name
        metrics_table: Metrics table name
        invoice_id: Extracted invoice ID
        vendor_type: Detected vendor type
        source_file: Original file URI
        extraction_model: LLM model used
        extraction_latency_ms: Processing time
        confidence_score: Extraction confidence
        success: Whether extraction succeeded
        error_message: Error details if failed

    Returns:
        True if metrics written successfully
    """
    try:
        now = datetime.now(timezone.utc)

        metrics_row = {
            "invoice_id": invoice_id,
            "vendor_type": vendor_type.value,
            "source_file": source_file,
            "extraction_model": extraction_model,
            "extraction_latency_ms": extraction_latency_ms,
            "confidence_score": confidence_score,
            "success": success,
            "error_message": error_message,
            "created_at": now.isoformat(),
        }

        bq_adapter.write_metrics(dataset, metrics_table, metrics_row)

        logger.debug(
            "Extraction metrics logged",
            extra={
                "invoice_id": invoice_id,
                "extraction_latency_ms": extraction_latency_ms,
            },
        )

        return True

    except Exception as e:
        logger.warning(
            "Failed to write extraction metrics",
            extra={
                "invoice_id": invoice_id,
                "error": str(e),
            },
        )
        return False
