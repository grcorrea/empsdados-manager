"""Tests for the render pipeline (HTML, PDF, TIFF)."""

import shutil
from pathlib import Path

import pytest

from invoice_gen.render.html_renderer import HTMLRenderer, currency_filter, star_rating_filter
from invoice_gen.schemas.delivery import DeliveryInfo
from invoice_gen.schemas.invoice import InvoiceData, VendorType
from invoice_gen.schemas.partner import PartnerBrand
from invoice_gen.schemas.payment import PaymentInfo


def _check_poppler_installed() -> bool:
    return shutil.which("pdftoppm") is not None


class TestCurrencyFilter:
    def test_format_integer(self) -> None:
        assert currency_filter(100) == "$100.00"

    def test_format_decimal(self) -> None:
        from decimal import Decimal

        assert currency_filter(Decimal("42.50")) == "$42.50"

    def test_format_large_number(self) -> None:
        assert currency_filter(1234567.89) == "$1,234,567.89"


class TestStarRatingFilter:
    def test_full_stars(self) -> None:
        assert star_rating_filter(5.0) == "★★★★★"

    def test_partial_stars(self) -> None:
        assert star_rating_filter(4.5) == "★★★★⯪"
        assert star_rating_filter(3.5) == "★★★⯪☆"

    def test_low_rating(self) -> None:
        assert star_rating_filter(2.0) == "★★☆☆☆"


class TestHTMLRenderer:
    def test_render_html_content(
        self,
        sample_invoice: InvoiceData,
        sample_partner: PartnerBrand,
    ) -> None:
        renderer = HTMLRenderer()
        html = renderer.render(sample_invoice, sample_partner)

        assert "<!DOCTYPE html>" in html
        assert sample_invoice.invoice_id in html
        assert sample_partner.display_name in html
        assert sample_invoice.restaurant_name in html

    def test_render_includes_line_items(
        self,
        sample_invoice: InvoiceData,
        sample_partner: PartnerBrand,
    ) -> None:
        renderer = HTMLRenderer()
        html = renderer.render(sample_invoice, sample_partner)

        for item in sample_invoice.line_items:
            assert item.description in html

    def test_render_with_delivery_info(
        self,
        sample_invoice: InvoiceData,
        sample_partner: PartnerBrand,
        sample_delivery: DeliveryInfo,
    ) -> None:
        renderer = HTMLRenderer()
        html = renderer.render(
            sample_invoice,
            sample_partner,
            delivery=sample_delivery,
        )

        assert sample_delivery.customer_name in html
        assert sample_delivery.driver_name in html

    def test_render_with_payment_info(
        self,
        sample_invoice: InvoiceData,
        sample_partner: PartnerBrand,
        sample_payment: PaymentInfo,
    ) -> None:
        renderer = HTMLRenderer()
        html = renderer.render(
            sample_invoice,
            sample_partner,
            payment=sample_payment,
        )

        assert sample_payment.masked_card in html
        assert sample_payment.transaction_id in html

    def test_render_all_vendors(
        self,
        sample_invoice: InvoiceData,
    ) -> None:
        from invoice_gen.brands.registry import get_brand

        renderer = HTMLRenderer()

        for vendor_type in VendorType:
            invoice = InvoiceData(
                **{**sample_invoice.model_dump(), "vendor_type": vendor_type}
            )
            partner = get_brand(vendor_type)
            html = renderer.render(invoice, partner)
            assert partner.display_name in html


class TestPDFGenerator:
    @pytest.mark.skipif(
        not _check_poppler_installed(),
        reason="Poppler not installed",
    )
    def test_generate_pdf_bytes(
        self,
        sample_invoice: InvoiceData,
        sample_partner: PartnerBrand,
    ) -> None:
        from invoice_gen.render.pdf_generator import PDFGenerator

        renderer = HTMLRenderer()
        pdf_gen = PDFGenerator()

        html = renderer.render(sample_invoice, sample_partner)
        pdf_bytes = pdf_gen.generate(html)

        assert pdf_bytes
        assert pdf_bytes[:4] == b"%PDF"

    @pytest.mark.skipif(
        not _check_poppler_installed(),
        reason="Poppler not installed",
    )
    def test_generate_pdf_to_file(
        self,
        sample_invoice: InvoiceData,
        sample_partner: PartnerBrand,
        output_dir: Path,
    ) -> None:
        from invoice_gen.render.pdf_generator import PDFGenerator

        renderer = HTMLRenderer()
        pdf_gen = PDFGenerator()

        html = renderer.render(sample_invoice, sample_partner)
        output_path = output_dir / "test_invoice.pdf"
        pdf_gen.generate(html, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestTiffConverter:
    @pytest.mark.skipif(
        not _check_poppler_installed(),
        reason="Poppler not installed",
    )
    def test_pdf_to_tiff(
        self,
        sample_invoice: InvoiceData,
        sample_partner: PartnerBrand,
        output_dir: Path,
    ) -> None:
        from invoice_gen.render.pdf_generator import PDFGenerator
        from invoice_gen.render.tiff_converter import TiffConverter

        renderer = HTMLRenderer()
        pdf_gen = PDFGenerator()
        tiff_conv = TiffConverter()

        html = renderer.render(sample_invoice, sample_partner)
        pdf_bytes = pdf_gen.generate(html)

        output_path = output_dir / "test_invoice.tiff"
        tiff_conv.pdf_to_tiff(pdf_bytes, output_path)

        assert output_path.exists()
        assert output_path.suffix == ".tiff"
