"""Partner brand registry with color and font configurations."""

from invoice_gen.schemas.invoice import VendorType
from invoice_gen.schemas.partner import PartnerBrand


class BrandRegistry:
    _brands: dict[VendorType, PartnerBrand] = {
        VendorType.UBEREATS: PartnerBrand(
            name="ubereats",
            display_name="Uber Eats",
            primary_color="#06C167",
            secondary_color="#000000",
            accent_color="#276EF1",
            font_family="Inter, sans-serif",
            logo_path="assets/logos/ubereats.svg",
            tagline="Get almost, almost anything",
        ),
        VendorType.DOORDASH: PartnerBrand(
            name="doordash",
            display_name="DoorDash",
            primary_color="#FF3008",
            secondary_color="#FFFFFF",
            accent_color="#1F1F1F",
            font_family="Poppins, sans-serif",
            logo_path="assets/logos/doordash.svg",
            tagline="Delivery & takeout from the best restaurants",
        ),
        VendorType.GRUBHUB: PartnerBrand(
            name="grubhub",
            display_name="Grubhub",
            primary_color="#F63440",
            secondary_color="#FFFFFF",
            accent_color="#0070EB",
            font_family="Roboto, sans-serif",
            logo_path="assets/logos/grubhub.svg",
            tagline="Perks make everything more rewarding",
        ),
        VendorType.IFOOD: PartnerBrand(
            name="ifood",
            display_name="iFood",
            primary_color="#EA1D2C",
            secondary_color="#FFFFFF",
            accent_color="#3E3E3E",
            font_family="Inter, sans-serif",
            logo_path="assets/logos/ifood.svg",
            tagline="Your food, delivered fast",
        ),
        VendorType.RAPPI: PartnerBrand(
            name="rappi",
            display_name="Rappi",
            primary_color="#FF441F",
            secondary_color="#FFFFFF",
            accent_color="#00B853",
            font_family="Poppins, sans-serif",
            logo_path="assets/logos/rappi.svg",
            tagline="Everything you need, delivered",
        ),
    }

    @classmethod
    def get(cls, vendor_type: VendorType) -> PartnerBrand:
        return cls._brands[vendor_type]

    @classmethod
    def all(cls) -> list[PartnerBrand]:
        return list(cls._brands.values())


def get_brand(vendor_type: VendorType) -> PartnerBrand:
    return BrandRegistry.get(vendor_type)
