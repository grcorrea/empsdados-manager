# Synthetic Invoice Generator

> CLI tool to generate premium-quality, brand-authentic multi-page TIFF invoices for testing data extraction pipelines.

## Overview

The Synthetic Invoice Generator creates realistic invoice documents for 5 major food delivery partners. Each invoice is rendered with authentic brand styling, professional typography, and real-world data patterns—making it ideal for testing OCR systems, LLM extraction pipelines, and document processing workflows.

**Why this tool?**

- Training and validating AI extraction models requires diverse, realistic test data
- Manual invoice creation is time-consuming and lacks consistency
- Real invoices contain sensitive data unsuitable for testing environments

**Who is it for?**

- Data engineers building invoice processing pipelines
- ML engineers testing document extraction models
- QA teams validating invoice parsing accuracy

## Quick Start

```bash
cd gen/synthetic-invoice-gen
pip install -e ".[dev]"

invoice-gen --partner ubereats --count 5
```

Generated invoices appear in `./output/` as multi-page TIFF files.

## Features

- **5 Partner Brands** — UberEats, DoorDash, Grubhub, iFood, Rappi with authentic colors and fonts
- **Premium Visual Quality** — Modern CSS with shadows, gradients, and professional typography
- **Realistic Data** — Faker-generated names, US addresses, EIN numbers, and USD prices
- **Customer Information** — Every invoice includes customer_name and customer_phone
- **Reproducible Output** — Seed support for deterministic generation
- **Multi-Page Support** — Automatic pagination for invoices with 8+ line items
- **LZW Compression** — Lossless TIFF output with optimal file sizes
- **Failure Injection** — Configurable rate of intentional math errors for validation testing
- **Debug Mode** — Keep HTML and PDF intermediates with `--keep-intermediates`
- **Pre-generated Samples** — See `samples/` directory for ready-to-use examples

## System Requirements

### Poppler (required for PDF to image conversion)

```bash
# macOS
brew install poppler

# Ubuntu/Debian
apt-get install poppler-utils

# Verify installation
pdftoppm -v
```

## Installation

```bash
cd gen/synthetic-invoice-gen
pip install -e ".[dev]"
```

## Usage

### Generate Single Invoice

```bash
invoice-gen --partner ubereats
invoice-gen --partner doordash --output ./my-output
```

### Generate Multiple Invoices

```bash
invoice-gen --partner ubereats --count 10
invoice-gen --all-partners --count 5
```

### Reproducible Generation

```bash
invoice-gen --partner ifood --seed 42
invoice-gen --partner ifood --seed 42
```

### Batch Generation

```bash
invoice-gen --all-partners --count 20
```

### Failure Injection

```bash
invoice-gen --all-partners --count 10 --failure-rate 0.15
```

### Debug Mode

```bash
invoice-gen --partner ubereats --count 5 --keep-intermediates
```

## CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--partner` | `-p` | Partner brand (ubereats, doordash, grubhub, ifood, rappi) | Required* |
| `--all-partners` | | Generate for all 5 partners | False |
| `--count` | `-n` | Number of invoices per partner | 1 |
| `--output` | `-o` | Output directory for TIFF files | ./output |
| `--seed` | | Random seed for reproducibility | None |
| `--format` | `-f` | Output format (tiff, pdf) | tiff |
| `--dpi` | | DPI for TIFF output | 200 |
| `--no-delivery` | | Exclude delivery information | False |
| `--no-payment` | | Exclude payment information | False |
| `--failure-rate` | | Rate (0.0-1.0) of invoices with wrong totals | 0.0 |
| `--keep-intermediates` | | Keep HTML and PDF intermediate files | False |

*Required unless `--all-partners` is used.

## Output Format

Generated TIFF files follow this naming convention:

```
{partner}_{invoice_id}_{date}.tiff

Examples:
ubereats_INV-UE-A1B2C3_20260125.tiff
doordash_INV-DD-X7Y8Z9_20260125.tiff
```

With `--keep-intermediates`:

```
ubereats_INV-UE-A1B2C3_20260125.html
ubereats_INV-UE-A1B2C3_20260125.pdf
ubereats_INV-UE-A1B2C3_20260125.tiff
```

## Samples Directory

Pre-generated samples are available in the `samples/` directory:

```
samples/
├── ubereats_INV-UE-308774_20260124.tiff
├── ubereats_INV-UE-308774_20260124.html
├── ubereats_INV-UE-308774_20260124.pdf
├── doordash_INV-DD-78F64F_20260123.tiff
├── doordash_INV-DD-78F64F_20260123.html
├── doordash_INV-DD-78F64F_20260123.pdf
└── ... (30 files total: 10 TIFF + 10 HTML + 10 PDF)
```

## Partner Brands

| Partner | Primary Color | Font |
|---------|---------------|------|
| UberEats | #06C167 (Green) | Inter |
| DoorDash | #FF3008 (Red) | Poppins |
| Grubhub | #F63440 (Red) | Roboto |
| iFood | #EA1D2C (Red) | Inter |
| Rappi | #FF441F (Orange) | Poppins |

## Invoice Schema

Each generated invoice includes:

| Field | Type | Description |
|-------|------|-------------|
| `invoice_id` | String | Unique identifier (e.g., INV-UE-A1B2C3) |
| `order_id` | String | Order reference |
| `vendor_type` | String | Partner brand |
| `restaurant_name` | String | Restaurant name |
| `restaurant_address` | String | Full address |
| `restaurant_phone` | String | Phone number |
| `restaurant_ein` | String | US EIN tax ID |
| `restaurant_rating` | Float | Star rating (3.5-5.0) |
| `cuisine_type` | String | American, Italian, Mexican, Asian, Fast Food |
| `order_date` | DateTime | Order timestamp |
| `customer_name` | String | Customer full name |
| `customer_phone` | String | Customer phone number |
| `line_items` | Array | Array of ordered items |
| `subtotal` | Decimal | Sum of line items |
| `delivery_fee` | Decimal | Delivery charge |
| `service_fee` | Decimal | Service charge |
| `tip_amount` | Decimal | Tip amount |
| `discount_amount` | Decimal | Any discounts |
| `total_amount` | Decimal | Final total |
| `currency` | String | USD |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYNTHETIC INVOICE GENERATOR                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   Pydantic   │───▶│    Jinja2    │───▶│  WeasyPrint  │───▶│  Pillow   │ │
│  │   Schemas    │    │  Templates   │    │  HTML → PDF  │    │  PDF→TIFF │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│        │                   │                                       │        │
│        ▼                   ▼                                       ▼        │
│  ┌──────────────┐    ┌──────────────┐                    ┌───────────────┐ │
│  │    Faker     │    │    Brand     │                    │  Multi-Page   │ │
│  │  Data Gen    │    │   Assets     │                    │    .tiff      │ │
│  │  (en_US)     │    │   (5 pkgs)   │                    │   output/     │ │
│  └──────────────┘    └──────────────┘                    └───────────────┘ │
│        │                                                                    │
│        ▼                                                                    │
│  ┌──────────────┐                                                           │
│  │   Failure    │  ← Intentionally corrupts totals for validation testing  │
│  │   Injector   │                                                           │
│  └──────────────┘                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Development

### Run Tests

```bash
pytest
pytest --cov=invoice_gen --cov-report=html
```

### Lint

```bash
ruff check .
ruff format .
```

## License

MIT
