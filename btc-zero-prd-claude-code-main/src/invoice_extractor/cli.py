"""Command-line interface for invoice extraction.

Provides three commands:
- extract: Process a single invoice file
- batch: Process all invoices in a directory
- validate: Validate a JSON extraction result
"""

import sys
from pathlib import Path

import click
from dotenv import load_dotenv

# Load environment variables from .env file in package directory
_package_dir = Path(__file__).parent
load_dotenv(_package_dir / ".env")

from .extractor import batch_extract, extract_invoice, save_error, save_result
from .llm_gateway import GeminiConfig, OpenRouterConfig
from .validator import validate_extraction

# =============================================================================
# CLI GROUP
# =============================================================================

@click.group()
@click.version_option(version="0.1.0", prog_name="invoice-extractor")
def cli():
    """Invoice Extractor - AI-powered invoice data extraction.

    Extract structured data from delivery platform invoices using
    Gemini 2.0 Flash with OpenRouter fallback.
    """
    pass


# =============================================================================
# EXTRACT COMMAND (SINGLE FILE)
# =============================================================================

@cli.command()
@click.argument(
    "input_file",
    type=click.Path(exists=True, path_type=Path)
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default="data/output",
    help="Output directory for extracted JSON files"
)
@click.option(
    "--processed-dir",
    type=click.Path(path_type=Path),
    default="data/processed",
    help="Directory for processed image files"
)
@click.option(
    "--errors-dir",
    type=click.Path(path_type=Path),
    default="data/errors",
    help="Directory for error logs"
)
@click.option(
    "--vendor",
    type=click.Choice(["ubereats", "doordash", "grubhub", "ifood", "rappi", "auto"]),
    default="ubereats",
    help="Vendor platform type"
)
@click.option(
    "--gemini-project",
    type=str,
    envvar="GOOGLE_CLOUD_PROJECT",
    help="GCP project ID for Gemini (or set GOOGLE_CLOUD_PROJECT)"
)
@click.option(
    "--openrouter-key",
    type=str,
    envvar="OPENROUTER_API_KEY",
    required=True,
    help="OpenRouter API key (or set OPENROUTER_API_KEY)"
)
def extract(
    input_file: Path,
    output_dir: Path,
    processed_dir: Path,
    errors_dir: Path,
    vendor: str,
    gemini_project: str | None,
    openrouter_key: str
):
    """Extract data from a single invoice file.

    INPUT_FILE: Path to invoice file (TIFF, PNG, or JPEG)

    Example:

        invoice-extract extract data/input/invoice.tiff

        invoice-extract extract invoice.tiff --vendor ubereats --output-dir results/
    """
    click.echo(f"Extracting invoice: {input_file}")
    click.echo(f"Vendor: {vendor}")
    click.echo()

    # Configure LLMs
    gemini_config = GeminiConfig(project_id=gemini_project)
    openrouter_config = OpenRouterConfig(api_key=openrouter_key)

    # Extract
    result = extract_invoice(
        input_path=input_file,
        output_dir=output_dir,
        processed_dir=processed_dir,
        errors_dir=errors_dir,
        gemini_config=gemini_config,
        openrouter_config=openrouter_config,
        vendor_type=vendor
    )

    # Display results
    if result.success:
        click.echo(click.style("✓ Extraction successful!", fg="green", bold=True))
        click.echo(f"\nInvoice ID: {result.invoice.invoice_id}")
        click.echo(f"Vendor: {result.invoice.vendor_name}")
        click.echo(f"Total: {result.invoice.currency} {result.invoice.total_amount}")
        click.echo(f"Confidence: {result.confidence:.1%}")
        click.echo(f"Latency: {result.latency_ms}ms")
        click.echo(f"Provider: {result.source}")

        # Save result
        save_result(result, output_dir)
        output_file = output_dir / f"{result.invoice.invoice_id}.json"
        click.echo(f"\nSaved to: {output_file}")

    else:
        click.echo(click.style("✗ Extraction failed!", fg="red", bold=True))
        click.echo("\nErrors:")
        for error in result.errors:
            click.echo(f"  - {error}")

        if result.warnings:
            click.echo("\nWarnings:")
            for warning in result.warnings:
                click.echo(f"  - {warning}")

        # Save error log
        save_error(result, errors_dir, input_file)
        error_file = errors_dir / f"{input_file.stem}_error.json"
        click.echo(f"\nError log saved to: {error_file}")

        sys.exit(1)


# =============================================================================
# BATCH COMMAND (DIRECTORY)
# =============================================================================

@cli.command()
@click.argument(
    "input_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default="data/output",
    help="Output directory for extracted JSON files"
)
@click.option(
    "--processed-dir",
    type=click.Path(path_type=Path),
    default="data/processed",
    help="Directory for processed image files"
)
@click.option(
    "--errors-dir",
    type=click.Path(path_type=Path),
    default="data/errors",
    help="Directory for error logs"
)
@click.option(
    "--vendor",
    type=click.Choice(["ubereats", "doordash", "grubhub", "ifood", "rappi", "auto"]),
    default="ubereats",
    help="Vendor platform type"
)
@click.option(
    "--gemini-project",
    type=str,
    envvar="GOOGLE_CLOUD_PROJECT",
    help="GCP project ID for Gemini"
)
@click.option(
    "--openrouter-key",
    type=str,
    envvar="OPENROUTER_API_KEY",
    required=True,
    help="OpenRouter API key"
)
def batch(
    input_dir: Path,
    output_dir: Path,
    processed_dir: Path,
    errors_dir: Path,
    vendor: str,
    gemini_project: str | None,
    openrouter_key: str
):
    """Process all invoices in a directory.

    INPUT_DIR: Directory containing invoice files

    Example:

        invoice-extract batch data/input/

        invoice-extract batch invoices/ --vendor ubereats --output-dir results/
    """
    click.echo(f"Batch processing directory: {input_dir}")
    click.echo(f"Vendor: {vendor}")
    click.echo()

    # Configure LLMs
    gemini_config = GeminiConfig(project_id=gemini_project)
    openrouter_config = OpenRouterConfig(api_key=openrouter_key)

    # Batch extract
    results = batch_extract(
        input_dir=input_dir,
        output_dir=output_dir,
        processed_dir=processed_dir,
        errors_dir=errors_dir,
        gemini_config=gemini_config,
        openrouter_config=openrouter_config,
        vendor_type=vendor
    )

    # Summary
    if results:
        success_count = sum(1 for r in results if r.success)
        total = len(results)

        click.echo()
        click.echo("=" * 60)
        if success_count == total:
            click.echo(click.style(f"✓ All {total} invoices processed successfully!", fg="green"))
        elif success_count > 0:
            click.echo(click.style(
                f"⚠ {success_count}/{total} invoices processed successfully",
                fg="yellow"
            ))
        else:
            click.echo(click.style(f"✗ All {total} invoices failed", fg="red"))
        click.echo("=" * 60)

        if success_count < total:
            sys.exit(1)
    else:
        click.echo("No invoice files found in directory")
        sys.exit(1)


# =============================================================================
# VALIDATE COMMAND (JSON FILE)
# =============================================================================

@cli.command()
@click.argument(
    "json_file",
    type=click.Path(exists=True, path_type=Path)
)
def validate(json_file: Path):
    """Validate a JSON extraction result.

    JSON_FILE: Path to extracted invoice JSON file

    Example:

        invoice-extract validate data/output/UE-2025-001234.json
    """
    click.echo(f"Validating: {json_file}")
    click.echo()

    # Read JSON
    try:
        raw_json = json_file.read_text(encoding="utf-8")
    except Exception as e:
        click.echo(click.style(f"✗ Failed to read file: {e}", fg="red"))
        sys.exit(1)

    # Validate
    result = validate_extraction(raw_json)

    # Display results
    if result.is_valid:
        click.echo(click.style("✓ Validation passed!", fg="green", bold=True))
        click.echo(f"\nConfidence: {result.confidence_score:.1%}")

        if result.warnings:
            click.echo("\nWarnings:")
            for warning in result.warnings:
                click.echo(f"  - {warning}")

    else:
        click.echo(click.style("✗ Validation failed!", fg="red", bold=True))

        if not result.schema_valid:
            click.echo("\nSchema Errors:")
            for error in result.schema_errors:
                click.echo(f"  - {error}")

        if not result.business_rules_valid:
            click.echo("\nBusiness Rule Violations:")
            for error in result.business_rule_errors:
                click.echo(f"  - {error}")

        if result.warnings:
            click.echo("\nWarnings:")
            for warning in result.warnings:
                click.echo(f"  - {warning}")

        click.echo(f"\nConfidence: {result.confidence_score:.1%}")
        sys.exit(1)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
