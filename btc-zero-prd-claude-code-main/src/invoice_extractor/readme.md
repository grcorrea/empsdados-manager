# Invoice Extractor

> AI-powered CLI tool for extracting structured data from delivery platform invoices

## Overview

Invoice Extractor is a command-line tool that uses Large Language Models (LLMs) to extract structured data from delivery platform invoices. It processes invoice images (TIFF, PNG, JPEG) and outputs validated JSON data with financial details, line items, and metadata.

The tool uses **Gemini 2.0 Flash** as the primary extraction engine with **OpenRouter** (Claude 3.5 Sonnet) as an automatic fallback, ensuring high availability and reliability.

**Key Benefits:**

- Reduces manual data entry time by 80%+
- Achieves 90%+ extraction accuracy with 3-layer validation
- Processes invoices in under 30 seconds (P95)
- Supports 6 delivery platforms with vendor-specific prompts

## Features

- **Multi-format Support**: Process TIFF (including multi-page), PNG, and JPEG invoice images
- **Vendor-specific Extraction**: Optimized prompts for UberEats, DoorDash, Grubhub, iFood, Rappi, and generic invoices
- **Dual LLM Architecture**: Gemini 2.0 Flash primary with OpenRouter fallback
- **3-Layer Validation**: Schema validation, business rules, and confidence scoring
- **Batch Processing**: Process entire directories of invoices
- **Structured Output**: Pydantic-validated JSON with full type safety
- **Image Optimization**: Automatic TIFF splitting, RGB conversion, and LLM-optimized resizing

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/owshq-academy/btc-zero-prd-claude-code.git
cd btc-zero-prd-claude-code

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Configuration

Set the required environment variables:

```bash
# Required: OpenRouter API key (fallback provider)
export OPENROUTER_API_KEY="sk-or-v1-..."

# Optional: GCP project for Gemini (uses Application Default Credentials)
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
```

Or create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```

### First Use

```bash
# Extract a single invoice
python -m invoice_extractor extract data/input/invoice.tiff

# Extract with specific vendor
python -m invoice_extractor extract invoice.png --vendor ubereats

# View help
python -m invoice_extractor --help
```

## CLI Commands

### extract

Process a single invoice file.

```bash
invoice-extractor extract INPUT_FILE [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `INPUT_FILE` | Path to invoice file (TIFF, PNG, or JPEG) |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir` | `data/output` | Directory for extracted JSON files |
| `--processed-dir` | `data/processed` | Directory for processed images |
| `--errors-dir` | `data/errors` | Directory for error logs |
| `--vendor` | `ubereats` | Vendor type: ubereats, doordash, grubhub, ifood, rappi, auto |
| `--gemini-project` | `$GOOGLE_CLOUD_PROJECT` | GCP project ID for Gemini |
| `--openrouter-key` | `$OPENROUTER_API_KEY` | OpenRouter API key (required) |

**Examples:**

```bash
# Basic extraction
invoice-extractor extract data/input/invoice.tiff

# Extract with custom output directory
invoice-extractor extract invoice.tiff --output-dir results/

# Extract DoorDash invoice
invoice-extractor extract doordash_invoice.png --vendor doordash

# Extract with explicit API key
invoice-extractor extract invoice.tiff --openrouter-key sk-or-v1-xxx
```

**Output:**

```
Extracting invoice: data/input/invoice.tiff
Vendor: ubereats

Extraction successful!

Invoice ID: UE-2025-001234
Vendor: Restaurante Exemplo LTDA
Total: BRL 1050.00
Confidence: 94.5%
Latency: 2450ms
Provider: gemini

Saved to: data/output/UE-2025-001234.json
```

### batch

Process all invoices in a directory.

```bash
invoice-extractor batch INPUT_DIR [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `INPUT_DIR` | Directory containing invoice files |

**Options:**

Same as `extract` command.

**Examples:**

```bash
# Process all invoices in a directory
invoice-extractor batch data/input/

# Process with specific vendor type
invoice-extractor batch invoices/ --vendor ifood --output-dir results/
```

**Output:**

```
Batch processing directory: data/input/
Vendor: ubereats

Found 5 invoice files to process

[1/5] Processing: invoice_001.tiff
  Success: UE-2025-001234 (2450ms)

[2/5] Processing: invoice_002.tiff
  Success: UE-2025-001235 (1890ms)

...

============================================================
All 5 invoices processed successfully!
============================================================
```

### validate

Validate a JSON extraction result against schema and business rules.

```bash
invoice-extractor validate JSON_FILE
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `JSON_FILE` | Path to extracted invoice JSON file |

**Examples:**

```bash
# Validate an extraction result
invoice-extractor validate data/output/UE-2025-001234.json
```

**Output (Success):**

```
Validating: data/output/UE-2025-001234.json

Validation passed!

Confidence: 94.5%
```

**Output (Failure):**

```
Validating: data/output/invalid_invoice.json

Validation failed!

Schema Errors:
  - invoice_id: String should match pattern '^[A-Z]{2,4}-\d{4}-\d{4,8}$'

Business Rule Violations:
  - BR-003: commission_amount (200.00) does not match subtotal * commission_rate (150.00)

Confidence: 45.0%
```

## Supported Vendors

The extractor includes vendor-specific prompt templates optimized for each platform's invoice format:

| Vendor | Code | Invoice ID Pattern | Currency |
|--------|------|-------------------|----------|
| UberEats | `ubereats` | UE-YYYY-NNNNNN | BRL, USD |
| DoorDash | `doordash` | DD-YYYY-NNNNNN | USD |
| Grubhub | `grubhub` | GH-YYYY-NNNNNN | USD |
| iFood | `ifood` | IF-YYYY-NNNNNN | BRL |
| Rappi | `rappi` | RP-YYYY-NNNNNN | BRL, COP, MXN |
| Generic | `auto` | Any format | Any |

Each vendor template includes:
- Platform-specific field locations and naming conventions
- Expected invoice structure and line item types
- Currency and regional formatting rules
- Commission calculation patterns

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | API key for OpenRouter fallback provider |
| `GOOGLE_CLOUD_PROJECT` | No | GCP project ID for Gemini API access |
| `GOOGLE_API_KEY` | No | Alternative: Direct Gemini API key |

### LLM Configuration

**Gemini Configuration:**

| Setting | Default | Description |
|---------|---------|-------------|
| Model | `gemini-2.0-flash` | Gemini model version |
| Region | `us-central1` | GCP region |
| Max Retries | 2 | Retry attempts before fallback |
| Timeout | 30s | Request timeout |
| Temperature | 0.1 | Low for consistent extraction |

**OpenRouter Configuration:**

| Setting | Default | Description |
|---------|---------|-------------|
| Model | `anthropic/claude-3.5-sonnet` | Fallback model |
| Max Retries | 2 | Retry attempts |
| Timeout | 30s | Request timeout |
| Temperature | 0.1 | Low for consistent extraction |

## Architecture Overview

```
                          INVOICE EXTRACTOR PIPELINE

    INPUT                 PROCESSING                           OUTPUT
    -----                 ----------                           ------

    +--------+     +----------------+     +-------------+     +--------+
    | TIFF   |---->| Image Process  |---->| LLM Extract |---->| JSON   |
    | PNG    |     | - Split pages  |     | - Gemini    |     | Output |
    | JPEG   |     | - Convert RGB  |     | - OpenRouter|     +--------+
    +--------+     | - Resize 4096  |     | - Fallback  |         |
                   +----------------+     +-------------+         |
                                                |                 |
                                                v                 v
                                          +-------------+   +-----------+
                                          | 3-Layer     |   | Error     |
                                          | Validation  |   | Logging   |
                                          +-------------+   +-----------+
                                                |
                                                v
                                          +-----------+
                                          | Pydantic  |
                                          | Schema    |
                                          +-----------+

    VALIDATION LAYERS:
    Layer 1: Pydantic schema validation
    Layer 2: Business rules (BR-001 to BR-006)
    Layer 3: Confidence scoring (completeness + consistency + LLM confidence)
```

### Pipeline Steps

1. **Image Processing**
   - Load TIFF/PNG/JPEG file
   - Split multi-page TIFF into separate images
   - Convert to RGB color mode
   - Resize to max 4096px (LLM input limit)
   - Save as optimized PNG

2. **Prompt Building**
   - Load vendor-specific prompt template
   - Inject JSON schema for structured output
   - Combine with processed images

3. **LLM Extraction**
   - Call Gemini 2.0 Flash with images + prompt
   - On failure: exponential backoff (1s, 2s, 4s)
   - After max retries: fallback to OpenRouter

4. **Validation**
   - Layer 1: Pydantic schema validation
   - Layer 2: Business rule checks (BR-001 to BR-006)
   - Layer 3: Confidence score calculation

5. **Output**
   - Save validated JSON to output directory
   - Save errors to errors directory
   - Return structured result with metadata

## Data Models

### ExtractedInvoice

The main output schema for extracted invoice data:

```python
{
    # Header Fields
    "invoice_id": "UE-2025-001234",      # Unique identifier (pattern: XX-YYYY-NNNNNN)
    "vendor_name": "Restaurant Name",     # Business name from invoice
    "vendor_type": "ubereats",            # Platform type
    "invoice_date": "2025-01-15",         # Issue date (YYYY-MM-DD)
    "due_date": "2025-02-15",             # Payment due date
    "currency": "BRL",                    # ISO currency code

    # Line Items
    "line_items": [
        {
            "description": "Food Delivery Sales",
            "quantity": 1,
            "unit_price": "1000.00"
            # "amount" is computed: quantity * unit_price
        }
    ],

    # Financial Summary
    "subtotal": "1000.00",                # Sum of line items
    "tax_amount": "50.00",                # Tax amount
    "commission_rate": "0.15",            # Platform commission (0.0-1.0)
    "commission_amount": "150.00",        # Calculated commission
    "total_amount": "1050.00"             # Final invoice total
}
```

### Validation Rules

| Rule | Description | Tolerance |
|------|-------------|-----------|
| BR-001 | `total_amount >= subtotal + tax_amount` | +/- 0.05 |
| BR-002 | `due_date >= invoice_date` | Exact |
| BR-003 | `commission_amount = subtotal * commission_rate` | +/- 0.02 |
| BR-004 | `sum(line_items) = subtotal` | +/- 0.10 (warning) |
| BR-005 | All monetary amounts >= 0 | Exact |
| BR-006 | Invoice ID matches pattern | Warning only |

### Confidence Score

The confidence score (0.0-1.0) is calculated as:

```
confidence = 0.40 * completeness + 0.30 * consistency + 0.30 * llm_confidence
```

Where:
- **completeness**: Percentage of required fields present
- **consistency**: Percentage of business rules passed
- **llm_confidence**: Model-reported confidence (default 0.8)

## Examples

### Single File Extraction

```bash
# Extract UberEats invoice
invoice-extractor extract data/input/ubereats_jan_2025.tiff \
    --vendor ubereats \
    --output-dir results/
```

### Batch Processing

```bash
# Process all January invoices
invoice-extractor batch data/input/january/ \
    --vendor ubereats \
    --output-dir results/january/
```

### Programmatic Usage

```python
import sys
sys.path.insert(0, "src")

from pathlib import Path
from invoice_extractor import (
    extract_invoice,
    ExtractedInvoice,
    GeminiConfig,
    OpenRouterConfig,
)

# Configure LLM providers
gemini_config = GeminiConfig(project_id="my-gcp-project")
openrouter_config = OpenRouterConfig(api_key="sk-or-v1-...")

# Extract single invoice
result = extract_invoice(
    input_path=Path("data/input/invoice.tiff"),
    output_dir=Path("data/output"),
    processed_dir=Path("data/processed"),
    errors_dir=Path("data/errors"),
    gemini_config=gemini_config,
    openrouter_config=openrouter_config,
    vendor_type="ubereats"
)

if result.success:
    invoice = result.invoice
    print(f"Invoice ID: {invoice.invoice_id}")
    print(f"Total: {invoice.currency} {invoice.total_amount}")
    print(f"Confidence: {result.confidence:.1%}")
else:
    print(f"Extraction failed: {result.errors}")
```

### Validate Existing JSON

```python
from invoice_extractor import validate_extraction

with open("data/output/UE-2025-001234.json") as f:
    raw_json = f.read()

result = validate_extraction(raw_json)

if result.is_valid:
    print(f"Valid with {result.confidence_score:.0%} confidence")
else:
    print(f"Schema errors: {result.schema_errors}")
    print(f"Business rule errors: {result.business_rule_errors}")
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=invoice_extractor --cov-report=term-missing

# Run specific test file
pytest tests/test_validator.py -v
```

### Code Quality

```bash
# Format and lint with Ruff
ruff check src/invoice-extractor/ --fix
ruff format src/invoice-extractor/
```

### Project Structure

```
src/invoice-extractor/
├── __init__.py           # Package exports
├── cli.py                # Click CLI commands
├── extractor.py          # Pipeline orchestration
├── models.py             # Pydantic data models
├── llm_gateway.py        # Gemini + OpenRouter integration
├── image_processor.py    # TIFF/PNG processing
├── validator.py          # 3-layer validation
└── prompts/              # Vendor-specific templates
    ├── ubereats.txt
    ├── doordash.txt
    ├── grubhub.txt
    ├── ifood.txt
    ├── rappi.txt
    └── generic.txt
```

## Troubleshooting

### Common Issues

**"OpenRouter API key required"**
```bash
# Set the environment variable
export OPENROUTER_API_KEY="sk-or-v1-your-key"
```

**"Gemini authentication failed"**
```bash
# Authenticate with GCP
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

**"Image processing failed"**
- Ensure the file is a valid TIFF, PNG, or JPEG
- Check file permissions
- Verify PIL/Pillow is installed: `pip install pillow`

**"Validation failed: BR-003"**
- Commission calculation mismatch
- Check if the invoice has non-standard commission structure
- Review raw LLM response in error log

### Debug Mode

For detailed debugging, examine the error logs:

```bash
# Check error details
cat data/errors/invoice_001_error.json
```

Error logs include:
- Original input file path
- All error and warning messages
- LLM provider used
- Processing latency
- Raw LLM response (for debugging)

## License

MIT License - see LICENSE file for details.

## Related Documentation

- [Project CLAUDE.md](../../.claude/CLAUDE.md) - Main project documentation
- [Architecture Overview](../../design/invoice-extractor-design.md) - System design
- [Requirements](../../design/invoice-extractor-requirements.md) - Business requirements
