"""Jinja2-based HTML renderer for invoice templates."""

from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from invoice_gen.schemas.delivery import DeliveryInfo
from invoice_gen.schemas.invoice import InvoiceData
from invoice_gen.schemas.partner import PartnerBrand
from invoice_gen.schemas.payment import PaymentInfo


def currency_filter(value: Decimal | float | int) -> str:
    return f"${float(value):,.2f}"


def star_rating_filter(value: float) -> str:
    full_stars = int(value)
    half_star = 1 if value - full_stars >= 0.5 else 0
    empty_stars = 5 - full_stars - half_star
    return "★" * full_stars + "⯪" * half_star + "☆" * empty_stars


class HTMLRenderer:
    def __init__(self, templates_dir: Path | None = None, assets_dir: Path | None = None):
        if templates_dir is None:
            package_root = Path(__file__).parent.parent.parent.parent
            templates_dir = package_root / "templates"
        if assets_dir is None:
            package_root = Path(__file__).parent.parent.parent.parent
            assets_dir = package_root / "assets"

        self.templates_dir = templates_dir
        self.assets_dir = assets_dir

        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )
        self.env.filters["currency"] = currency_filter
        self.env.filters["star_rating"] = star_rating_filter

    def render(
        self,
        invoice: InvoiceData,
        partner: PartnerBrand,
        delivery: DeliveryInfo | None = None,
        payment: PaymentInfo | None = None,
    ) -> str:
        template_name = f"{invoice.vendor_type.value}.html.j2"
        template = self.env.get_template(template_name)

        return template.render(
            invoice=invoice,
            partner=partner,
            delivery=delivery,
            payment=payment,
            assets_path=str(self.assets_dir.absolute()),
        )

    def get_template_path(self, vendor_type: str) -> Path:
        return self.templates_dir / f"{vendor_type}.html.j2"
