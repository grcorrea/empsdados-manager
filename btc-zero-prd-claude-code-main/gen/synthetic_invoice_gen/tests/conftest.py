"""Pytest fixtures for invoice generator tests."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from invoice_gen.brands.registry import get_brand
from invoice_gen.data.faker_gen import InvoiceDataGenerator
from invoice_gen.schemas.delivery import DeliveryInfo
from invoice_gen.schemas.invoice import InvoiceData, LineItem, VendorType
from invoice_gen.schemas.partner import PartnerBrand
from invoice_gen.schemas.payment import PaymentInfo, PaymentMethod


@pytest.fixture
def sample_line_item() -> LineItem:
    return LineItem(
        description="Classic Cheeseburger",
        quantity=2,
        unit_price=Decimal("12.99"),
        modifiers=["Extra cheese", "No onions"],
    )


@pytest.fixture
def sample_invoice() -> InvoiceData:
    return InvoiceData(
        invoice_id="INV-UE-ABC123",
        order_id="ORD12345",
        vendor_type=VendorType.UBEREATS,
        restaurant_name="The Classic Diner",
        restaurant_address="123 Main St, New York, NY 10001",
        restaurant_phone="(555) 123-4567",
        restaurant_ein="12-3456789",
        restaurant_rating=4.5,
        cuisine_type="American",
        order_date=datetime(2026, 1, 25, 12, 30, 0),
        customer_name="John Smith",
        customer_phone="(555) 987-6543",
        line_items=[
            LineItem(
                description="Classic Cheeseburger",
                quantity=2,
                unit_price=Decimal("12.99"),
            ),
            LineItem(
                description="Large Fries",
                quantity=1,
                unit_price=Decimal("4.99"),
            ),
        ],
        subtotal=Decimal("30.97"),
        delivery_fee=Decimal("4.99"),
        service_fee=Decimal("1.55"),
        tip_amount=Decimal("5.00"),
        discount_amount=Decimal("0"),
        total_amount=Decimal("42.51"),
        currency="USD",
    )


@pytest.fixture
def sample_partner() -> PartnerBrand:
    return get_brand(VendorType.UBEREATS)


@pytest.fixture
def sample_delivery() -> DeliveryInfo:
    return DeliveryInfo(
        customer_name="John Smith",
        customer_address="456 Oak Ave, Brooklyn, NY 11201",
        customer_phone="(555) 987-6543",
        delivery_instructions="Leave at door",
        driver_name="Mike",
        estimated_delivery=datetime(2026, 1, 25, 13, 0, 0),
        actual_delivery=datetime(2026, 1, 25, 12, 55, 0),
        distance_miles=2.5,
    )


@pytest.fixture
def sample_payment() -> PaymentInfo:
    return PaymentInfo(
        method=PaymentMethod.CREDIT_CARD,
        card_last_four="4242",
        card_brand="Visa",
        transaction_id="TXN123456789",
        payment_date=datetime(2026, 1, 25, 12, 30, 0),
        is_successful=True,
    )


@pytest.fixture
def data_generator() -> InvoiceDataGenerator:
    return InvoiceDataGenerator(seed=42)


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    output = tmp_path / "output"
    output.mkdir()
    return output
