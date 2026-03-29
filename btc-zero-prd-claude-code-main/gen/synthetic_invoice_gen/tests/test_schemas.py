"""Tests for Pydantic schema models."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from invoice_gen.schemas.delivery import DeliveryInfo
from invoice_gen.schemas.invoice import InvoiceData, LineItem, VendorType
from invoice_gen.schemas.partner import PartnerBrand
from invoice_gen.schemas.payment import PaymentInfo, PaymentMethod


class TestLineItem:
    def test_create_valid_line_item(self, sample_line_item: LineItem) -> None:
        assert sample_line_item.description == "Classic Cheeseburger"
        assert sample_line_item.quantity == 2
        assert sample_line_item.unit_price == Decimal("12.99")
        assert len(sample_line_item.modifiers) == 2

    def test_amount_calculation(self, sample_line_item: LineItem) -> None:
        expected = Decimal("25.98")
        assert sample_line_item.amount == expected

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            LineItem(description="Test", quantity=0, unit_price=Decimal("10.00"))

    def test_price_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            LineItem(description="Test", quantity=1, unit_price=Decimal("-5.00"))


class TestInvoiceData:
    def test_create_valid_invoice(self, sample_invoice: InvoiceData) -> None:
        assert sample_invoice.invoice_id == "INV-UE-ABC123"
        assert sample_invoice.vendor_type == VendorType.UBEREATS
        assert len(sample_invoice.line_items) == 2

    def test_formatted_order_date(self, sample_invoice: InvoiceData) -> None:
        assert "January 25, 2026" in sample_invoice.formatted_order_date

    def test_items_count(self, sample_invoice: InvoiceData) -> None:
        assert sample_invoice.items_count == 3

    def test_at_least_one_line_item_required(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="INV-001",
                order_id="ORD-001",
                vendor_type=VendorType.UBEREATS,
                restaurant_name="Test",
                restaurant_address="123 Test St",
                restaurant_phone="555-1234",
                restaurant_ein="12-3456789",
                restaurant_rating=4.0,
                cuisine_type="American",
                order_date=datetime.now(),
                customer_name="Test Customer",
                customer_phone="555-9876",
                line_items=[],
                subtotal=Decimal("0"),
                delivery_fee=Decimal("0"),
                service_fee=Decimal("0"),
                total_amount=Decimal("0"),
            )

    def test_currency_validation(self, sample_invoice: InvoiceData) -> None:
        assert sample_invoice.currency == "USD"


class TestVendorType:
    def test_all_vendor_types(self) -> None:
        vendors = list(VendorType)
        assert len(vendors) == 5
        assert VendorType.UBEREATS in vendors
        assert VendorType.DOORDASH in vendors
        assert VendorType.GRUBHUB in vendors
        assert VendorType.IFOOD in vendors
        assert VendorType.RAPPI in vendors


class TestPartnerBrand:
    def test_create_valid_partner(self, sample_partner: PartnerBrand) -> None:
        assert sample_partner.name == "ubereats"
        assert sample_partner.display_name == "Uber Eats"
        assert sample_partner.primary_color == "#06C167"

    def test_css_variables(self, sample_partner: PartnerBrand) -> None:
        css_vars = sample_partner.css_variables
        assert "--primary-color" in css_vars
        assert css_vars["--primary-color"] == "#06C167"

    def test_invalid_color_format(self) -> None:
        with pytest.raises(ValidationError):
            PartnerBrand(
                name="test",
                display_name="Test",
                primary_color="invalid",
                secondary_color="#FFFFFF",
                accent_color="#000000",
                font_family="sans-serif",
                logo_path="test.svg",
            )


class TestDeliveryInfo:
    def test_create_valid_delivery(self, sample_delivery: DeliveryInfo) -> None:
        assert sample_delivery.customer_name == "John Smith"
        assert sample_delivery.distance_miles == 2.5

    def test_formatted_distance(self, sample_delivery: DeliveryInfo) -> None:
        assert sample_delivery.formatted_distance == "2.5 mi"

    def test_formatted_times(self, sample_delivery: DeliveryInfo) -> None:
        assert sample_delivery.formatted_estimated == "01:00 PM"
        assert sample_delivery.formatted_actual == "12:55 PM"


class TestPaymentInfo:
    def test_create_valid_payment(self, sample_payment: PaymentInfo) -> None:
        assert sample_payment.method == PaymentMethod.CREDIT_CARD
        assert sample_payment.card_last_four == "4242"

    def test_masked_card(self, sample_payment: PaymentInfo) -> None:
        assert sample_payment.masked_card == "**** **** **** 4242"

    def test_formatted_method(self, sample_payment: PaymentInfo) -> None:
        assert sample_payment.formatted_method == "Credit Card"

    def test_invalid_card_last_four(self) -> None:
        with pytest.raises(ValidationError):
            PaymentInfo(
                method=PaymentMethod.CREDIT_CARD,
                card_last_four="123",
                transaction_id="TXN123",
                payment_date=datetime.now(),
            )
