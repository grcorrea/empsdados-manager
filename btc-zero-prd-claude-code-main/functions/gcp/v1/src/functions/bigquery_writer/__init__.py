"""BigQuery writer Cloud Run function.

Persists extracted invoice data to BigQuery with duplicate detection,
validation, and metrics logging. Final stage of the invoice processing pipeline.
"""

from functions.bigquery_writer.writer import write_invoice_to_bigquery

__all__ = ["write_invoice_to_bigquery"]
