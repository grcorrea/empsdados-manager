"""Tests for Faker-based data generation."""

from decimal import Decimal

from invoice_gen.data.faker_gen import InvoiceDataGenerator
from invoice_gen.schemas.invoice import VendorType


class TestInvoiceDataGenerator:
    def test_generate_invoice_with_seed(self) -> None:
        gen = InvoiceDataGenerator(seed=42)
        invoice1 = gen.generate(VendorType.UBEREATS)

        gen2 = InvoiceDataGenerator(seed=42)
        invoice2 = gen2.generate(VendorType.UBEREATS)

        assert invoice1.vendor_type == invoice2.vendor_type
        assert invoice1.currency == invoice2.currency
        assert len(invoice1.line_items) > 0
        assert len(invoice2.line_items) > 0

    def test_generate_invoice_different_seeds(self) -> None:
        gen1 = InvoiceDataGenerator(seed=42)
        gen2 = InvoiceDataGenerator(seed=123)

        invoice1 = gen1.generate(VendorType.UBEREATS)
        invoice2 = gen2.generate(VendorType.UBEREATS)

        assert invoice1.invoice_id != invoice2.invoice_id

    def test_invoice_id_format(self, data_generator: InvoiceDataGenerator) -> None:
        invoice = data_generator.generate(VendorType.UBEREATS)
        assert invoice.invoice_id.startswith("INV-UE-")

        invoice_dd = data_generator.generate(VendorType.DOORDASH)
        assert invoice_dd.invoice_id.startswith("INV-DD-")

    def test_all_vendors_supported(self, data_generator: InvoiceDataGenerator) -> None:
        for vendor_type in VendorType:
            invoice = data_generator.generate(vendor_type)
            assert invoice.vendor_type == vendor_type
            assert invoice.invoice_id is not None

    def test_invoice_has_required_fields(self, data_generator: InvoiceDataGenerator) -> None:
        invoice = data_generator.generate(VendorType.UBEREATS)

        assert invoice.invoice_id
        assert invoice.order_id
        assert invoice.restaurant_name
        assert invoice.restaurant_address
        assert invoice.restaurant_ein
        assert invoice.order_date
        assert len(invoice.line_items) >= 2

    def test_financial_calculations(self, data_generator: InvoiceDataGenerator) -> None:
        invoice = data_generator.generate(VendorType.UBEREATS)

        line_items_total = sum(item.amount for item in invoice.line_items)
        assert invoice.subtotal == line_items_total

        expected_total = (
            invoice.subtotal
            + invoice.delivery_fee
            + invoice.service_fee
            + invoice.tip_amount
            - invoice.discount_amount
        )
        assert invoice.total_amount == expected_total

    def test_currency_is_usd(self, data_generator: InvoiceDataGenerator) -> None:
        invoice = data_generator.generate(VendorType.UBEREATS)
        assert invoice.currency == "USD"

    def test_rating_in_valid_range(self, data_generator: InvoiceDataGenerator) -> None:
        for _ in range(10):
            invoice = data_generator.generate(VendorType.UBEREATS)
            assert 3.5 <= invoice.restaurant_rating <= 5.0

    def test_generate_delivery_info(self, data_generator: InvoiceDataGenerator) -> None:
        delivery = data_generator.generate_delivery_info()

        assert delivery.customer_name
        assert delivery.customer_address
        assert delivery.driver_name
        assert delivery.estimated_delivery
        assert 0.5 <= delivery.distance_miles <= 10.0

    def test_generate_payment_info(self, data_generator: InvoiceDataGenerator) -> None:
        from datetime import datetime

        order_date = datetime.now()
        payment = data_generator.generate_payment_info(order_date)

        assert payment.card_last_four
        assert len(payment.card_last_four) == 4
        assert payment.transaction_id
        assert payment.payment_date == order_date


class TestLineItemGeneration:
    def test_line_items_have_valid_quantities(
        self, data_generator: InvoiceDataGenerator
    ) -> None:
        for _ in range(10):
            invoice = data_generator.generate(VendorType.UBEREATS)
            for item in invoice.line_items:
                assert 1 <= item.quantity <= 3

    def test_line_items_have_valid_prices(
        self, data_generator: InvoiceDataGenerator
    ) -> None:
        for _ in range(10):
            invoice = data_generator.generate(VendorType.UBEREATS)
            for item in invoice.line_items:
                assert item.unit_price >= Decimal("0")

    def test_modifiers_optional(self, data_generator: InvoiceDataGenerator) -> None:
        invoices_with_modifiers = 0
        for _ in range(20):
            invoice = data_generator.generate(VendorType.UBEREATS)
            for item in invoice.line_items:
                if item.modifiers:
                    invoices_with_modifiers += 1
                    break

        assert invoices_with_modifiers > 0
