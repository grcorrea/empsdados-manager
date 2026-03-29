"""Invoice extraction pipeline orchestration.

Coordinates the full extraction workflow:
1. Image processing (TIFF → PNG)
2. Prompt template loading
3. LLM extraction (Gemini with OpenRouter fallback)
4. Validation (schema + business rules)
5. Result storage (JSON + Parquet)
"""

import json
import time
from pathlib import Path

from .image_processor import process_invoice_image
from .llm_gateway import (
    GeminiConfig,
    OpenRouterConfig,
    extract_with_fallback,
)
from .models import (
    ExtractedInvoice,
    ExtractionResult,
    ExtractionSource,
    get_extraction_schema_json,
)
from .validator import validate_extraction

# =============================================================================
# PROMPT MANAGEMENT
# =============================================================================

def load_prompt_template(vendor_type: str = "ubereats") -> str:
    """Load vendor-specific prompt template.

    Args:
        vendor_type: Vendor platform type (ubereats, doordash, grubhub)

    Returns:
        Prompt template string with {schema} placeholder

    Raises:
        FileNotFoundError: If template file doesn't exist

    Example:
        >>> template = load_prompt_template("ubereats")
        >>> "{schema}" in template
        True
    """
    # Get template path relative to this file
    template_dir = Path(__file__).parent / "prompts"
    template_path = template_dir / f"{vendor_type}.txt"

    if not template_path.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {template_path}\n"
            f"Available templates: {list(template_dir.glob('*.txt'))}"
        )

    return template_path.read_text(encoding="utf-8")


def build_extraction_prompt(template: str, schema_json: str) -> str:
    """Combine prompt template with JSON schema.

    Args:
        template: Prompt template with {schema} placeholder
        schema_json: JSON schema string from get_extraction_schema_json()

    Returns:
        Complete extraction prompt ready for LLM

    Example:
        >>> template = load_prompt_template("ubereats")
        >>> schema = get_extraction_schema_json()
        >>> prompt = build_extraction_prompt(template, schema)
        >>> "ExtractedInvoice" in prompt
        True
    """
    return template.replace("{schema}", schema_json)


# =============================================================================
# SINGLE INVOICE EXTRACTION
# =============================================================================

def extract_invoice(
    input_path: Path,
    output_dir: Path,
    processed_dir: Path,
    errors_dir: Path,
    gemini_config: GeminiConfig,
    openrouter_config: OpenRouterConfig,
    vendor_type: str = "ubereats"
) -> ExtractionResult:
    """Full extraction pipeline for a single invoice.

    Pipeline Steps:
        1. Process image (TIFF → PNG, resize, etc.)
        2. Load and build extraction prompt
        3. Call LLM with fallback chain
        4. Parse JSON response
        5. Validate extraction
        6. Save result or error

    Args:
        input_path: Path to input invoice file (TIFF/PNG)
        output_dir: Directory to save successful extractions
        processed_dir: Directory to save processed images
        errors_dir: Directory to save failed extractions
        gemini_config: Gemini configuration
        openrouter_config: OpenRouter configuration
        vendor_type: Vendor platform type for prompt selection

    Returns:
        ExtractionResult with invoice data or error details

    Example:
        >>> from pathlib import Path
        >>> result = extract_invoice(
        ...     input_path=Path("data/input/invoice.tiff"),
        ...     output_dir=Path("data/output"),
        ...     processed_dir=Path("data/processed"),
        ...     errors_dir=Path("data/errors"),
        ...     gemini_config=GeminiConfig(),
        ...     openrouter_config=OpenRouterConfig(api_key="sk-...")
        ... )
        >>> if result.success:
        ...     print(f"Extracted: {result.invoice.invoice_id}")
    """
    start_time = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    errors_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Process image
    processing_result = process_invoice_image(input_path, processed_dir)

    if not processing_result.success:
        return ExtractionResult(
            invoice=None,
            success=False,
            source=ExtractionSource.GEMINI,
            errors=[f"Image processing failed: {processing_result.error_message}"],
            input_file=str(input_path)
        )

    # Step 2: Load prompt template
    try:
        template = load_prompt_template(vendor_type)
        schema_json = get_extraction_schema_json()
        prompt = build_extraction_prompt(template, schema_json)
    except Exception as e:
        return ExtractionResult(
            invoice=None,
            success=False,
            source=ExtractionSource.GEMINI,
            errors=[f"Prompt loading failed: {str(e)}"],
            input_file=str(input_path)
        )

    # Step 3: Call LLM with fallback
    llm_response = extract_with_fallback(
        prompt=prompt,
        image_paths=processing_result.output_paths,
        gemini_config=gemini_config,
        openrouter_config=openrouter_config
    )

    if not llm_response.success:
        return ExtractionResult(
            invoice=None,
            success=False,
            source=ExtractionSource(llm_response.provider),
            latency_ms=llm_response.latency_ms,
            errors=[f"LLM extraction failed: {llm_response.error_message}"],
            raw_response=llm_response.content,
            input_file=str(input_path)
        )

    # Step 4: Parse and validate
    validation_result = validate_extraction(
        raw_json=llm_response.content,
        llm_confidence=None  # Could extract from LLM response if available
    )

    if not validation_result.is_valid:
        # Validation failed
        all_errors = validation_result.schema_errors + validation_result.business_rule_errors
        return ExtractionResult(
            invoice=None,
            success=False,
            source=ExtractionSource(llm_response.provider),
            latency_ms=llm_response.latency_ms,
            tokens_used=llm_response.tokens_used,
            errors=all_errors,
            warnings=validation_result.warnings,
            raw_response=llm_response.content,
            input_file=str(input_path)
        )

    # Step 5: Parse successful extraction
    try:
        invoice_data = json.loads(llm_response.content)
        invoice = ExtractedInvoice(**invoice_data)
    except Exception as e:
        return ExtractionResult(
            invoice=None,
            success=False,
            source=ExtractionSource(llm_response.provider),
            latency_ms=llm_response.latency_ms,
            errors=[f"Failed to parse validated JSON: {str(e)}"],
            raw_response=llm_response.content,
            input_file=str(input_path)
        )

    # Success!
    latency_ms = int((time.time() - start_time) * 1000)

    return ExtractionResult(
        invoice=invoice,
        success=True,
        source=ExtractionSource(llm_response.provider),
        confidence=validation_result.confidence_score,
        latency_ms=latency_ms,
        tokens_used=llm_response.tokens_used,
        errors=[],
        warnings=validation_result.warnings,
        raw_response=llm_response.content,
        input_file=str(input_path)
    )


# =============================================================================
# BATCH EXTRACTION
# =============================================================================

def batch_extract(
    input_dir: Path,
    output_dir: Path,
    processed_dir: Path,
    errors_dir: Path,
    gemini_config: GeminiConfig,
    openrouter_config: OpenRouterConfig,
    vendor_type: str = "ubereats"
) -> list[ExtractionResult]:
    """Process multiple invoices from a directory.

    Args:
        input_dir: Directory containing input invoice files
        output_dir: Directory to save successful extractions
        processed_dir: Directory to save processed images
        errors_dir: Directory to save failed extractions
        gemini_config: Gemini configuration
        openrouter_config: OpenRouter configuration
        vendor_type: Vendor platform type

    Returns:
        List of ExtractionResult objects, one per input file

    Example:
        >>> results = batch_extract(
        ...     input_dir=Path("data/input"),
        ...     output_dir=Path("data/output"),
        ...     processed_dir=Path("data/processed"),
        ...     errors_dir=Path("data/errors"),
        ...     gemini_config=GeminiConfig(),
        ...     openrouter_config=OpenRouterConfig(api_key="sk-...")
        ... )
        >>> success_count = sum(1 for r in results if r.success)
        >>> print(f"Processed {len(results)} files, {success_count} successful")
    """
    # Find all invoice files
    invoice_files = []
    for pattern in ["*.tiff", "*.tif", "*.png", "*.jpg", "*.jpeg"]:
        invoice_files.extend(input_dir.glob(pattern))

    if not invoice_files:
        print(f"No invoice files found in {input_dir}")
        return []

    print(f"Found {len(invoice_files)} invoice files to process")

    results = []
    for i, input_path in enumerate(invoice_files, 1):
        print(f"\n[{i}/{len(invoice_files)}] Processing: {input_path.name}")

        result = extract_invoice(
            input_path=input_path,
            output_dir=output_dir,
            processed_dir=processed_dir,
            errors_dir=errors_dir,
            gemini_config=gemini_config,
            openrouter_config=openrouter_config,
            vendor_type=vendor_type
        )

        results.append(result)

        if result.success:
            print(f"  ✓ Success: {result.invoice.invoice_id} ({result.latency_ms}ms)")
            # Save result
            save_result(result, output_dir)
        else:
            print(f"  ✗ Failed: {result.errors[0] if result.errors else 'Unknown error'}")
            # Save error
            save_error(result, errors_dir, input_path)

    # Summary
    success_count = sum(1 for r in results if r.success)
    print(f"\n{'='*60}")
    print(f"Batch Complete: {success_count}/{len(results)} successful")
    print(f"{'='*60}")

    return results


# =============================================================================
# RESULT STORAGE
# =============================================================================

def save_result(result: ExtractionResult, output_dir: Path) -> None:
    """Save successful extraction result as JSON.

    Args:
        result: Successful ExtractionResult
        output_dir: Directory to save output files

    Output filename: {invoice_id}.json
    """
    if not result.success or not result.invoice:
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Use invoice_id as filename
    output_path = output_dir / f"{result.invoice.invoice_id}.json"

    # Serialize to JSON
    output_data = {
        "invoice": result.invoice.model_dump(mode="json"),
        "metadata": {
            "source": result.source,
            "confidence": result.confidence,
            "latency_ms": result.latency_ms,
            "tokens_used": result.tokens_used,
            "input_file": result.input_file
        }
    }

    output_path.write_text(
        json.dumps(output_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def save_error(result: ExtractionResult, errors_dir: Path, input_path: Path) -> None:
    """Save failed extraction details.

    Args:
        result: Failed ExtractionResult
        errors_dir: Directory to save error files
        input_path: Original input file path

    Output filename: {input_filename}_error.json
    """
    errors_dir.mkdir(parents=True, exist_ok=True)

    # Use input filename with _error suffix
    error_path = errors_dir / f"{input_path.stem}_error.json"

    error_data = {
        "input_file": str(input_path),
        "errors": result.errors,
        "warnings": result.warnings,
        "source": result.source,
        "latency_ms": result.latency_ms,
        "raw_response": result.raw_response
    }

    error_path.write_text(
        json.dumps(error_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
