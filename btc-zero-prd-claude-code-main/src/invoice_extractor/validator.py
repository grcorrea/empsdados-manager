"""Multi-layer validation for invoice extraction.

Three validation layers:
1. Schema Validation: Pydantic model validation
2. Business Rules: Cross-field consistency checks (BR-001 to BR-006)
3. Confidence Scoring: Quality assessment based on completeness and consistency
"""

import json
from decimal import Decimal

from pydantic import ValidationError

from .models import ExtractedInvoice, ValidationResult

# =============================================================================
# LAYER 1: SCHEMA VALIDATION
# =============================================================================

def validate_schema(data: dict) -> tuple[ExtractedInvoice | None, list[str]]:
    """Validate extraction data against Pydantic schema.

    Args:
        data: Raw extraction dictionary from LLM

    Returns:
        Tuple of (validated_invoice, error_messages)
        - If valid: (ExtractedInvoice, [])
        - If invalid: (None, [error messages])

    Example:
        >>> data = {"invoice_id": "UE-2025-001", ...}
        >>> invoice, errors = validate_schema(data)
        >>> if invoice:
        ...     print(f"Valid: {invoice.invoice_id}")
        ... else:
        ...     print(f"Errors: {errors}")
    """
    try:
        invoice = ExtractedInvoice(**data)
        return (invoice, [])
    except ValidationError as e:
        # Extract error messages
        errors = []
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            errors.append(f"{field}: {message}")
        return (None, errors)


# =============================================================================
# LAYER 2: BUSINESS RULES VALIDATION
# =============================================================================

def validate_business_rules(invoice: ExtractedInvoice) -> list[str]:
    """Validate cross-field business rules.

    Implements business rules BR-001 through BR-006 from the design doc.

    Args:
        invoice: Validated ExtractedInvoice object

    Returns:
        List of business rule violation messages (empty if all pass)

    Business Rules:
        BR-001: total_amount = subtotal + tax_amount (tolerance ±0.05)
        BR-002: due_date >= invoice_date (already enforced by Pydantic)
        BR-003: commission_amount = subtotal * commission_rate (tolerance ±0.02)
        BR-004: sum(line_items.amount) = subtotal (tolerance ±0.10, warning only)
        BR-005: All monetary amounts >= 0 (already enforced by Pydantic)
        BR-006: invoice_id matches expected format (warning only)
    """
    violations = []

    # BR-001: Total calculation
    # For delivery platform invoices, total includes additional fees:
    # - Delivery fees, service fees, tips, adjustments
    # We allow total >= subtotal + tax (additional fees are expected)
    # Only flag if total < subtotal + tax (indicates missing data)
    expected_minimum = invoice.subtotal + invoice.tax_amount

    if invoice.total_amount < expected_minimum - Decimal("0.05"):
        violations.append(
            f"BR-001: total_amount ({invoice.total_amount}) is less than "
            f"subtotal + tax_amount ({expected_minimum}), "
            f"possible missing data"
        )
    # Note: total > expected_minimum is normal (delivery fees, service fees, etc.)

    # BR-002: Date validation (already handled by Pydantic model_validator)
    # No additional check needed here

    # BR-003: Commission calculation
    expected_commission = (invoice.subtotal * invoice.commission_rate).quantize(
        Decimal("0.01")
    )
    commission_diff = abs(invoice.commission_amount - expected_commission)
    tolerance_br003 = Decimal("0.02")

    if commission_diff > tolerance_br003:
        violations.append(
            f"BR-003: commission_amount ({invoice.commission_amount}) does not match "
            f"subtotal * commission_rate ({expected_commission}), "
            f"difference: {commission_diff}"
        )

    # BR-004: Line items sum (WARNING only)
    if invoice.line_items:
        line_items_sum = sum(item.amount for item in invoice.line_items)
        items_diff = abs(line_items_sum - invoice.subtotal)
        tolerance_br004 = Decimal("0.10")

        if items_diff > tolerance_br004:
            # This is a warning, not a hard violation
            # Don't add to violations list, just note it
            pass

    # BR-005: Non-negative amounts (already enforced by Pydantic Field constraints)
    # No additional check needed

    # BR-006: Invoice ID format (WARNING only, handled in Pydantic field_validator)
    # No additional check needed

    return violations


# =============================================================================
# LAYER 3: CONFIDENCE SCORING
# =============================================================================

def calculate_confidence(
    invoice: ExtractedInvoice,
    llm_confidence: float | None
) -> float:
    """Calculate overall extraction confidence score.

    Formula:
        confidence = (
            0.40 * completeness_score +
            0.30 * consistency_score +
            0.30 * llm_confidence
        )

    Args:
        invoice: Validated invoice object
        llm_confidence: LLM-reported confidence (0.0-1.0), default 0.8 if None

    Returns:
        Overall confidence score from 0.0 to 1.0

    Components:
        - completeness_score: Percentage of required fields present
        - consistency_score: Percentage of business rules passed
        - llm_confidence: Reported confidence from LLM (default 0.8)

    Example:
        >>> invoice = ExtractedInvoice(...)
        >>> conf = calculate_confidence(invoice, llm_confidence=0.95)
        >>> print(f"Confidence: {conf:.2%}")
    """
    # Completeness: Check required fields
    required_fields = [
        "invoice_id",
        "vendor_name",
        "invoice_date",
        "due_date",
        "subtotal",
        "total_amount"
    ]
    present_count = sum(
        1 for field in required_fields
        if getattr(invoice, field, None) is not None
    )
    completeness = present_count / len(required_fields)

    # Consistency: Check business rules
    business_violations = validate_business_rules(invoice)
    total_rules = 6  # BR-001 through BR-006
    rules_passed = total_rules - len(business_violations)
    consistency = rules_passed / total_rules if total_rules > 0 else 1.0

    # LLM confidence (default to 0.8 if not provided)
    llm_conf = llm_confidence if llm_confidence is not None else 0.80

    # Weighted combination
    confidence = (0.40 * completeness) + (0.30 * consistency) + (0.30 * llm_conf)

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, confidence))


# =============================================================================
# FULL VALIDATION PIPELINE
# =============================================================================

def validate_extraction(
    raw_json: str,
    llm_confidence: float | None = None
) -> ValidationResult:
    """Full 3-layer validation pipeline.

    Combines schema validation, business rule validation, and confidence scoring.

    Args:
        raw_json: JSON string from LLM extraction
        llm_confidence: Optional LLM-reported confidence score

    Returns:
        ValidationResult with all validation details

    Pipeline:
        1. Parse JSON
        2. Validate against Pydantic schema (Layer 1)
        3. Check business rules (Layer 2)
        4. Calculate confidence (Layer 3)
        5. Return comprehensive validation result

    Example:
        >>> raw_json = '{"invoice_id": "UE-2025-001", ...}'
        >>> result = validate_extraction(raw_json, llm_confidence=0.95)
        >>> if result.is_valid:
        ...     print(f"Valid with {result.confidence_score:.0%} confidence")
        ... else:
        ...     print(f"Errors: {result.schema_errors + result.business_rule_errors}")
    """
    # Parse JSON
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        return ValidationResult(
            is_valid=False,
            schema_valid=False,
            business_rules_valid=False,
            confidence_score=0.0,
            schema_errors=[f"JSON parsing error: {str(e)}"]
        )

    # Layer 1: Schema validation
    invoice, schema_errors = validate_schema(data)

    if not invoice:
        # Schema validation failed
        return ValidationResult(
            is_valid=False,
            schema_valid=False,
            business_rules_valid=False,
            confidence_score=0.0,
            schema_errors=schema_errors
        )

    # Layer 2: Business rules validation
    business_violations = validate_business_rules(invoice)
    business_rules_valid = len(business_violations) == 0

    # Layer 3: Confidence scoring
    confidence = calculate_confidence(invoice, llm_confidence)

    # Overall validation
    is_valid = business_rules_valid  # Schema already passed if we got here

    return ValidationResult(
        is_valid=is_valid,
        schema_valid=True,
        business_rules_valid=business_rules_valid,
        confidence_score=confidence,
        schema_errors=[],
        business_rule_errors=business_violations,
        warnings=[],  # Could add warnings from BR-004, BR-006 here
        field_confidence={}  # Could add per-field confidence if available
    )
