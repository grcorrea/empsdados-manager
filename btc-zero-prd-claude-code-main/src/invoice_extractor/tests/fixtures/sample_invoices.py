"""Sample invoice data for testing.

Provides realistic test data for all vendor types and edge cases.
"""

from datetime import date
from decimal import Decimal

from ...models import ExtractedInvoice, LineItem, VendorType


SAMPLE_LINE_ITEMS = [
    LineItem(description="Order Sales", quantity=1, unit_price=Decimal("1250.00")),
    LineItem(description="Delivery Fees", quantity=1, unit_price=Decimal("185.00")),
    LineItem(description="Promotions Adjustment", quantity=1, unit_price=Decimal("45.00")),
]

SAMPLE_UBEREATS_INVOICE = {
    "invoice_id": "UE-2026-001234",
    "vendor_name": "Test Restaurant ABC",
    "vendor_type": "ubereats",
    "invoice_date": "2026-01-15",
    "due_date": "2026-01-29",
    "currency": "USD",
    "line_items": [
        {"description": "Order Sales", "quantity": 1, "unit_price": "1250.00"},
        {"description": "Delivery Fees Collected", "quantity": 1, "unit_price": "185.00"},
        {"description": "Promotions Adjustment", "quantity": 1, "unit_price": "45.00"},
    ],
    "subtotal": "1480.00",
    "tax_amount": "0.00",
    "commission_rate": "0.25",
    "commission_amount": "370.00",
    "total_amount": "1110.00",
}

SAMPLE_DOORDASH_INVOICE = {
    "invoice_id": "DD-2026-789012",
    "vendor_name": "City Diner",
    "vendor_type": "doordash",
    "invoice_date": "2026-01-21",
    "due_date": "2026-01-24",
    "currency": "USD",
    "line_items": [
        {"description": "Order Subtotal", "quantity": 1, "unit_price": "2340.50"},
        {"description": "Tips", "quantity": 1, "unit_price": "456.75"},
        {"description": "Delivery Fees", "quantity": 1, "unit_price": "234.00"},
    ],
    "subtotal": "3031.25",
    "tax_amount": "0.00",
    "commission_rate": "0.20",
    "commission_amount": "606.25",
    "total_amount": "2425.00",
}

SAMPLE_IFOOD_INVOICE = {
    "invoice_id": "IF-2026-123456",
    "vendor_name": "Restaurante Sabor Caseiro",
    "vendor_type": "ifood",
    "invoice_date": "2026-01-15",
    "due_date": "2026-01-22",
    "currency": "BRL",
    "line_items": [
        {"description": "Vendas de Pedidos", "quantity": 1, "unit_price": "4850.00"},
        {"description": "Taxa de Entrega Repassada", "quantity": 1, "unit_price": "612.00"},
    ],
    "subtotal": "5462.00",
    "tax_amount": "0.00",
    "commission_rate": "0.23",
    "commission_amount": "1256.26",
    "total_amount": "4205.74",
}

SAMPLE_EXTRACTED_INVOICE = ExtractedInvoice(
    invoice_id="UE-2026-001234",
    vendor_name="Test Restaurant ABC",
    vendor_type=VendorType.UBEREATS,
    invoice_date=date(2026, 1, 15),
    due_date=date(2026, 1, 29),
    currency="USD",
    line_items=SAMPLE_LINE_ITEMS,
    subtotal=Decimal("1480.00"),
    tax_amount=Decimal("0.00"),
    commission_rate=Decimal("0.25"),
    commission_amount=Decimal("370.00"),
    total_amount=Decimal("1110.00"),
)


def create_sample_invoice(
    vendor_type: VendorType = VendorType.UBEREATS,
    invoice_id: str | None = None,
    vendor_name: str | None = None,
    total_amount: Decimal | None = None,
) -> ExtractedInvoice:
    """Create a sample invoice for testing with optional overrides.

    Args:
        vendor_type: Vendor type to use
        invoice_id: Optional custom invoice ID
        vendor_name: Optional custom vendor name
        total_amount: Optional custom total amount

    Returns:
        ExtractedInvoice with specified or default values
    """
    vendor_prefixes = {
        VendorType.UBEREATS: "UE",
        VendorType.DOORDASH: "DD",
        VendorType.GRUBHUB: "GH",
        VendorType.IFOOD: "IF",
        VendorType.RAPPI: "RP",
        VendorType.OTHER: "INV",
    }

    prefix = vendor_prefixes.get(vendor_type, "INV")
    default_id = f"{prefix}-2026-{hash(vendor_type.value) % 1000000:06d}"

    currencies = {
        VendorType.UBEREATS: "USD",
        VendorType.DOORDASH: "USD",
        VendorType.GRUBHUB: "USD",
        VendorType.IFOOD: "BRL",
        VendorType.RAPPI: "BRL",
        VendorType.OTHER: "USD",
    }

    return ExtractedInvoice(
        invoice_id=invoice_id or default_id,
        vendor_name=vendor_name or f"Test {vendor_type.value.title()} Restaurant",
        vendor_type=vendor_type,
        invoice_date=date(2026, 1, 15),
        due_date=date(2026, 1, 29),
        currency=currencies.get(vendor_type, "USD"),
        line_items=[
            LineItem(description="Food Sales", quantity=1, unit_price=Decimal("1000.00")),
            LineItem(description="Delivery Fees", quantity=1, unit_price=Decimal("150.00")),
        ],
        subtotal=Decimal("1150.00"),
        tax_amount=Decimal("0.00"),
        commission_rate=Decimal("0.20"),
        commission_amount=Decimal("230.00"),
        total_amount=total_amount or Decimal("920.00"),
    )


def create_minimal_tiff() -> bytes:
    """Create a minimal valid TIFF for testing.

    Returns:
        Bytes representing a minimal 1x1 white TIFF image
    """
    import io
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="TIFF")
    return buffer.getvalue()


def create_multipage_tiff(pages: int = 3) -> bytes:
    """Create a multi-page TIFF for testing.

    Args:
        pages: Number of pages to include

    Returns:
        Bytes representing a multi-page TIFF image
    """
    import io
    from PIL import Image

    images = []
    for i in range(pages):
        color = (255 - i * 50, 255 - i * 50, 255 - i * 50)
        img = Image.new("RGB", (200, 200), color=color)
        images.append(img)

    buffer = io.BytesIO()
    images[0].save(
        buffer,
        format="TIFF",
        save_all=True,
        append_images=images[1:],
    )
    return buffer.getvalue()
