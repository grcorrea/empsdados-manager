# Cloud Run Functions Architecture Design v2

> **Source:** User Requirements + `design/design-plan-cloud-run-fncs.md` + `design/multi-cloud-architecture.md`
> **Purpose:** Revised architecture blueprint with configuration decoupling, GCS folder flow, and Adapter Pattern for future extensibility
> **Status:** Design Phase - v2
> **Version:** 2.0
> **Cloud Focus:** GCP (primary implementation)

---

## Executive Summary

| Aspect | Value |
|--------|-------|
| **Total Functions** | 4 modular Cloud Run functions |
| **Architecture Pattern** | Event-driven with Pub/Sub between functions |
| **Design Pattern** | Adapter Pattern (GCP primary, future multi-cloud extensibility) |
| **Configuration** | Fully decoupled via YAML files |
| **GCS Flow** | Landing -> Converted -> Classified -> Extracted -> Loaded |
| **Target LLM** | Gemini 2.5 Pro |
| **Functions Location** | `functions/gcp/` |
| **GCP Project (Dev)** | `eda-gemini-dev` |
| **GCP Project (Prod)** | `eda-gemini-prd` |

### Cloud Run Function Naming Convention

**Format:** `fnc-{function-name}-{env}`

| Function | Dev Name | Prod Name |
|----------|----------|-----------|
| tiff-to-png-converter | `fnc-tiff-to-png-converter-dev` | `fnc-tiff-to-png-converter-prd` |
| invoice-classifier | `fnc-invoice-classifier-dev` | `fnc-invoice-classifier-prd` |
| data-extractor | `fnc-data-extractor-dev` | `fnc-data-extractor-prd` |
| bigquery-writer | `fnc-bigquery-writer-dev` | `fnc-bigquery-writer-prd` |

### Resource Naming Summary

| Resource Type | Dev Environment | Prod Environment |
|---------------|-----------------|------------------|
| GCP Project | `eda-gemini-dev` | `eda-gemini-prd` |
| GCS Bucket | `eda-gemini-dev-pipeline` | `eda-gemini-prd-pipeline` |
| BigQuery Dataset | `ds_bq_gemini_dev` | `ds_bq_gemini_prd` |
| Pub/Sub Topics | `eda-gemini-dev-{topic}` | `eda-gemini-prd-{topic}` |
| Secrets | `eda-gemini-dev-{secret}` | `eda-gemini-prd-{secret}` |

### v1 Scope Exclusions (Per User Requirements)

| Feature | Status | Notes |
|---------|--------|-------|
| Dead Letter Queue (DLQ) | **EXCLUDED** | Deferred to v2 |
| LangFuse Integration | **EXCLUDED** | Deferred to v2 |
| Scaling Profiles | **EXCLUDED** | Deferred to v2 |

---

## Table of Contents

1. [YAML Configuration Schema](#1-yaml-configuration-schema)
2. [GCS Folder Flow Design](#2-gcs-folder-flow-design)
3. [The 4 Cloud Run Functions](#3-the-4-cloud-run-functions)
4. [Adapter Pattern Architecture](#4-adapter-pattern-architecture)
5. [Project Folder Structure](#5-project-folder-structure)
6. [Pub/Sub Topics](#6-pubsub-topics)
7. [Data Flow Diagram](#7-data-flow-diagram)
8. [Implementation Tasks](#8-implementation-tasks)

---

## 1. YAML Configuration Schema

### 1.1 Configuration Philosophy

All code MUST be completely decoupled from configuration. Configuration is loaded from YAML files at runtime, enabling:

- Environment-specific deployments (dev, prod)
- No code changes for configuration updates
- Secrets referenced by key name (fetched from Secret Manager)
- Easy testing with mock configurations

### 1.2 Main Configuration File (Dev Environment)

**Location:** `functions/gcp/config/pipeline.yaml`

```yaml
# =============================================================================
# PIPELINE CONFIGURATION - DEVELOPMENT ENVIRONMENT
# =============================================================================
# This file contains all configuration for the invoice processing pipeline.
# DO NOT hardcode any of these values in the code.
# =============================================================================

# -----------------------------------------------------------------------------
# GCP Project Settings
# -----------------------------------------------------------------------------
gcp:
  project_id: "eda-gemini-dev"
  region: "us-central1"

# -----------------------------------------------------------------------------
# GCS Bucket Configuration
# -----------------------------------------------------------------------------
storage:
  bucket: "eda-gemini-dev-pipeline"
  folders:
    landing: "landing"           # Incoming TIFF files
    converted: "converted"       # PNG files after conversion
    classified: "classified"     # Files after classification
    extracted: "extracted"       # Files after LLM extraction
    loaded: "loaded"             # Files after BigQuery write (archive)
    failed: "failed"             # Failed processing (manual review)

# -----------------------------------------------------------------------------
# Pub/Sub Topics
# -----------------------------------------------------------------------------
pubsub:
  topics:
    invoice_uploaded: "eda-gemini-dev-invoice-uploaded"
    invoice_converted: "eda-gemini-dev-invoice-converted"
    invoice_classified: "eda-gemini-dev-invoice-classified"
    invoice_extracted: "eda-gemini-dev-invoice-extracted"

  # Raw output topic for debugging/auditing
  raw_output_topic: "eda-gemini-dev-raw-gemini-output"

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------
llm:
  provider: "gemini"
  model: "gemini-2.5-pro"
  temperature: 0.0
  max_tokens: 4096
  timeout_seconds: 30

# -----------------------------------------------------------------------------
# BigQuery Configuration
# -----------------------------------------------------------------------------
bigquery:
  dataset: "ds_bq_gemini_dev"
  tables:
    extractions: "extractions"
    line_items: "line_items"
    audit_log: "audit_log"

# -----------------------------------------------------------------------------
# Secrets (Reference names in Secret Manager)
# -----------------------------------------------------------------------------
secrets:
  # These are SECRET NAMES, not values. Values are fetched at runtime.
  gemini_api_key: "eda-gemini-dev-gemini-api-key"

# -----------------------------------------------------------------------------
# Cloud Run Function Names
# -----------------------------------------------------------------------------
functions:
  tiff_to_png_converter:
    name: "fnc-tiff-to-png-converter-dev"
    max_file_size_mb: 50
    output_format: "PNG"
    resize_threshold_mb: 4

  invoice_classifier:
    name: "fnc-invoice-classifier-dev"
    supported_vendors:
      - ubereats
      - doordash
      - grubhub
      - ifood
      - rappi
    confidence_threshold: 0.7

  data_extractor:
    name: "fnc-data-extractor-dev"
    retry_attempts: 3
    retry_delay_seconds: 2

  bigquery_writer:
    name: "fnc-bigquery-writer-dev"
    batch_size: 100
    enable_streaming: true
```

### 1.3 Main Configuration File (Prod Environment)

**Location:** `functions/gcp/config/pipeline-prd.yaml`

```yaml
# =============================================================================
# PIPELINE CONFIGURATION - PRODUCTION ENVIRONMENT
# =============================================================================

# -----------------------------------------------------------------------------
# GCP Project Settings
# -----------------------------------------------------------------------------
gcp:
  project_id: "eda-gemini-prd"
  region: "us-central1"

# -----------------------------------------------------------------------------
# GCS Bucket Configuration
# -----------------------------------------------------------------------------
storage:
  bucket: "eda-gemini-prd-pipeline"
  folders:
    landing: "landing"
    converted: "converted"
    classified: "classified"
    extracted: "extracted"
    loaded: "loaded"
    failed: "failed"

# -----------------------------------------------------------------------------
# Pub/Sub Topics
# -----------------------------------------------------------------------------
pubsub:
  topics:
    invoice_uploaded: "eda-gemini-prd-invoice-uploaded"
    invoice_converted: "eda-gemini-prd-invoice-converted"
    invoice_classified: "eda-gemini-prd-invoice-classified"
    invoice_extracted: "eda-gemini-prd-invoice-extracted"

  raw_output_topic: "eda-gemini-prd-raw-gemini-output"

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------
llm:
  provider: "gemini"
  model: "gemini-2.5-pro"
  temperature: 0.0
  max_tokens: 4096
  timeout_seconds: 30

# -----------------------------------------------------------------------------
# BigQuery Configuration
# -----------------------------------------------------------------------------
bigquery:
  dataset: "ds_bq_gemini_prd"
  tables:
    extractions: "extractions"
    line_items: "line_items"
    audit_log: "audit_log"

# -----------------------------------------------------------------------------
# Secrets (Reference names in Secret Manager)
# -----------------------------------------------------------------------------
secrets:
  gemini_api_key: "eda-gemini-prd-gemini-api-key"

# -----------------------------------------------------------------------------
# Cloud Run Function Names
# -----------------------------------------------------------------------------
functions:
  tiff_to_png_converter:
    name: "fnc-tiff-to-png-converter-prd"
    max_file_size_mb: 50
    output_format: "PNG"
    resize_threshold_mb: 4

  invoice_classifier:
    name: "fnc-invoice-classifier-prd"
    supported_vendors:
      - ubereats
      - doordash
      - grubhub
      - ifood
      - rappi
    confidence_threshold: 0.7

  data_extractor:
    name: "fnc-data-extractor-prd"
    retry_attempts: 3
    retry_delay_seconds: 2

  bigquery_writer:
    name: "fnc-bigquery-writer-prd"
    batch_size: 100
    enable_streaming: true
```

### 1.4 Vendor-Specific Prompt Configuration

**Location:** `functions/gcp/config/prompts/`

```yaml
# functions/gcp/config/prompts/prompts.yaml
# =============================================================================
# PROMPT CONFIGURATION
# =============================================================================

base_prompt: |
  Extract structured data from this invoice image.

  ## Output Schema (JSON)

  Return ONLY valid JSON matching this exact schema:

  {
    "invoice_id": "string",
    "order_id": "string",
    "vendor_type": "string",
    "restaurant_name": "string",
    "restaurant_address": "string",
    "order_date": "YYYY-MM-DD",
    "line_items": [
      {
        "description": "string",
        "quantity": integer,
        "unit_price": float,
        "amount": float
      }
    ],
    "subtotal": float,
    "delivery_fee": float,
    "service_fee": float,
    "tip_amount": float,
    "total_amount": float,
    "currency": "string"
  }

  ## Rules

  1. Use ISO 8601 dates (YYYY-MM-DD)
  2. Use decimal numbers without currency symbols
  3. Use null for missing optional fields
  4. Return pure JSON - NO markdown formatting

vendor_prompts:
  ubereats: |
    ## UberEats Invoice Hints
    - Invoice ID format: INV-UE-XXXXXX
    - Look for UberEats logo at the top
    - Currency: USD
    Set vendor_type = "ubereats"

  doordash: |
    ## DoorDash Invoice Hints
    - Invoice ID format: INV-DD-XXXXXX
    - Look for DoorDash red logo
    - Currency: USD
    Set vendor_type = "doordash"

  grubhub: |
    ## Grubhub Invoice Hints
    - Invoice ID format: INV-GH-XXXXXX
    - Look for Grubhub orange logo
    - Currency: USD
    Set vendor_type = "grubhub"

  ifood: |
    ## iFood Invoice Hints
    - Invoice ID format: INV-IF-XXXXXX
    - Look for iFood red logo
    - Currency: BRL (Brazilian Real)
    - Portuguese terms: Pedido=Order, Entrega=Delivery
    Set vendor_type = "ifood"

  rappi: |
    ## Rappi Invoice Hints
    - Invoice ID format: INV-RP-XXXXXX
    - Look for Rappi orange logo
    - Currency: May be USD, MXN, COP, BRL
    - Spanish terms: Pedido=Order, Envio=Delivery
    Set vendor_type = "rappi"
```

### 1.5 Configuration Loading Pattern

```python
# All functions MUST load config at startup, never hardcode values

from pathlib import Path
import yaml

def load_config() -> dict:
    """Load pipeline configuration from YAML."""
    config_path = Path(__file__).parent.parent / "config" / "pipeline.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

# Usage in any function:
config = load_config()
bucket = config["storage"]["bucket"]
landing_folder = config["storage"]["folders"]["landing"]
```

---

## 2. GCS Folder Flow Design

### 2.1 Folder Flow Philosophy

Each function MUST store files on GCS between folders so the flow of process is **visible and traceable**. This enables:

- Visual pipeline monitoring via GCS console
- Easy debugging (check which folder a file reached)
- Replay capability (re-process from any folder)
- Audit trail for compliance

### 2.2 GCS Folder Structure

```
gs://eda-gemini-dev-pipeline/
│
├── landing/                    # STEP 1: Raw TIFF files arrive here
│   └── {invoice_id}.tiff       # e.g., INV-UE-308774_20260121.tiff
│
├── converted/                  # STEP 2: After TIFF -> PNG conversion
│   └── {invoice_id}.png        # e.g., INV-UE-308774_20260121.png
│
├── classified/                 # STEP 3: After vendor classification
│   └── {vendor}/{invoice_id}.png
│   └── ubereats/INV-UE-308774_20260121.png
│   └── doordash/INV-DD-47C462_20251227.png
│
├── extracted/                  # STEP 4: After LLM extraction (JSON stored)
│   └── {vendor}/{invoice_id}.json
│   └── ubereats/INV-UE-308774_20260121.json
│
├── loaded/                     # STEP 5: After BigQuery write (archive)
│   └── {year}/{month}/{vendor}/{invoice_id}.json
│   └── 2026/01/ubereats/INV-UE-308774_20260121.json
│
└── failed/                     # ERROR: Files that failed processing
    └── {step}/{invoice_id}.{ext}
    └── converter/INV-XX-BROKEN_20260101.tiff
    └── classifier/INV-XX-UNKNOWN_20260101.png
    └── extractor/INV-UE-FAILED_20260101.png
```

### 2.3 GCS Folder Flow Diagram

```
                              GCS FOLDER FLOW
                    Bucket: eda-gemini-{env}-pipeline
═══════════════════════════════════════════════════════════════════════════════

     STEP 1              STEP 2              STEP 3              STEP 4
    LANDING            CONVERTED           CLASSIFIED          EXTRACTED
    ───────            ─────────           ──────────          ─────────
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐
  │ landing/│        │converted│        │classified│       │extracted│
  │         │        │         │        │         │        │         │
  │  .tiff  │───────▶│  .png   │───────▶│  .png   │───────▶│  .json  │
  │         │        │         │        │(by vendor)│       │(by vendor)│
  └─────────┘        └─────────┘        └─────────┘        └─────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐
  │ Pub/Sub │        │ Pub/Sub │        │ Pub/Sub │        │ Pub/Sub │
  │uploaded │        │converted│        │classified│       │extracted│
  └─────────┘        └─────────┘        └─────────┘        └─────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
  │fnc-tiff-to- │   │fnc-invoice- │   │fnc-data-    │   │fnc-bigquery-│
  │png-converter│   │classifier   │   │extractor    │   │writer       │
  │-{env}       │   │-{env}       │   │-{env}       │   │-{env}       │
  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
                                                               │
                                                               ▼
                                                          STEP 5
                                                          LOADED
                                                          ──────
                                                               │
                                                               ▼
                                                        ┌─────────┐
                                                        │ loaded/ │
                                                        │         │
                                                        │  .json  │
                                                        │(archived)│
                                                        └─────────┘
                                                               │
                                                               ▼
                                                        ┌─────────┐
                                                        │BigQuery │
                                                        │ds_bq_   │
                                                        │gemini_  │
                                                        │{env}    │
                                                        └─────────┘

  ERROR HANDLING (any step)
  ─────────────────────────

  On failure at any step:
  ┌─────────┐
  │ failed/ │
  │{step}/  │ ← File moved here with error metadata
  │{file}   │
  └─────────┘

═══════════════════════════════════════════════════════════════════════════════
```

### 2.4 File Movement Rules

| Function | Source Folder | Destination Folder | File Transform |
|----------|---------------|-------------------|----------------|
| `fnc-tiff-to-png-converter-{env}` | `landing/` | `converted/` | `.tiff` -> `.png` |
| `fnc-invoice-classifier-{env}` | `converted/` | `classified/{vendor}/` | Move to vendor subfolder |
| `fnc-data-extractor-{env}` | `classified/{vendor}/` | `extracted/{vendor}/` | `.png` -> `.json` (extraction result) |
| `fnc-bigquery-writer-{env}` | `extracted/{vendor}/` | `loaded/{year}/{month}/{vendor}/` | Archive after write |

### 2.5 Error Handling Folder Structure

```
failed/
├── converter/          # TIFF conversion failures
│   └── {filename}.tiff
│   └── {filename}.error.json   # Error details
│
├── classifier/         # Classification failures
│   └── {filename}.png
│   └── {filename}.error.json
│
├── extractor/          # LLM extraction failures
│   └── {filename}.png
│   └── {filename}.error.json
│
└── writer/             # BigQuery write failures
    └── {filename}.json
    └── {filename}.error.json
```

---

## 3. The 4 Cloud Run Functions

### Function 1: `fnc-tiff-to-png-converter-{env}`

| Attribute | Description |
|-----------|-------------|
| **Dev Name** | `fnc-tiff-to-png-converter-dev` |
| **Prod Name** | `fnc-tiff-to-png-converter-prd` |
| **Purpose** | Convert multi-page TIFF files to individual PNG images |
| **Trigger** | `eda-gemini-{env}-invoice-uploaded` Pub/Sub topic |
| **Input** | `gs://eda-gemini-{env}-pipeline/landing/{filename}.tiff` |
| **Output** | `gs://eda-gemini-{env}-pipeline/converted/{filename}.png` |
| **Publishes To** | `eda-gemini-{env}-invoice-converted` Pub/Sub topic |
| **On Failure** | Move to `gs://eda-gemini-{env}-pipeline/failed/converter/` |

**Message Schema (Published):**

```json
{
  "invoice_id": "INV-UE-308774",
  "source_file": "landing/INV-UE-308774_20260121.tiff",
  "converted_file": "converted/INV-UE-308774_20260121.png",
  "timestamp": "2026-01-26T10:30:00Z",
  "metadata": {
    "original_size_bytes": 1234567,
    "converted_size_bytes": 456789,
    "pages_extracted": 1
  }
}
```

---

### Function 2: `fnc-invoice-classifier-{env}`

| Attribute | Description |
|-----------|-------------|
| **Dev Name** | `fnc-invoice-classifier-dev` |
| **Prod Name** | `fnc-invoice-classifier-prd` |
| **Purpose** | Validate image quality and classify invoice vendor type |
| **Trigger** | `eda-gemini-{env}-invoice-converted` Pub/Sub topic |
| **Input** | `gs://eda-gemini-{env}-pipeline/converted/{filename}.png` |
| **Output** | `gs://eda-gemini-{env}-pipeline/classified/{vendor}/{filename}.png` |
| **Publishes To** | `eda-gemini-{env}-invoice-classified` Pub/Sub topic |
| **On Failure** | Move to `gs://eda-gemini-{env}-pipeline/failed/classifier/` |

**Message Schema (Published):**

```json
{
  "invoice_id": "INV-UE-308774",
  "source_file": "converted/INV-UE-308774_20260121.png",
  "classified_file": "classified/ubereats/INV-UE-308774_20260121.png",
  "vendor_type": "ubereats",
  "confidence": 0.95,
  "timestamp": "2026-01-26T10:30:05Z"
}
```

---

### Function 3: `fnc-data-extractor-{env}`

| Attribute | Description |
|-----------|-------------|
| **Dev Name** | `fnc-data-extractor-dev` |
| **Prod Name** | `fnc-data-extractor-prd` |
| **Purpose** | Extract structured data using Gemini LLM |
| **Trigger** | `eda-gemini-{env}-invoice-classified` Pub/Sub topic |
| **Input** | `gs://eda-gemini-{env}-pipeline/classified/{vendor}/{filename}.png` |
| **Output** | `gs://eda-gemini-{env}-pipeline/extracted/{vendor}/{filename}.json` |
| **Publishes To** | `eda-gemini-{env}-invoice-extracted` Pub/Sub topic |
| **LLM** | Gemini 2.5 Pro |
| **On Failure** | Move to `gs://eda-gemini-{env}-pipeline/failed/extractor/` |

**Message Schema (Published):**

```json
{
  "invoice_id": "INV-UE-308774",
  "source_file": "classified/ubereats/INV-UE-308774_20260121.png",
  "extracted_file": "extracted/ubereats/INV-UE-308774_20260121.json",
  "vendor_type": "ubereats",
  "extraction_result": {
    "invoice_id": "INV-UE-308774",
    "total_amount": 45.67,
    "currency": "USD"
  },
  "metadata": {
    "model": "gemini-2.5-pro",
    "latency_ms": 1234,
    "tokens_used": 567
  },
  "timestamp": "2026-01-26T10:30:10Z"
}
```

---

### Function 4: `fnc-bigquery-writer-{env}`

| Attribute | Description |
|-----------|-------------|
| **Dev Name** | `fnc-bigquery-writer-dev` |
| **Prod Name** | `fnc-bigquery-writer-prd` |
| **Purpose** | Write extracted JSON to BigQuery and archive file |
| **Trigger** | `eda-gemini-{env}-invoice-extracted` Pub/Sub topic |
| **Input** | `gs://eda-gemini-{env}-pipeline/extracted/{vendor}/{filename}.json` |
| **Output** | BigQuery row + `gs://eda-gemini-{env}-pipeline/loaded/{year}/{month}/{vendor}/{filename}.json` |
| **On Failure** | Move to `gs://eda-gemini-{env}-pipeline/failed/writer/` |

**BigQuery Table Schema:**

```sql
-- Dataset: ds_bq_gemini_dev (dev) or ds_bq_gemini_prd (prod)
CREATE TABLE ds_bq_gemini_dev.extractions (
  extraction_id STRING NOT NULL,
  invoice_id STRING NOT NULL,
  vendor_type STRING NOT NULL,
  restaurant_name STRING,
  order_date DATE,
  subtotal FLOAT64,
  delivery_fee FLOAT64,
  service_fee FLOAT64,
  tip_amount FLOAT64,
  total_amount FLOAT64,
  currency STRING,
  source_file STRING,
  processed_at TIMESTAMP,
  metadata JSON
);
```

---

## 4. Adapter Pattern Architecture

### 4.1 Design Philosophy

The Adapter Pattern provides **future extensibility** for multi-cloud deployment while keeping **GCP as the primary implementation** for this project. All cloud-specific services are abstracted behind interfaces (ports), enabling:

- **GCP Primary:** Full implementation and production-ready
- **Future Multi-cloud:** AWS and Azure adapters can be added later
- Easy testing with mock adapters
- Clean separation of business logic from infrastructure

**Note:** For this project, GCP is the sole target platform. The Adapter Pattern is included for architectural best practices and future extensibility, not immediate multi-cloud deployment.

### 4.2 Port Interfaces (Abstract Base Classes)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ADAPTER PATTERN ARCHITECTURE                         │
│                        (GCP Primary Implementation)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BUSINESS LOGIC LAYER (Cloud-Agnostic)                                      │
│  ─────────────────────────────────────                                      │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Core Services (Pure Python)                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ Converter   │  │ Classifier  │  │ Extractor   │  │ Writer      │  │  │
│  │  │ Service     │  │ Service     │  │ Service     │  │ Service     │  │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │  │
│  │         │                │                │                │          │  │
│  └─────────┼────────────────┼────────────────┼────────────────┼──────────┘  │
│            │                │                │                │             │
│  PORT LAYER (Abstractions / Interfaces)                                     │
│  ──────────────────────────────────────                                     │
│            │                │                │                │             │
│  ┌─────────▼────────────────▼────────────────▼────────────────▼──────────┐  │
│  │                     Port Interfaces (ABC)                              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ StoragePort │  │ MessagingPort│ │ LLMPort     │  │ WarehousePort│ │  │
│  │  │ (ABC)       │  │ (ABC)       │  │ (ABC)       │  │ (ABC)       │  │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │  │
│  │         │                │                │                │          │  │
│  └─────────┼────────────────┼────────────────┼────────────────┼──────────┘  │
│            │                │                │                │             │
│  ADAPTER LAYER (Cloud-Specific Implementations)                             │
│  ──────────────────────────────────────────────                             │
│            │                │                │                │             │
│  ┌─────────▼────────────────▼────────────────▼────────────────▼──────────┐  │
│  │  GCP ADAPTERS (PRIMARY - v1)                                         │  │
│  │  Project: eda-gemini-dev / eda-gemini-prd                            │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ GCSAdapter  │  │PubSubAdapter│  │GeminiAdapter│  │BigQueryAdapter│ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  AWS ADAPTERS (Future Extensibility - Not Implemented)                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ S3Adapter   │  │ SQSAdapter  │  │BedrockAdapter│ │RedshiftAdapter│ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  AZURE ADAPTERS (Future Extensibility - Not Implemented)              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ BlobAdapter │  │ServiceBusAdapter│ │AzureOpenAIAdapter│ │SynapseAdapter│ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Port Interface Definitions (Python ABC)

**Location:** `functions/gcp/src/ports/`

#### StoragePort

```python
# functions/gcp/src/ports/storage.py
"""Storage Port - Abstract interface for object storage operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO, Optional


@dataclass
class StorageObject:
    """Represents an object in cloud storage."""
    bucket: str
    key: str
    content_type: str
    size: int
    metadata: dict


class StoragePort(ABC):
    """Abstract interface for cloud storage operations.

    Implementations:
    - GCP: GCSAdapter (google-cloud-storage) [PRIMARY]
    - AWS: S3Adapter (boto3) [Future]
    - Azure: BlobAdapter (azure-storage-blob) [Future]
    """

    @abstractmethod
    def download(self, bucket: str, key: str) -> bytes:
        """Download object content as bytes."""
        pass

    @abstractmethod
    def upload(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[dict] = None
    ) -> StorageObject:
        """Upload data to storage."""
        pass

    @abstractmethod
    def move(self, bucket: str, source_key: str, dest_key: str) -> StorageObject:
        """Move object within bucket (copy + delete)."""
        pass

    @abstractmethod
    def delete(self, bucket: str, key: str) -> None:
        """Delete object from storage."""
        pass

    @abstractmethod
    def exists(self, bucket: str, key: str) -> bool:
        """Check if object exists."""
        pass

    @abstractmethod
    def list_objects(self, bucket: str, prefix: str) -> list[StorageObject]:
        """List objects with given prefix."""
        pass
```

#### MessagingPort

```python
# functions/gcp/src/ports/messaging.py
"""Messaging Port - Abstract interface for pub/sub operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Message:
    """Represents a message in the messaging system."""
    id: str
    body: dict
    attributes: dict
    timestamp: str
    ack_id: Optional[str] = None


class MessagingPort(ABC):
    """Abstract interface for messaging operations.

    Implementations:
    - GCP: PubSubAdapter (google-cloud-pubsub) [PRIMARY]
    - AWS: SQSAdapter (boto3) [Future]
    - Azure: ServiceBusAdapter (azure-servicebus) [Future]
    """

    @abstractmethod
    def publish(
        self,
        topic: str,
        message: dict,
        attributes: Optional[dict] = None
    ) -> str:
        """Publish message to topic. Returns message ID."""
        pass

    @abstractmethod
    def ack(self, message: Message) -> None:
        """Acknowledge message processing success."""
        pass

    @abstractmethod
    def nack(self, message: Message) -> None:
        """Negative acknowledge - message will be redelivered."""
        pass
```

#### LLMPort

```python
# functions/gcp/src/ports/llm.py
"""LLM Port - Abstract interface for Large Language Model operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Represents a response from an LLM."""
    content: str
    model: str
    usage: dict  # tokens, cost
    latency_ms: float
    raw_response: Optional[dict] = None


class LLMPort(ABC):
    """Abstract interface for LLM operations.

    Implementations:
    - GCP: GeminiAdapter (google-generativeai / Vertex AI) [PRIMARY]
    - AWS: BedrockAdapter (boto3 bedrock-runtime) [Future]
    - Azure: AzureOpenAIAdapter (azure-openai) [Future]
    """

    @abstractmethod
    def extract_from_image(
        self,
        image_bytes: bytes,
        prompt: str,
        schema: Optional[dict] = None
    ) -> LLMResponse:
        """Extract structured data from an image using vision capabilities."""
        pass

    @abstractmethod
    def classify_image(
        self,
        image_bytes: bytes,
        categories: list[str]
    ) -> tuple[str, float]:
        """Classify image into one of the categories. Returns (category, confidence)."""
        pass
```

#### DataWarehousePort

```python
# functions/gcp/src/ports/warehouse.py
"""Data Warehouse Port - Abstract interface for analytical database operations."""

from abc import ABC, abstractmethod
from typing import Optional


class DataWarehousePort(ABC):
    """Abstract interface for data warehouse operations.

    Implementations:
    - GCP: BigQueryAdapter (google-cloud-bigquery) [PRIMARY]
    - AWS: RedshiftAdapter (boto3) or AthenaAdapter [Future]
    - Azure: SynapseAdapter (azure-synapse) [Future]
    """

    @abstractmethod
    def insert_row(self, dataset: str, table: str, row: dict) -> str:
        """Insert single row. Returns row ID."""
        pass

    @abstractmethod
    def insert_rows(self, dataset: str, table: str, rows: list[dict]) -> int:
        """Insert multiple rows. Returns count of inserted rows."""
        pass

    @abstractmethod
    def query(self, sql: str, params: Optional[dict] = None) -> list[dict]:
        """Execute query and return results."""
        pass

    @abstractmethod
    def table_exists(self, dataset: str, table: str) -> bool:
        """Check if table exists."""
        pass
```

### 4.4 GCP Adapter Implementations

**Location:** `functions/gcp/src/adapters/gcp/`

```python
# functions/gcp/src/adapters/gcp/storage.py
"""GCS Adapter - Google Cloud Storage implementation of StoragePort."""

from google.cloud import storage as gcs

from src.ports.storage import StoragePort, StorageObject


class GCSAdapter(StoragePort):
    """Google Cloud Storage adapter.

    Primary implementation for eda-gemini-dev and eda-gemini-prd projects.
    """

    def __init__(self, project_id: str):
        """Initialize GCS adapter.

        Args:
            project_id: GCP project ID (e.g., 'eda-gemini-dev' or 'eda-gemini-prd')
        """
        self._client = gcs.Client(project=project_id)

    def download(self, bucket: str, key: str) -> bytes:
        bucket_obj = self._client.bucket(bucket)
        blob = bucket_obj.blob(key)
        return blob.download_as_bytes()

    def upload(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: dict | None = None
    ) -> StorageObject:
        bucket_obj = self._client.bucket(bucket)
        blob = bucket_obj.blob(key)
        blob.metadata = metadata
        blob.upload_from_string(data, content_type=content_type)
        return StorageObject(
            bucket=bucket,
            key=key,
            content_type=content_type,
            size=len(data),
            metadata=metadata or {}
        )

    def move(self, bucket: str, source_key: str, dest_key: str) -> StorageObject:
        bucket_obj = self._client.bucket(bucket)
        source_blob = bucket_obj.blob(source_key)
        dest_blob = bucket_obj.copy_blob(source_blob, bucket_obj, dest_key)
        source_blob.delete()
        return StorageObject(
            bucket=bucket,
            key=dest_key,
            content_type=dest_blob.content_type or "",
            size=dest_blob.size or 0,
            metadata=dest_blob.metadata or {}
        )

    def delete(self, bucket: str, key: str) -> None:
        bucket_obj = self._client.bucket(bucket)
        blob = bucket_obj.blob(key)
        blob.delete()

    def exists(self, bucket: str, key: str) -> bool:
        bucket_obj = self._client.bucket(bucket)
        blob = bucket_obj.blob(key)
        return blob.exists()

    def list_objects(self, bucket: str, prefix: str) -> list[StorageObject]:
        bucket_obj = self._client.bucket(bucket)
        blobs = bucket_obj.list_blobs(prefix=prefix)
        return [
            StorageObject(
                bucket=bucket,
                key=blob.name,
                content_type=blob.content_type or "",
                size=blob.size or 0,
                metadata=blob.metadata or {}
            )
            for blob in blobs
        ]
```

### 4.5 Adapter Factory

```python
# functions/gcp/src/adapters/factory.py
"""Adapter Factory - Creates appropriate adapters based on cloud provider.

Note: This project is GCP-focused. AWS and Azure adapters are placeholders
for future extensibility and are not implemented.
"""

from enum import Enum
from typing import TYPE_CHECKING

from src.ports.storage import StoragePort
from src.ports.messaging import MessagingPort
from src.ports.llm import LLMPort
from src.ports.warehouse import DataWarehousePort

if TYPE_CHECKING:
    from src.config.settings import PipelineConfig


class CloudProvider(str, Enum):
    """Supported cloud providers."""
    GCP = "gcp"  # Primary - fully implemented
    AWS = "aws"  # Future extensibility
    AZURE = "azure"  # Future extensibility


class AdapterFactory:
    """Factory for creating cloud-specific adapters.

    Currently supports GCP only. AWS and Azure are placeholders for future use.
    """

    def __init__(self, config: "PipelineConfig"):
        self._config = config
        self._provider = CloudProvider(config.get("cloud_provider", "gcp"))

    def create_storage(self) -> StoragePort:
        """Create storage adapter for configured cloud provider."""
        match self._provider:
            case CloudProvider.GCP:
                from src.adapters.gcp.storage import GCSAdapter
                return GCSAdapter(self._config["gcp"]["project_id"])
            case CloudProvider.AWS:
                raise NotImplementedError("AWS adapters not implemented - GCP is primary")
            case CloudProvider.AZURE:
                raise NotImplementedError("Azure adapters not implemented - GCP is primary")
            case _:
                raise ValueError(f"Unsupported provider: {self._provider}")

    def create_messaging(self) -> MessagingPort:
        """Create messaging adapter for configured cloud provider."""
        match self._provider:
            case CloudProvider.GCP:
                from src.adapters.gcp.messaging import PubSubAdapter
                return PubSubAdapter(self._config["gcp"]["project_id"])
            case CloudProvider.AWS:
                raise NotImplementedError("AWS adapters not implemented - GCP is primary")
            case CloudProvider.AZURE:
                raise NotImplementedError("Azure adapters not implemented - GCP is primary")
            case _:
                raise ValueError(f"Unsupported provider: {self._provider}")

    def create_llm(self) -> LLMPort:
        """Create LLM adapter for configured cloud provider."""
        match self._provider:
            case CloudProvider.GCP:
                from src.adapters.gcp.llm import GeminiAdapter
                return GeminiAdapter(
                    project_id=self._config["gcp"]["project_id"],
                    model=self._config["llm"]["model"]
                )
            case CloudProvider.AWS:
                raise NotImplementedError("AWS adapters not implemented - GCP is primary")
            case CloudProvider.AZURE:
                raise NotImplementedError("Azure adapters not implemented - GCP is primary")
            case _:
                raise ValueError(f"Unsupported provider: {self._provider}")

    def create_warehouse(self) -> DataWarehousePort:
        """Create data warehouse adapter for configured cloud provider."""
        match self._provider:
            case CloudProvider.GCP:
                from src.adapters.gcp.warehouse import BigQueryAdapter
                return BigQueryAdapter(self._config["gcp"]["project_id"])
            case CloudProvider.AWS:
                raise NotImplementedError("AWS adapters not implemented - GCP is primary")
            case CloudProvider.AZURE:
                raise NotImplementedError("Azure adapters not implemented - GCP is primary")
            case _:
                raise ValueError(f"Unsupported provider: {self._provider}")
```

---

## 5. Project Folder Structure

### 5.1 Complete Directory Layout

```
functions/
└── gcp/                                    # GCP-specific functions
    │
    ├── config/                             # Configuration (YAML files)
    │   ├── pipeline.yaml                   # Dev environment configuration
    │   ├── pipeline-prd.yaml               # Prod environment configuration
    │   ├── prompts/
    │   │   └── prompts.yaml                # LLM prompt templates
    │   └── schemas/
    │       ├── invoice.json                # JSON schema for validation
    │       └── pubsub_messages.json        # Pub/Sub message schemas
    │
    ├── src/                                # Source code
    │   │
    │   ├── core/                           # Business logic (cloud-agnostic)
    │   │   ├── __init__.py
    │   │   ├── models/
    │   │   │   ├── __init__.py
    │   │   │   ├── invoice.py              # Pydantic models for invoice
    │   │   │   └── events.py               # Pub/Sub message models
    │   │   ├── services/
    │   │   │   ├── __init__.py
    │   │   │   ├── converter.py            # TIFF to PNG conversion logic
    │   │   │   ├── classifier.py           # Invoice classification logic
    │   │   │   ├── extractor.py            # LLM extraction logic
    │   │   │   └── writer.py               # BigQuery write logic
    │   │   └── exceptions.py               # Custom exceptions
    │   │
    │   ├── ports/                          # Abstract interfaces (Hexagonal)
    │   │   ├── __init__.py
    │   │   ├── storage.py                  # StoragePort ABC
    │   │   ├── messaging.py                # MessagingPort ABC
    │   │   ├── llm.py                      # LLMPort ABC
    │   │   └── warehouse.py                # DataWarehousePort ABC
    │   │
    │   ├── adapters/                       # Cloud-specific implementations
    │   │   ├── __init__.py
    │   │   ├── factory.py                  # AdapterFactory
    │   │   └── gcp/                        # GCP adapters (PRIMARY)
    │   │       ├── __init__.py
    │   │       ├── storage.py              # GCSAdapter
    │   │       ├── messaging.py            # PubSubAdapter
    │   │       ├── llm.py                  # GeminiAdapter
    │   │       └── warehouse.py            # BigQueryAdapter
    │   │
    │   ├── handlers/                       # Cloud Run entry points
    │   │   ├── __init__.py
    │   │   ├── converter_handler.py        # fnc-tiff-to-png-converter entry
    │   │   ├── classifier_handler.py       # fnc-invoice-classifier entry
    │   │   ├── extractor_handler.py        # fnc-data-extractor entry
    │   │   └── writer_handler.py           # fnc-bigquery-writer entry
    │   │
    │   └── utils/                          # Shared utilities
    │       ├── __init__.py
    │       ├── config.py                   # Configuration loader
    │       ├── logging.py                  # Structured logging
    │       └── validation.py               # Schema validation helpers
    │
    ├── tests/                              # Test suite
    │   ├── __init__.py
    │   ├── unit/
    │   │   ├── test_converter.py
    │   │   ├── test_classifier.py
    │   │   ├── test_extractor.py
    │   │   └── test_writer.py
    │   ├── integration/
    │   │   └── test_gcp_adapters.py
    │   └── fixtures/
    │       └── sample_invoices/
    │
    ├── Dockerfile                          # Container definition
    ├── requirements.txt                    # Python dependencies
    ├── pyproject.toml                      # Project metadata
    └── README.md                           # Function documentation
```

### 5.2 File Responsibilities

| File/Folder | Responsibility |
|-------------|----------------|
| `config/pipeline.yaml` | Dev environment runtime configuration |
| `config/pipeline-prd.yaml` | Prod environment runtime configuration |
| `config/prompts/` | LLM prompt templates |
| `src/core/` | Pure business logic, no cloud imports |
| `src/ports/` | Abstract interfaces (contracts) |
| `src/adapters/gcp/` | GCP-specific implementations (primary) |
| `src/handlers/` | HTTP entry points for Cloud Run |
| `tests/` | Unit and integration tests |

---

## 6. Pub/Sub Topics

### 6.1 Topic Configuration

**Topic Naming Pattern:** `{project-id}-{topic-name}`

| Topic Name (Dev) | Topic Name (Prod) | Publisher | Subscriber | Purpose |
|------------------|-------------------|-----------|------------|---------|
| `eda-gemini-dev-invoice-uploaded` | `eda-gemini-prd-invoice-uploaded` | GCS Eventarc | fnc-tiff-to-png-converter | New TIFF file notification |
| `eda-gemini-dev-invoice-converted` | `eda-gemini-prd-invoice-converted` | fnc-tiff-to-png-converter | fnc-invoice-classifier | PNG ready for classification |
| `eda-gemini-dev-invoice-classified` | `eda-gemini-prd-invoice-classified` | fnc-invoice-classifier | fnc-data-extractor | Ready for LLM extraction |
| `eda-gemini-dev-invoice-extracted` | `eda-gemini-prd-invoice-extracted` | fnc-data-extractor | fnc-bigquery-writer | Ready for storage |
| `eda-gemini-dev-raw-gemini-output` | `eda-gemini-prd-raw-gemini-output` | fnc-data-extractor | (audit/debug) | Raw LLM output for debugging |

### 6.2 Message Schemas

```json
// invoice-uploaded message
{
  "type": "object",
  "properties": {
    "event_type": { "const": "invoice.uploaded" },
    "invoice_id": { "type": "string" },
    "bucket": { "type": "string" },
    "file_path": { "type": "string" },
    "file_size_bytes": { "type": "integer" },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "required": ["event_type", "invoice_id", "bucket", "file_path", "timestamp"]
}

// invoice-converted message
{
  "type": "object",
  "properties": {
    "event_type": { "const": "invoice.converted" },
    "invoice_id": { "type": "string" },
    "source_file": { "type": "string" },
    "converted_file": { "type": "string" },
    "conversion_metadata": {
      "type": "object",
      "properties": {
        "original_size_bytes": { "type": "integer" },
        "converted_size_bytes": { "type": "integer" },
        "pages_extracted": { "type": "integer" }
      }
    },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "required": ["event_type", "invoice_id", "source_file", "converted_file", "timestamp"]
}

// invoice-classified message
{
  "type": "object",
  "properties": {
    "event_type": { "const": "invoice.classified" },
    "invoice_id": { "type": "string" },
    "source_file": { "type": "string" },
    "classified_file": { "type": "string" },
    "vendor_type": { "type": "string", "enum": ["ubereats", "doordash", "grubhub", "ifood", "rappi", "unknown"] },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "required": ["event_type", "invoice_id", "vendor_type", "classified_file", "timestamp"]
}

// invoice-extracted message
{
  "type": "object",
  "properties": {
    "event_type": { "const": "invoice.extracted" },
    "invoice_id": { "type": "string" },
    "vendor_type": { "type": "string" },
    "source_file": { "type": "string" },
    "extracted_file": { "type": "string" },
    "extraction_result": { "type": "object" },
    "llm_metadata": {
      "type": "object",
      "properties": {
        "model": { "type": "string" },
        "latency_ms": { "type": "number" },
        "tokens_used": { "type": "integer" }
      }
    },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "required": ["event_type", "invoice_id", "vendor_type", "extracted_file", "timestamp"]
}
```

---

## 7. Data Flow Diagram

### 7.1 Complete Pipeline Flow

```
══════════════════════════════════════════════════════════════════════════════════
                    INVOICE PROCESSING PIPELINE - COMPLETE DATA FLOW
                    GCP Project: eda-gemini-dev / eda-gemini-prd
══════════════════════════════════════════════════════════════════════════════════

                                    ┌─────────────────┐
                                    │   CONFIG YAML   │
                                    │  pipeline.yaml  │
                                    │  prompts.yaml   │
                                    └────────┬────────┘
                                             │ loads
                 ┌───────────────────────────┼───────────────────────────┐
                 │                           │                           │
                 ▼                           ▼                           ▼

     ┌───────────────────────────────────────────────────────────────────────────┐
     │  STEP 1: UPLOAD                                                           │
     │  ─────────────────                                                        │
     │                                                                           │
     │  External System ──────▶ GCS: eda-gemini-{env}-pipeline/landing/{inv}.tiff│
     │                                      │                                    │
     │                                      ▼                                    │
     │                               Eventarc Trigger                            │
     │                                      │                                    │
     │                                      ▼                                    │
     │                   Pub/Sub: eda-gemini-{env}-invoice-uploaded              │
     └───────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
     ┌───────────────────────────────────────────────────────────────────────────┐
     │  STEP 2: CONVERT (fnc-tiff-to-png-converter-{env})                        │
     │  ─────────────────────────────────────────────────                        │
     │                                                                           │
     │  ┌─────────────┐                                                          │
     │  │  Receives   │                                                          │
     │  │  Pub/Sub    │                                                          │
     │  │  Message    │                                                          │
     │  └──────┬──────┘                                                          │
     │         │                                                                 │
     │         ▼                                                                 │
     │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
     │  │ Download    │───▶│ Convert     │───▶│ Upload      │                   │
     │  │ from GCS    │    │ TIFF→PNG    │    │ to GCS      │                   │
     │  │ landing/    │    │ (Pillow)    │    │ converted/  │                   │
     │  └─────────────┘    └─────────────┘    └─────────────┘                   │
     │                                               │                           │
     │                                               ▼                           │
     │                      Pub/Sub: eda-gemini-{env}-invoice-converted          │
     │                                                                           │
     │  On Error: Move to failed/converter/                                      │
     └───────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
     ┌───────────────────────────────────────────────────────────────────────────┐
     │  STEP 3: CLASSIFY (fnc-invoice-classifier-{env})                          │
     │  ────────────────────────────────────────────────                         │
     │                                                                           │
     │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
     │  │ Download    │───▶│ Classify    │───▶│ Move to     │                   │
     │  │ from GCS    │    │ Vendor Type │    │ GCS         │                   │
     │  │ converted/  │    │(rules/LLM)  │    │classified/  │                   │
     │  │             │    │             │    │ {vendor}/   │                   │
     │  └─────────────┘    └─────────────┘    └─────────────┘                   │
     │                                               │                           │
     │  Classification Methods:                      │                           │
     │  1. Filename parsing (INV-UE-, INV-DD-)       ▼                           │
     │  2. Logo detection (optional LLM)   Pub/Sub: eda-gemini-{env}-invoice-    │
     │  3. Text pattern matching                     classified                  │
     │                                                                           │
     │  On Error: Move to failed/classifier/                                     │
     └───────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
     ┌───────────────────────────────────────────────────────────────────────────┐
     │  STEP 4: EXTRACT (fnc-data-extractor-{env})                               │
     │  ──────────────────────────────────────────                               │
     │                                                                           │
     │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
     │  │ Download    │───▶│ Load Prompt │───▶│ Call Gemini │                   │
     │  │ from GCS    │    │ base.md +   │    │ 2.5 Pro     │                   │
     │  │classified/  │    │ {vendor}.md │    │ Vision API  │                   │
     │  │ {vendor}/   │    │             │    │             │                   │
     │  └─────────────┘    └─────────────┘    └──────┬──────┘                   │
     │                                               │                           │
     │                                               ▼                           │
     │                                        ┌─────────────┐                    │
     │                                        │ Validate    │                    │
     │                                        │ Response    │                    │
     │                                        │ (Pydantic)  │                    │
     │                                        └──────┬──────┘                    │
     │                                               │                           │
     │                                               ▼                           │
     │                                        ┌─────────────┐                    │
     │                                        │ Save JSON   │                    │
     │                                        │ to GCS      │                    │
     │                                        │ extracted/  │                    │
     │                                        │ {vendor}/   │                    │
     │                                        └──────┬──────┘                    │
     │                                               │                           │
     │                                               ▼                           │
     │                      Pub/Sub: eda-gemini-{env}-invoice-extracted          │
     │                                                                           │
     │  Also publishes to: eda-gemini-{env}-raw-gemini-output (for debugging)    │
     │  On Error: Move to failed/extractor/                                      │
     └───────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
     ┌───────────────────────────────────────────────────────────────────────────┐
     │  STEP 5: LOAD (fnc-bigquery-writer-{env})                                 │
     │  ────────────────────────────────────────                                 │
     │                                                                           │
     │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
     │  │ Download    │───▶│ Transform   │───▶│ Insert to   │                   │
     │  │ JSON from   │    │ to BQ       │    │ BigQuery    │                   │
     │  │ GCS         │    │ Schema      │    │ds_bq_gemini │                   │
     │  │ extracted/  │    │             │    │_{env}       │                   │
     │  └─────────────┘    └─────────────┘    └──────┬──────┘                   │
     │                                               │                           │
     │                                               ▼                           │
     │                                        ┌─────────────┐                    │
     │                                        │ Archive to  │                    │
     │                                        │ GCS loaded/ │                    │
     │                                        │{y}/{m}/{v}/ │                    │
     │                                        └─────────────┘                    │
     │                                                                           │
     │  On Error: Move to failed/writer/                                         │
     └───────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
                                      ┌─────────────┐
                                      │  BigQuery   │
                                      │ds_bq_gemini_│
                                      │{env}        │
                                      │.extractions │
                                      └─────────────┘

══════════════════════════════════════════════════════════════════════════════════
```

---

## 8. Implementation Tasks

### 8.1 Task Overview

| Phase | Focus | Duration |
|-------|-------|----------|
| Phase 1 | Foundation (Config, Ports, Core Models) | 2-3 days |
| Phase 2 | GCP Adapters | 2-3 days |
| Phase 3 | Function Handlers | 3-4 days |
| Phase 4 | Integration & Testing | 2-3 days |
| Phase 5 | Deployment | 1-2 days |

### 8.2 Ordered Task List

#### Phase 1: Foundation

| # | Task | Priority | Dependencies |
|---|------|----------|--------------|
| 1.1 | Create `functions/gcp/` folder structure | P0 | None |
| 1.2 | Create `config/pipeline.yaml` with dev configuration (eda-gemini-dev) | P0 | 1.1 |
| 1.2b | Create `config/pipeline-prd.yaml` with prod configuration (eda-gemini-prd) | P0 | 1.1 |
| 1.3 | Create `config/prompts/prompts.yaml` | P0 | 1.1 |
| 1.4 | Create `src/utils/config.py` - Configuration loader | P0 | 1.2 |
| 1.5 | Create `src/core/models/invoice.py` - Pydantic models | P0 | 1.1 |
| 1.6 | Create `src/core/models/events.py` - Pub/Sub message models | P0 | 1.1 |
| 1.7 | Create `src/core/exceptions.py` - Custom exceptions | P1 | 1.1 |
| 1.8 | Create `requirements.txt` with dependencies | P0 | 1.1 |

#### Phase 2: Port Interfaces & GCP Adapters

| # | Task | Priority | Dependencies |
|---|------|----------|--------------|
| 2.1 | Create `src/ports/storage.py` - StoragePort ABC | P0 | 1.1 |
| 2.2 | Create `src/ports/messaging.py` - MessagingPort ABC | P0 | 1.1 |
| 2.3 | Create `src/ports/llm.py` - LLMPort ABC | P0 | 1.1 |
| 2.4 | Create `src/ports/warehouse.py` - DataWarehousePort ABC | P0 | 1.1 |
| 2.5 | Create `src/adapters/gcp/storage.py` - GCSAdapter | P0 | 2.1 |
| 2.6 | Create `src/adapters/gcp/messaging.py` - PubSubAdapter | P0 | 2.2 |
| 2.7 | Create `src/adapters/gcp/llm.py` - GeminiAdapter | P0 | 2.3 |
| 2.8 | Create `src/adapters/gcp/warehouse.py` - BigQueryAdapter | P0 | 2.4 |
| 2.9 | Create `src/adapters/factory.py` - AdapterFactory (GCP only) | P0 | 2.5-2.8 |

#### Phase 3: Core Services & Handlers

| # | Task | Priority | Dependencies |
|---|------|----------|--------------|
| 3.1 | Create `src/core/services/converter.py` - TIFF to PNG logic | P0 | 2.5 |
| 3.2 | Create `src/core/services/classifier.py` - Classification logic | P0 | 2.5 |
| 3.3 | Create `src/core/services/extractor.py` - LLM extraction logic | P0 | 2.7 |
| 3.4 | Create `src/core/services/writer.py` - BigQuery write logic | P0 | 2.8 |
| 3.5 | Create `src/handlers/converter_handler.py` - fnc-tiff-to-png-converter-{env} entry | P0 | 3.1 |
| 3.6 | Create `src/handlers/classifier_handler.py` - fnc-invoice-classifier-{env} entry | P0 | 3.2 |
| 3.7 | Create `src/handlers/extractor_handler.py` - fnc-data-extractor-{env} entry | P0 | 3.3 |
| 3.8 | Create `src/handlers/writer_handler.py` - fnc-bigquery-writer-{env} entry | P0 | 3.4 |
| 3.9 | Create `Dockerfile` for Cloud Run | P0 | 3.5-3.8 |

#### Phase 4: Testing

| # | Task | Priority | Dependencies |
|---|------|----------|--------------|
| 4.1 | Create mock adapters for testing | P1 | 2.1-2.4 |
| 4.2 | Write unit tests for converter service | P1 | 3.1, 4.1 |
| 4.3 | Write unit tests for classifier service | P1 | 3.2, 4.1 |
| 4.4 | Write unit tests for extractor service | P1 | 3.3, 4.1 |
| 4.5 | Write unit tests for writer service | P1 | 3.4, 4.1 |
| 4.6 | Write integration tests for GCP adapters | P1 | 2.5-2.8 |
| 4.7 | Create test fixtures (sample invoices) | P1 | 4.2-4.5 |

#### Phase 5: Deployment (Dev Environment - eda-gemini-dev)

| # | Task | Priority | Dependencies |
|---|------|----------|--------------|
| 5.1 | Create GCS bucket `eda-gemini-dev-pipeline` with folder structure | P0 | 4.6 |
| 5.2 | Create Pub/Sub topics (`eda-gemini-dev-*`) and subscriptions | P0 | 4.6 |
| 5.3 | Create BigQuery dataset `ds_bq_gemini_dev` and tables | P0 | 4.6 |
| 5.4 | Deploy `fnc-tiff-to-png-converter-dev` to Cloud Run | P0 | 5.1, 5.2 |
| 5.5 | Deploy `fnc-invoice-classifier-dev` to Cloud Run | P0 | 5.4 |
| 5.6 | Deploy `fnc-data-extractor-dev` to Cloud Run | P0 | 5.5 |
| 5.7 | Deploy `fnc-bigquery-writer-dev` to Cloud Run | P0 | 5.3, 5.6 |
| 5.8 | End-to-end pipeline test in dev | P0 | 5.7 |

#### Phase 6: Deployment (Prod Environment - eda-gemini-prd)

| # | Task | Priority | Dependencies |
|---|------|----------|--------------|
| 6.1 | Create GCS bucket `eda-gemini-prd-pipeline` with folder structure | P0 | 5.8 |
| 6.2 | Create Pub/Sub topics (`eda-gemini-prd-*`) and subscriptions | P0 | 5.8 |
| 6.3 | Create BigQuery dataset `ds_bq_gemini_prd` and tables | P0 | 5.8 |
| 6.4 | Deploy `fnc-tiff-to-png-converter-prd` to Cloud Run | P0 | 6.1, 6.2 |
| 6.5 | Deploy `fnc-invoice-classifier-prd` to Cloud Run | P0 | 6.4 |
| 6.6 | Deploy `fnc-data-extractor-prd` to Cloud Run | P0 | 6.5 |
| 6.7 | Deploy `fnc-bigquery-writer-prd` to Cloud Run | P0 | 6.3, 6.6 |
| 6.8 | End-to-end pipeline test in prod | P0 | 6.7 |

### 8.3 Task Dependencies Diagram

```
Phase 1 (Foundation)
────────────────────
1.1 ──┬── 1.2 ── 1.4
      │
      ├── 1.2b (prod config)
      │
      ├── 1.3
      │
      ├── 1.5
      │
      ├── 1.6
      │
      └── 1.7, 1.8

Phase 2 (Adapters - GCP Primary)
────────────────────────────────
2.1 ── 2.5 ──┐
2.2 ── 2.6 ──┼── 2.9
2.3 ── 2.7 ──┤
2.4 ── 2.8 ──┘

Phase 3 (Services)
──────────────────
2.5 ── 3.1 ── 3.5 ──┐
2.5 ── 3.2 ── 3.6 ──┼── 3.9
2.7 ── 3.3 ── 3.7 ──┤
2.8 ── 3.4 ── 3.8 ──┘

Phase 4 (Testing)
─────────────────
2.1-2.4 ── 4.1 ──┬── 4.2
                 ├── 4.3
                 ├── 4.4
                 ├── 4.5
                 └── 4.6 ── 4.7

Phase 5 (Dev Deployment - eda-gemini-dev)
─────────────────────────────────────────
4.6 ──┬── 5.1 ── 5.4 ── 5.5 ── 5.6 ──┬── 5.8
      │                              │
      ├── 5.2 ───────────────────────┤
      │                              │
      └── 5.3 ── 5.7 ────────────────┘

Phase 6 (Prod Deployment - eda-gemini-prd)
──────────────────────────────────────────
5.8 ──┬── 6.1 ── 6.4 ── 6.5 ── 6.6 ──┬── 6.8
      │                              │
      ├── 6.2 ───────────────────────┤
      │                              │
      └── 6.3 ── 6.7 ────────────────┘
```

---

## 9. Appendix

### 9.1 Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Runtime | Python | 3.11+ |
| Validation | Pydantic | 2.x |
| Image Processing | Pillow | 10.x |
| GCS | google-cloud-storage | 2.x |
| Pub/Sub | google-cloud-pubsub | 2.x |
| BigQuery | google-cloud-bigquery | 3.x |
| LLM | google-generativeai | 0.x |
| HTTP Server | FastAPI | 0.x |
| YAML | PyYAML | 6.x |

### 9.2 Environment Variables (Not Used - Config in YAML)

All configuration is in YAML files. The only environment variable that MAY be used:

| Variable | Purpose | Default |
|----------|---------|---------|
| `CONFIG_PATH` | Override config file location | `config/pipeline.yaml` |
| `GOOGLE_CLOUD_PROJECT` | GCP project (set by Cloud Run) | From config |
| `ENVIRONMENT` | Environment selector (dev/prd) | `dev` |

### 9.3 GCP Resource Summary

| Resource Type | Dev (eda-gemini-dev) | Prod (eda-gemini-prd) |
|---------------|----------------------|------------------------|
| GCS Bucket | `eda-gemini-dev-pipeline` | `eda-gemini-prd-pipeline` |
| BigQuery Dataset | `ds_bq_gemini_dev` | `ds_bq_gemini_prd` |
| Cloud Run Functions | `fnc-*-dev` | `fnc-*-prd` |
| Pub/Sub Topics | `eda-gemini-dev-*` | `eda-gemini-prd-*` |
| Secrets | `eda-gemini-dev-*` | `eda-gemini-prd-*` |

### 9.4 Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Config format | YAML | Human-readable, supports comments |
| Folder flow | 5 stages | Visible pipeline, easy debugging |
| Adapter pattern | GCP primary with extensibility | Best practice, future flexibility |
| v1 exclusions | DLQ, LangFuse, Scaling | Focus on core pipeline |
| LLM | Gemini 2.5 Pro | Best vision capabilities |
| Cloud Focus | GCP only | Project requirement |
| Naming convention | `fnc-{name}-{env}` | Clear, consistent, environment-aware |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2026-01-26 | Updated naming conventions: GCP projects (eda-gemini-dev/prd), function names (fnc-*-{env}), BigQuery datasets (ds_bq_gemini_{env}), GCS buckets (eda-gemini-{env}-pipeline), Pub/Sub topics (eda-gemini-{env}-*). Clarified GCP as primary focus with Adapter Pattern for future extensibility. |
| 2.0 | 2026-01-26 | Complete rewrite with config decoupling, GCS folder flow, adapter pattern |
| 1.0 | 2026-01-XX | Initial architecture design |

---

*Generated by the-planner agent | Confidence: 0.95 (HIGH)*
