"""Main invoice generation orchestrator."""

from dataclasses import dataclass
from pathlib import Path

from invoice_gen.brands.registry import get_brand
from invoice_gen.data.faker_gen import InvoiceDataGenerator
from invoice_gen.render.html_renderer import HTMLRenderer
from invoice_gen.render.pdf_generator import PDFGenerator
from invoice_gen.render.tiff_converter import TiffConverter
from invoice_gen.schemas.invoice import InvoiceData, VendorType


@dataclass
class GeneratedInvoice:
    invoice_data: InvoiceData
    tiff_path: Path
    html_path: Path | None = None
    pdf_path: Path | None = None


class InvoiceGenerator:
    def __init__(
        self,
        seed: int | None = None,
        output_dir: Path | None = None,
        dpi: int = 200,
        include_delivery: bool = True,
        include_payment: bool = True,
        failure_rate: float = 0.0,
        keep_intermediates: bool = False,
    ):
        self.seed = seed
        self.output_dir = output_dir or Path("./output")
        self.dpi = dpi
        self.include_delivery = include_delivery
        self.include_payment = include_payment
        self.failure_rate = failure_rate
        self.keep_intermediates = keep_intermediates

        self.data_generator = InvoiceDataGenerator(seed=seed, failure_rate=failure_rate)
        self.html_renderer = HTMLRenderer()
        self.pdf_generator = PDFGenerator()
        self.tiff_converter = TiffConverter(dpi=dpi)

    def generate(self, vendor_type: VendorType) -> InvoiceData:
        return self.data_generator.generate(vendor_type)

    def generate_html(self, vendor_type: VendorType) -> tuple[InvoiceData, str]:
        invoice = self.generate(vendor_type)
        brand = get_brand(vendor_type)

        delivery = None
        payment = None

        if self.include_delivery:
            delivery = self.data_generator.generate_delivery_info()

        if self.include_payment:
            payment = self.data_generator.generate_payment_info(invoice.order_date)

        html_content = self.html_renderer.render(
            invoice=invoice,
            partner=brand,
            delivery=delivery,
            payment=payment,
        )

        return invoice, html_content

    def generate_pdf(self, vendor_type: VendorType, output_path: Path | None = None) -> GeneratedInvoice:
        invoice, html_content = self.generate_html(vendor_type)

        if output_path is None:
            filename = self._generate_filename(invoice, "pdf")
            output_path = self.output_dir / filename

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_generator.generate(html_content, output_path)

        result = GeneratedInvoice(
            invoice_data=invoice,
            tiff_path=output_path,
        )

        if self.keep_intermediates:
            html_path = output_path.with_suffix(".html")
            html_path.write_text(html_content, encoding="utf-8")
            result.html_path = html_path

        return result

    def generate_tiff(self, vendor_type: VendorType, output_path: Path | None = None) -> GeneratedInvoice:
        invoice, html_content = self.generate_html(vendor_type)

        if output_path is None:
            filename = self._generate_filename(invoice, "tiff")
            output_path = self.output_dir / filename

        self.output_dir.mkdir(parents=True, exist_ok=True)

        pdf_bytes = self.pdf_generator.generate(html_content)
        self.tiff_converter.pdf_to_tiff(pdf_bytes, output_path)

        result = GeneratedInvoice(
            invoice_data=invoice,
            tiff_path=output_path,
        )

        if self.keep_intermediates:
            html_path = output_path.with_suffix(".html")
            pdf_path = output_path.with_suffix(".pdf")

            html_path.write_text(html_content, encoding="utf-8")
            pdf_path.write_bytes(pdf_bytes)

            result.html_path = html_path
            result.pdf_path = pdf_path

        return result

    def generate_batch(
        self,
        vendor_types: list[VendorType],
        count_per_vendor: int = 1,
    ) -> list[GeneratedInvoice]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        generated = []

        for vendor_type in vendor_types:
            for _ in range(count_per_vendor):
                try:
                    result = self.generate_tiff(vendor_type)
                    generated.append(result)
                except Exception as e:
                    print(f"Error generating invoice for {vendor_type.value}: {e}")
                    continue

        return generated

    def _generate_filename(self, invoice: InvoiceData, extension: str) -> str:
        date_str = invoice.order_date.strftime("%Y%m%d")
        return f"{invoice.vendor_type.value}_{invoice.invoice_id}_{date_str}.{extension}"
