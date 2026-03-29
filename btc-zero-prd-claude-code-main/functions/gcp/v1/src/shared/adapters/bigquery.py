"""BigQuery adapter with Protocol interface and GCP implementation.

Handles writing extracted invoice data to BigQuery tables.
"""

from typing import Any, Protocol

from shared.schemas.invoice import ExtractedInvoice


class BigQueryAdapter(Protocol):
    """Protocol for BigQuery operations."""

    def write_invoice(self, dataset: str, table: str, invoice: ExtractedInvoice, metadata: dict[str, Any]) -> str:
        """Write invoice record to BigQuery.

        Args:
            dataset: BigQuery dataset name
            table: Table name
            invoice: ExtractedInvoice instance
            metadata: Additional metadata (source_file, extraction_model, etc.)

        Returns:
            Row ID
        """
        ...

    def write_line_items(self, dataset: str, table: str, invoice_id: str, line_items: list[dict]) -> int:
        """Write line items to BigQuery.

        Args:
            dataset: BigQuery dataset name
            table: Table name
            invoice_id: Parent invoice ID
            line_items: List of line item dicts

        Returns:
            Number of rows inserted
        """
        ...

    def invoice_exists(self, dataset: str, table: str, invoice_id: str) -> bool:
        """Check if invoice already exists (deduplication).

        Args:
            dataset: BigQuery dataset name
            table: Table name
            invoice_id: Invoice ID to check

        Returns:
            True if invoice exists
        """
        ...


class GCPBigQueryAdapter:
    """Google BigQuery implementation."""

    def __init__(self, project_id: str | None = None):
        """Initialize BigQuery client.

        Args:
            project_id: GCP project ID (uses ADC default if None)
        """
        from google.cloud import bigquery

        self._client = bigquery.Client(project=project_id)
        self._project_id = project_id or self._client.project

    def write_invoice(
        self, dataset: str, table: str, invoice: ExtractedInvoice, metadata: dict[str, Any]
    ) -> str:
        """Write invoice record to BigQuery."""
        import uuid
        from datetime import datetime

        table_id = f"{self._project_id}.{dataset}.{table}"

        row = {
            "id": str(uuid.uuid4()),
            "invoice_id": invoice.invoice_id,
            "vendor_name": invoice.vendor_name,
            "vendor_type": invoice.vendor_type.value,
            "invoice_date": invoice.invoice_date.isoformat(),
            "due_date": invoice.due_date.isoformat(),
            "subtotal": float(invoice.subtotal),
            "tax_amount": float(invoice.tax_amount),
            "commission_rate": float(invoice.commission_rate),
            "commission_amount": float(invoice.commission_amount),
            "total_amount": float(invoice.total_amount),
            "currency": invoice.currency,
            "source_file": metadata.get("source_file", ""),
            "extraction_model": metadata.get("extraction_model", "gemini"),
            "extraction_latency_ms": metadata.get("extraction_latency_ms", 0),
            "confidence_score": metadata.get("confidence_score", 0.0),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        errors = self._client.insert_rows_json(table_id, [row])
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")

        return row["id"]

    def write_line_items(
        self, dataset: str, table: str, invoice_id: str, line_items: list[dict]
    ) -> int:
        """Write line items to BigQuery."""
        import uuid
        from datetime import datetime

        table_id = f"{self._project_id}.{dataset}.{table}"

        rows = []
        for item in line_items:
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "invoice_id": invoice_id,
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity", 1),
                    "unit_price": float(item.get("unit_price", 0)),
                    "amount": float(item.get("amount", 0)),
                    "created_at": datetime.utcnow().isoformat(),
                }
            )

        if rows:
            errors = self._client.insert_rows_json(table_id, rows)
            if errors:
                raise RuntimeError(f"BigQuery insert errors: {errors}")

        return len(rows)

    def invoice_exists(self, dataset: str, table: str, invoice_id: str) -> bool:
        """Check if invoice already exists."""
        query = f"""
            SELECT COUNT(*) as count
            FROM `{self._project_id}.{dataset}.{table}`
            WHERE invoice_id = @invoice_id
        """

        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("invoice_id", "STRING", invoice_id)]
        )

        result = self._client.query(query, job_config=job_config).result()
        for row in result:
            return row.count > 0
        return False

    def write_invoice_row(self, dataset: str, table: str, row: dict) -> str:
        """Write invoice row dict directly to BigQuery.

        Used when caller has already prepared the row dict.

        Args:
            dataset: BigQuery dataset name
            table: Table name
            row: Prepared row dict

        Returns:
            Invoice ID from row
        """
        table_id = f"{self._project_id}.{dataset}.{table}"

        errors = self._client.insert_rows_json(table_id, [row])
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")

        return row.get("invoice_id", "")

    def write_line_item_rows(self, dataset: str, table: str, rows: list[dict]) -> int:
        """Write line item rows directly to BigQuery.

        Args:
            dataset: BigQuery dataset name
            table: Table name
            rows: List of prepared row dicts

        Returns:
            Number of rows inserted
        """
        if not rows:
            return 0

        table_id = f"{self._project_id}.{dataset}.{table}"

        errors = self._client.insert_rows_json(table_id, rows)
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")

        return len(rows)

    def write_metrics(self, dataset: str, table: str, row: dict) -> None:
        """Write extraction metrics to BigQuery.

        Args:
            dataset: BigQuery dataset name
            table: Metrics table name
            row: Metrics row dict
        """
        table_id = f"{self._project_id}.{dataset}.{table}"

        errors = self._client.insert_rows_json(table_id, [row])
        if errors:
            raise RuntimeError(f"BigQuery metrics insert errors: {errors}")
