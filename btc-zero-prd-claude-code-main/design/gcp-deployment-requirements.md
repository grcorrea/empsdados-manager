# GCP Deployment Requirements

> **Version:** 1.2.0 | **Created:** January 29, 2026 | **Updated:** January 29, 2026
> **Purpose:** Developer reference for building the Invoice Processing Pipeline (All Vendors)
> **Source:** Consolidated from [notes/summary-requirements.md](../notes/summary-requirements.md)

---

## Architectural Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **LLM Model** | Gemini 2.5 Flash | Newer model with improved reasoning, better accuracy |
| **Observability** | Cloud Logging | Native GCP logging and monitoring for MVP |
| **Brand Scope** | All 5 vendors from day 1 | UberEats, DoorDash, Grubhub, iFood, Rappi + Other |
| **Error Handling** | Retry → Fallback → DLQ | 3 retries, OpenRouter fallback, then dead-letter queue |
| **Deployment** | Dev environment only | Single environment for MVP, add prod later |
| **Architecture** | 4 separate Cloud Run services | Independent scaling, isolated failures |
| **Code Patterns** | Pydantic + Adapters | Validation + cloud service abstraction for portability |

---

## Table of Contents

1. [Event Flow Diagram](#1-event-flow-diagram)
2. [Cloud Run Functions](#2-cloud-run-functions)
3. [GCS Buckets](#3-gcs-buckets)
4. [Pub/Sub Topics](#4-pubsub-topics)
5. [Invoice Extraction Schema](#5-invoice-extraction-schema)
6. [Success Metrics](#6-success-metrics)
7. [Implementation Notes](#7-implementation-notes)

---

## 1. Event Flow Diagram

```text
+==============================================================================+
|                    INVOICE PROCESSING PIPELINE - EVENT FLOW                   |
+==============================================================================+

  FILE UPLOAD                                                         DATA STORE
      |                                                                    |
      v                                                                    v
+----------+    +----------------+    +-----------+    +-----------+    +-------+
|   GCS    |    |  TIFF-TO-PNG   |    | INVOICE   |    |   DATA    |    |  BIG  |
| invoices |===>|   CONVERTER    |===>| CLASSIFIER|===>| EXTRACTOR |===>| QUERY |
|  -input  |    |                |    |           |    |           |    |       |
+----------+    +----------------+    +-----------+    +-----------+    +-------+
     |                |                    |                |
     |                |                    |                |
     |                v                    v                v
     |           +----------+         +----------+    +----------+
     |           |   GCS    |         |   GCS    |    |   GCS    |
     |           | invoices |         | invoices |    | invoices |
     |           |-processed|         | -archive |    | -failed  |
     |           +----------+         +----------+    +----------+
     |
     +-------------------+-------------------+-------------------+
                         |                   |                   |
                         v                   v                   v
                  +-----------+       +-----------+       +-----------+
                  |  invoice- |       |  invoice- |       |  invoice- |
                  |  uploaded |       | converted |       | classified|
                  |  (topic)  |       |  (topic)  |       |  (topic)  |
                  +-----------+       +-----------+       +-----------+
                         |                   |                   |
                         v                   v                   v
                  +-----------+       +-----------+       +-----------+
                  | tiff-to-  |       |  invoice- |       |   data-   |
                  |   png-    |       | classifier|       | extractor |
                  | converter |       |           |       |           |
                  +-----------+       +-----------+       +-----------+


  DETAILED MESSAGE FLOW:
  ======================

  1. TIFF file lands in gs://invoices-input
           |
           v
  2. GCS trigger publishes to `invoice-uploaded` topic
           |
           v
  3. tiff-to-png-converter subscribes, converts file
           |
           +---> Writes PNG to gs://invoices-processed
           |
           v
  4. Publishes to `invoice-converted` topic
           |
           v
  5. invoice-classifier subscribes, validates & classifies
           |
           +---> Archives original to gs://invoices-archive
           |
           v
  6. Publishes to `invoice-classified` topic (includes vendor_type)
           |
           v
  7. data-extractor subscribes, calls Gemini 2.5 Flash
           |
           +---> On failure: writes to gs://invoices-failed
           |
           v
  8. Publishes to `invoice-extracted` topic (includes JSON payload)
           |
           v
  9. bigquery-writer subscribes, validates with Pydantic, writes to BQ

```

---

## 2. Cloud Run Functions

### 2.1 Overview

| # | Function Name | Purpose | Trigger | Owner |
|---|---------------|---------|---------|-------|
| 1 | tiff-to-png-converter | Convert TIFF to PNG format | Pub/Sub: invoice-uploaded | Joao Silva |
| 2 | invoice-classifier | Validate structure and detect vendor type | Pub/Sub: invoice-converted | Ana Costa |
| 3 | data-extractor | Extract structured data using Gemini 2.5 Flash | Pub/Sub: invoice-classified | Ana Costa |
| 4 | bigquery-writer | Write validated data to BigQuery | Pub/Sub: invoice-extracted | Joao Silva |

---

### 2.2 Function Details

#### Function 1: tiff-to-png-converter

| Attribute | Value |
|-----------|-------|
| **Name** | `tiff-to-png-converter` |
| **Purpose** | Convert multi-page TIFF files to PNG format for LLM processing |
| **Runtime** | Python 3.11 |
| **Memory** | 512 MB |
| **Timeout** | 60 seconds |
| **Min Instances** | 0 |
| **Max Instances** | 10 |

**Inputs:**

| Input | Source | Format |
|-------|--------|--------|
| Pub/Sub message | `invoice-uploaded` topic | JSON with GCS file path |
| TIFF file | GCS bucket | Binary TIFF (single or multi-page) |

**Outputs:**

| Output | Destination | Format |
|--------|-------------|--------|
| PNG file(s) | `gs://invoices-processed` | Binary PNG |
| Event message | `invoice-converted` topic | JSON |

**Technology Stack:**

```text
- Pillow (PIL): TIFF to PNG conversion
- google-cloud-storage: GCS operations
- google-cloud-pubsub: Event publishing
- functions-framework: Cloud Run entry point
```

**Output Message Schema:**

```json
{
  "source_file": "gs://invoices-input/invoice-001.tiff",
  "converted_files": [
    "gs://invoices-processed/invoice-001_page1.png",
    "gs://invoices-processed/invoice-001_page2.png"
  ],
  "page_count": 2,
  "timestamp": "2026-01-29T10:30:00Z"
}
```

---

#### Function 2: invoice-classifier

| Attribute | Value |
|-----------|-------|
| **Name** | `invoice-classifier` |
| **Purpose** | Validate image quality and classify invoice by vendor type |
| **Runtime** | Python 3.11 |
| **Memory** | 256 MB |
| **Timeout** | 30 seconds |
| **Min Instances** | 0 |
| **Max Instances** | 10 |

**Inputs:**

| Input | Source | Format |
|-------|--------|--------|
| Pub/Sub message | `invoice-converted` topic | JSON with converted file paths |
| PNG file(s) | GCS bucket | Binary PNG |

**Outputs:**

| Output | Destination | Format |
|--------|-------------|--------|
| Archived original | `gs://invoices-archive` | Binary TIFF |
| Event message | `invoice-classified` topic | JSON |

**Technology Stack:**

```text
- Rule-based classifier (MVP): Pattern matching on filename/content
- Optional: Gemini 2.5 Flash for complex classification
- google-cloud-storage: GCS operations
- google-cloud-pubsub: Event publishing
```

**Vendor Types (Enum) - All supported from MVP:**

| Value | Description | Volume % |
|-------|-------------|----------|
| `ubereats` | UberEats invoice | ~40% |
| `doordash` | DoorDash invoice | ~20% |
| `grubhub` | Grubhub invoice | ~15% |
| `ifood` | iFood invoice (Brazil) | ~15% |
| `rappi` | Rappi invoice (LATAM) | ~8% |
| `other` | Unrecognized vendor (manual review) | ~2% |

**Output Message Schema:**

```json
{
  "source_file": "gs://invoices-input/invoice-001.tiff",
  "converted_files": [
    "gs://invoices-processed/invoice-001_page1.png"
  ],
  "vendor_type": "ubereats",
  "quality_score": 0.95,
  "archived_to": "gs://invoices-archive/2026/01/invoice-001.tiff",
  "timestamp": "2026-01-29T10:30:05Z"
}
```

---

#### Function 3: data-extractor

| Attribute | Value |
|-----------|-------|
| **Name** | `data-extractor` |
| **Purpose** | Extract structured invoice data using Gemini 2.5 Flash |
| **Runtime** | Python 3.11 |
| **Memory** | 1024 MB |
| **Timeout** | 120 seconds |
| **Min Instances** | 0 |
| **Max Instances** | 20 |

**Inputs:**

| Input | Source | Format |
|-------|--------|--------|
| Pub/Sub message | `invoice-classified` topic | JSON with vendor type |
| PNG file(s) | GCS bucket | Binary PNG |

**Outputs:**

| Output | Destination | Format |
|--------|-------------|--------|
| Failed file copy | `gs://invoices-failed` | Binary PNG (on failure) |
| Event message | `invoice-extracted` topic | JSON with extracted data |

**Technology Stack:**

```text
- google-cloud-aiplatform: Vertex AI / Gemini 2.5 Flash
- openrouter (fallback): Alternative LLM provider (Claude 3.5 Sonnet)
- pydantic: Output validation
- google-cloud-storage: GCS operations
- google-cloud-pubsub: Event publishing
```

**Prompt Selection Logic:**

```text
vendor_type == "ubereats"  --> prompts/ubereats_extraction.txt
vendor_type == "doordash"  --> prompts/doordash_extraction.txt
vendor_type == "grubhub"   --> prompts/grubhub_extraction.txt
vendor_type == "ifood"     --> prompts/ifood_extraction.txt
vendor_type == "rappi"     --> prompts/rappi_extraction.txt
vendor_type == "other"     --> prompts/generic_extraction.txt
```

**Output Message Schema:**

```json
{
  "source_file": "gs://invoices-input/invoice-001.tiff",
  "vendor_type": "ubereats",
  "extraction_model": "gemini-2.5-flash",
  "extraction_latency_ms": 1200,
  "token_usage": {
    "input_tokens": 1500,
    "output_tokens": 350
  },
  "extracted_data": {
    "invoice_id": "UE-2026-001234",
    "vendor_name": "Restaurant ABC",
    "...": "see full schema below"
  },
  "confidence_score": 0.95,
  "timestamp": "2026-01-29T10:30:10Z"
}
```

---

#### Function 4: bigquery-writer

| Attribute | Value |
|-----------|-------|
| **Name** | `bigquery-writer` |
| **Purpose** | Validate and write extracted data to BigQuery |
| **Runtime** | Python 3.11 |
| **Memory** | 256 MB |
| **Timeout** | 30 seconds |
| **Min Instances** | 0 |
| **Max Instances** | 10 |

**Inputs:**

| Input | Source | Format |
|-------|--------|--------|
| Pub/Sub message | `invoice-extracted` topic | JSON with extracted data |

**Outputs:**

| Output | Destination | Format |
|--------|-------------|--------|
| Invoice record | BigQuery table | Structured row |
| Line items | BigQuery table | Structured rows |

**Technology Stack:**

```text
- google-cloud-bigquery: BigQuery SDK
- pydantic: Input validation
- google-cloud-pubsub: Message acknowledgment
```

**BigQuery Tables:**

| Table | Purpose |
|-------|---------|
| `invoices.extracted_invoices` | Main invoice records |
| `invoices.line_items` | Invoice line item details |
| `invoices.extraction_metrics` | Processing metrics |

---

## 3. GCS Buckets

### 3.1 Bucket Overview

| Bucket Name | Purpose | Retention | Access Pattern |
|-------------|---------|-----------|----------------|
| `invoices-input` | Raw TIFF files landing zone | 30 days | Write: External, Read: tiff-to-png-converter |
| `invoices-processed` | Converted PNG files | 90 days | Write: tiff-to-png-converter, Read: data-extractor |
| `invoices-archive` | Original files for compliance | 7 years | Write: invoice-classifier, Read: Manual/Audit |
| `invoices-failed` | Failed processing for review | Until resolved | Write: data-extractor, Read: Manual review |

### 3.2 Bucket Configuration Details

#### invoices-input

```text
Name:           ${PROJECT_ID}-invoices-input
Location:       us-central1
Storage Class:  STANDARD
Lifecycle:
  - Delete objects older than 30 days
Notifications:
  - Pub/Sub topic: invoice-uploaded (on finalize)
IAM:
  - Service account (upload): roles/storage.objectCreator
  - Cloud Run SA: roles/storage.objectViewer
```

#### invoices-processed

```text
Name:           ${PROJECT_ID}-invoices-processed
Location:       us-central1
Storage Class:  STANDARD
Lifecycle:
  - Delete objects older than 90 days
IAM:
  - tiff-to-png-converter SA: roles/storage.objectCreator
  - data-extractor SA: roles/storage.objectViewer
```

#### invoices-archive

```text
Name:           ${PROJECT_ID}-invoices-archive
Location:       us-central1
Storage Class:  ARCHIVE (after 30 days)
Lifecycle:
  - Transition to ARCHIVE class after 30 days
  - Delete objects older than 7 years
IAM:
  - invoice-classifier SA: roles/storage.objectCreator
  - Audit role: roles/storage.objectViewer
```

#### invoices-failed

```text
Name:           ${PROJECT_ID}-invoices-failed
Location:       us-central1
Storage Class:  STANDARD
Lifecycle:
  - None (manual cleanup required)
IAM:
  - data-extractor SA: roles/storage.objectCreator
  - Operations team: roles/storage.objectAdmin
```

---

## 4. Pub/Sub Topics

### 4.1 Topic Overview

| Topic Name | Triggered By | Subscribed By | Message Schema |
|------------|--------------|---------------|----------------|
| `invoice-uploaded` | GCS notification (file finalize) | tiff-to-png-converter | GCS event |
| `invoice-converted` | tiff-to-png-converter | invoice-classifier | Custom JSON |
| `invoice-classified` | invoice-classifier | data-extractor | Custom JSON |
| `invoice-extracted` | data-extractor | bigquery-writer | Custom JSON |

### 4.2 Topic Configuration Details

#### invoice-uploaded

```text
Topic:          invoice-uploaded
Purpose:        New file notification from GCS
Trigger:        GCS bucket notification (finalize event)
Subscriber:     tiff-to-png-converter (push subscription)

Subscription Config:
  - Type: Push
  - Ack deadline: 60 seconds
  - Retry policy:
      Minimum backoff: 10 seconds
      Maximum backoff: 600 seconds
  - Dead letter topic: invoice-uploaded-dlq
  - Max delivery attempts: 5
```

#### invoice-converted

```text
Topic:          invoice-converted
Purpose:        TIFF to PNG conversion complete
Trigger:        tiff-to-png-converter function
Subscriber:     invoice-classifier (push subscription)

Message Attributes:
  - source_file: Original GCS path
  - page_count: Number of pages converted

Subscription Config:
  - Type: Push
  - Ack deadline: 30 seconds
  - Retry policy:
      Minimum backoff: 10 seconds
      Maximum backoff: 300 seconds
  - Dead letter topic: invoice-converted-dlq
  - Max delivery attempts: 5
```

#### invoice-classified

```text
Topic:          invoice-classified
Purpose:        Invoice classification complete
Trigger:        invoice-classifier function
Subscriber:     data-extractor (push subscription)

Message Attributes:
  - vendor_type: ubereats|doordash|grubhub|other
  - quality_score: Image quality assessment

Subscription Config:
  - Type: Push
  - Ack deadline: 120 seconds
  - Retry policy:
      Minimum backoff: 10 seconds
      Maximum backoff: 600 seconds
  - Dead letter topic: invoice-classified-dlq
  - Max delivery attempts: 3
```

#### invoice-extracted

```text
Topic:          invoice-extracted
Purpose:        Data extraction complete
Trigger:        data-extractor function
Subscriber:     bigquery-writer (push subscription)

Message Attributes:
  - extraction_model: Model used for extraction
  - confidence_score: Extraction confidence

Subscription Config:
  - Type: Push
  - Ack deadline: 30 seconds
  - Retry policy:
      Minimum backoff: 10 seconds
      Maximum backoff: 300 seconds
  - Dead letter topic: invoice-extracted-dlq
  - Max delivery attempts: 5
```

### 4.3 Dead Letter Queues (DLQ)

| DLQ Topic | Source Topic | Retention | Alert Threshold |
|-----------|--------------|-----------|-----------------|
| `invoice-uploaded-dlq` | invoice-uploaded | 14 days | > 10 messages |
| `invoice-converted-dlq` | invoice-converted | 14 days | > 10 messages |
| `invoice-classified-dlq` | invoice-classified | 14 days | > 5 messages |
| `invoice-extracted-dlq` | invoice-extracted | 14 days | > 5 messages |

---

## 5. Invoice Extraction Schema

### 5.1 Main Invoice Schema

| Field | Type | Required | Validation | Example |
|-------|------|----------|------------|---------|
| `invoice_id` | String | Yes | Pattern: `^[A-Z]{2}-\d{4}-\d{6}$` | "UE-2026-001234" |
| `vendor_name` | String | Yes | Min length: 2, Max length: 200 | "Restaurant ABC" |
| `vendor_type` | Enum | Yes | `ubereats\|doordash\|grubhub\|other` | "ubereats" |
| `invoice_date` | Date | Yes | ISO 8601 format | "2026-01-15" |
| `due_date` | Date | Yes | ISO 8601 format, >= invoice_date | "2026-02-15" |
| `subtotal` | Float | Yes | >= 0, precision: 2 decimal places | 1234.56 |
| `tax_amount` | Float | Yes | >= 0, precision: 2 decimal places | 123.45 |
| `commission_rate` | Float | Yes | 0.0 - 1.0 | 0.15 |
| `commission_amount` | Float | Yes | >= 0, precision: 2 decimal places | 185.18 |
| `total_amount` | Float | Yes | >= 0, precision: 2 decimal places | 1358.01 |
| `currency` | String | Yes | ISO 4217 (3 chars) | "BRL" |
| `line_items` | Array | Yes | Min items: 1 | See below |

### 5.2 Line Item Schema

| Field | Type | Required | Validation | Example |
|-------|------|----------|------------|---------|
| `description` | String | Yes | Max length: 500 | "Delivery Fee" |
| `quantity` | Integer | Yes | > 0 | 1 |
| `unit_price` | Float | Yes | >= 0 | 5.99 |
| `amount` | Float | Yes | = quantity * unit_price | 5.99 |

### 5.3 Pydantic Model Definition

```python
from datetime import date
from enum import Enum
from typing import List
from pydantic import BaseModel, Field, field_validator


class VendorType(str, Enum):
    UBEREATS = "ubereats"
    DOORDASH = "doordash"
    GRUBHUB = "grubhub"
    OTHER = "other"


class LineItem(BaseModel):
    description: str = Field(..., max_length=500)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    amount: float = Field(..., ge=0)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v, info):
        expected = info.data.get("quantity", 0) * info.data.get("unit_price", 0)
        if abs(v - expected) > 0.01:
            raise ValueError(f"Amount {v} does not match quantity * unit_price")
        return v


class Invoice(BaseModel):
    invoice_id: str = Field(..., pattern=r"^[A-Z]{2}-\d{4}-\d{6}$")
    vendor_name: str = Field(..., min_length=2, max_length=200)
    vendor_type: VendorType
    invoice_date: date
    due_date: date
    subtotal: float = Field(..., ge=0)
    tax_amount: float = Field(..., ge=0)
    commission_rate: float = Field(..., ge=0, le=1)
    commission_amount: float = Field(..., ge=0)
    total_amount: float = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    line_items: List[LineItem] = Field(..., min_length=1)

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v, info):
        invoice_date = info.data.get("invoice_date")
        if invoice_date and v < invoice_date:
            raise ValueError("due_date must be >= invoice_date")
        return v
```

### 5.4 BigQuery Table Schema

```sql
-- Main invoices table
CREATE TABLE IF NOT EXISTS invoices.extracted_invoices (
    id STRING NOT NULL,
    invoice_id STRING NOT NULL,
    vendor_name STRING NOT NULL,
    vendor_type STRING NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    subtotal NUMERIC(15, 2) NOT NULL,
    tax_amount NUMERIC(15, 2) NOT NULL,
    commission_rate NUMERIC(5, 4) NOT NULL,
    commission_amount NUMERIC(15, 2) NOT NULL,
    total_amount NUMERIC(15, 2) NOT NULL,
    currency STRING NOT NULL,
    source_file STRING NOT NULL,
    extraction_model STRING NOT NULL,
    extraction_latency_ms INT64,
    confidence_score FLOAT64,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(invoice_date)
CLUSTER BY vendor_type, vendor_name;

-- Line items table
CREATE TABLE IF NOT EXISTS invoices.line_items (
    id STRING NOT NULL,
    invoice_id STRING NOT NULL,
    description STRING NOT NULL,
    quantity INT64 NOT NULL,
    unit_price NUMERIC(15, 2) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY invoice_id;

-- Extraction metrics table
CREATE TABLE IF NOT EXISTS invoices.extraction_metrics (
    id STRING NOT NULL,
    source_file STRING NOT NULL,
    extraction_model STRING NOT NULL,
    input_tokens INT64,
    output_tokens INT64,
    latency_ms INT64,
    confidence_score FLOAT64,
    validation_passed BOOL,
    error_message STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(created_at);
```

---

## 6. Success Metrics

### 6.1 Primary Metrics

| Metric | Target | Alert Threshold | Measurement Method |
|--------|--------|-----------------|-------------------|
| Extraction accuracy (overall) | >= 90% | < 85% | Ground truth comparison |
| Extraction accuracy (per field) | >= 90% | < 85% | Field-level validation |
| Processing latency P95 | < 30 seconds | > 45 seconds | Cloud Monitoring |
| Pipeline availability | > 99% | < 98% | Uptime monitoring |
| Cost per invoice | < $0.01 | > $0.02 | Cloud Billing |

### 6.2 LLM-Specific Metrics

| Metric | Target | Alert Threshold | Measurement Method |
|--------|--------|-----------------|-------------------|
| LLM latency P95 | < 3 seconds | > 5 seconds | Cloud Monitoring |
| Cost per extraction | < $0.005 | > $0.01 | Cloud Billing |
| Validation failure rate | < 5% | > 10% | Pydantic failures |
| Fallback trigger rate | < 5% | > 10% | OpenRouter usage |

### 6.3 Operational Metrics

| Metric | Target | Alert Threshold | Measurement Method |
|--------|--------|-----------------|-------------------|
| Time to detect issues | < 5 minutes | > 15 minutes | CrewAI metrics |
| Manual processing reduction | > 80% | < 70% | FTE hours tracking |
| DLQ message count | 0 | > 10 messages | Pub/Sub monitoring |
| Failed extraction rate | < 2% | > 5% | Pipeline metrics |

### 6.4 Dashboard Queries (BigQuery)

```sql
-- Daily extraction accuracy
SELECT
    DATE(created_at) as date,
    COUNT(*) as total_invoices,
    COUNTIF(confidence_score >= 0.90) as high_confidence,
    AVG(confidence_score) as avg_confidence,
    AVG(extraction_latency_ms) as avg_latency_ms
FROM invoices.extracted_invoices
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Validation failure rate
SELECT
    DATE(created_at) as date,
    COUNT(*) as total_attempts,
    COUNTIF(NOT validation_passed) as failures,
    COUNTIF(NOT validation_passed) / COUNT(*) * 100 as failure_rate
FROM invoices.extraction_metrics
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Cost analysis
SELECT
    DATE(created_at) as date,
    extraction_model,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    COUNT(*) as invoice_count,
    -- Gemini 2.0 Flash pricing (approximate)
    (SUM(input_tokens) * 0.000075 + SUM(output_tokens) * 0.0003) / COUNT(*) as cost_per_invoice
FROM invoices.extraction_metrics
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY DATE(created_at), extraction_model
ORDER BY date DESC;
```

---

## 7. Implementation Notes

### 7.1 Environment Configuration (Dev Only for MVP)

| Variable | Dev Value | Secret? | Notes |
|----------|-----------|---------|-------|
| `GOOGLE_CLOUD_PROJECT` | invoice-pipeline-dev | No | Single environment for MVP |
| `GCP_REGION` | us-central1 | No | Primary region |
| `GEMINI_MODEL` | gemini-2.5-flash | No | Updated to 2.5 Flash |
| `OPENROUTER_API_KEY` | (dev key) | Yes | Fallback LLM provider |

> **Note:** Production environment will be added post-MVP validation. Terraform modules should be designed for multi-environment support from the start.

### 7.2 Error Handling Strategy

```text
FUNCTION: tiff-to-png-converter
  - Retry: 3 attempts with exponential backoff
  - On failure: Move to DLQ, log error
  - Alert: If DLQ > 10 messages

FUNCTION: invoice-classifier
  - Retry: 3 attempts with exponential backoff
  - On low quality: Set vendor_type = "other", continue
  - On failure: Move to DLQ, log error

FUNCTION: data-extractor
  - Primary: Gemini 2.5 Flash (Vertex AI)
  - Fallback: OpenRouter (Claude 3.5 Sonnet)
  - On both fail: Copy to gs://invoices-failed, move to DLQ
  - Alert: If fallback rate > 5%

FUNCTION: bigquery-writer
  - Retry: 5 attempts with exponential backoff
  - On validation fail: Log to extraction_metrics, alert
  - On write fail: Move to DLQ, alert immediately
```

### 7.3 Adapter Pattern Interfaces

```python
# Storage adapter interface
class StorageAdapter(Protocol):
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> str: ...
    def delete(self, path: str) -> bool: ...
    def move(self, source: str, destination: str) -> str: ...

# Messaging adapter interface
class MessagingAdapter(Protocol):
    def publish(self, topic: str, message: dict, attributes: dict = None) -> str: ...
    def subscribe(self, subscription: str, callback: Callable) -> None: ...

# LLM adapter interface
class LLMAdapter(Protocol):
    def extract(self, image: bytes, prompt: str) -> dict: ...
    def get_usage(self) -> dict: ...
```

### 7.4 Deployment Commands (gcloud CLI)

```bash
# Deploy tiff-to-png-converter
gcloud run deploy tiff-to-png-converter \
    --source=./src/functions/tiff-to-png-converter \
    --region=us-central1 \
    --memory=512Mi \
    --timeout=60s \
    --min-instances=0 \
    --max-instances=10 \
    --service-account=tiff-converter-sa@${PROJECT_ID}.iam.gserviceaccount.com

# Deploy invoice-classifier
gcloud run deploy invoice-classifier \
    --source=./src/functions/invoice-classifier \
    --region=us-central1 \
    --memory=256Mi \
    --timeout=30s \
    --min-instances=0 \
    --max-instances=10 \
    --service-account=invoice-classifier-sa@${PROJECT_ID}.iam.gserviceaccount.com

# Deploy data-extractor
gcloud run deploy data-extractor \
    --source=./src/functions/data-extractor \
    --region=us-central1 \
    --memory=1Gi \
    --timeout=120s \
    --min-instances=0 \
    --max-instances=20 \
    --service-account=data-extractor-sa@${PROJECT_ID}.iam.gserviceaccount.com

# Deploy bigquery-writer
gcloud run deploy bigquery-writer \
    --source=./src/functions/bigquery-writer \
    --region=us-central1 \
    --memory=256Mi \
    --timeout=30s \
    --min-instances=0 \
    --max-instances=10 \
    --service-account=bigquery-writer-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

### 7.5 Service Account Permissions

| Service Account | Required Roles |
|-----------------|----------------|
| tiff-converter-sa | `roles/storage.objectViewer` (input), `roles/storage.objectCreator` (processed), `roles/pubsub.publisher` |
| invoice-classifier-sa | `roles/storage.objectViewer` (processed), `roles/storage.objectCreator` (archive), `roles/pubsub.publisher` |
| data-extractor-sa | `roles/storage.objectViewer` (processed), `roles/storage.objectCreator` (failed), `roles/pubsub.publisher`, `roles/aiplatform.user` |
| bigquery-writer-sa | `roles/bigquery.dataEditor`, `roles/pubsub.subscriber` |

### 7.6 Testing Checklist

```text
UNIT TESTS (per function):
  [ ] TIFF to PNG conversion (single page)
  [ ] TIFF to PNG conversion (multi-page)
  [ ] Invoice classification (each vendor type)
  [ ] Data extraction (mock Gemini response)
  [ ] Pydantic validation (valid data)
  [ ] Pydantic validation (invalid data)
  [ ] BigQuery write (mock client)

INTEGRATION TESTS:
  [ ] GCS upload triggers Pub/Sub
  [ ] Full pipeline: TIFF -> BigQuery
  [ ] Fallback to OpenRouter
  [ ] DLQ routing on failure
  [ ] Deduplication logic

LOAD TESTS:
  [ ] 100 concurrent invoices
  [ ] Large TIFF files (10+ pages)
  [ ] Sustained throughput (3,500/month rate)

ACCURACY TESTS:
  [ ] Ground truth comparison (50+ invoices)
  [ ] Per-field accuracy >= 90%
  [ ] Edge cases (handwritten, poor quality)
```

---

## Document Metadata

| Field | Value |
|-------|-------|
| **Version** | 1.2.0 |
| **Created** | January 29, 2026 |
| **Updated** | January 29, 2026 |
| **Source** | notes/summary-requirements.md |
| **Author** | Meeting Analyst Agent |
| **Review Status** | Ready for development |

### Change Log

| Version | Date       | Changes                                                                                                              |
|---------|------------|----------------------------------------------------------------------------------------------------------------------|
| 1.1.0   | 2026-01-29 | Updated LLM to Gemini 2.5 Flash; All 5 vendors supported from MVP; Dev-only environment |
| 1.2.0   | 2026-01-29 | Removed LangFuse/LLMOps from MVP scope; Use Cloud Logging for observability |
| 1.0.0   | 2026-01-29 | Initial version                                                                                                      |

---

## Quick Reference

```text
ENVIRONMENT: Dev only (invoice-pipeline-dev)
LLM MODEL:   Gemini 2.5 Flash (Vertex AI)
FALLBACK:    OpenRouter (Claude 3.5 Sonnet)

VENDORS (All supported from MVP):
  - ubereats  (~60%)
  - doordash  (~25%)
  - grubhub   (~10%)
  - other     (~5%)

BUCKETS:
  - INPUT:     gs://${PROJECT_ID}-invoices-input
  - PROCESSED: gs://${PROJECT_ID}-invoices-processed
  - ARCHIVE:   gs://${PROJECT_ID}-invoices-archive
  - FAILED:    gs://${PROJECT_ID}-invoices-failed

TOPICS:
  - invoice-uploaded    --> tiff-to-png-converter
  - invoice-converted   --> invoice-classifier
  - invoice-classified  --> data-extractor
  - invoice-extracted   --> bigquery-writer

FUNCTIONS:
  1. tiff-to-png-converter  (512MB, 60s)
  2. invoice-classifier     (256MB, 30s)
  3. data-extractor         (1GB, 120s)  [Gemini 2.5 Flash]
  4. bigquery-writer        (256MB, 30s)

ERROR HANDLING:
  Retry (3x) → Fallback (OpenRouter) → DLQ

TARGETS:
  - Accuracy: >= 90%
  - Latency P95: < 30s
  - Availability: > 99%
  - Cost/invoice: < $0.01

DEFERRED TO PHASE 2:
  - Production environment
  - CrewAI autonomous ops
```
