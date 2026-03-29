"""Core invoice data models with Pydantic validation."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class VendorType(str, Enum):
    UBEREATS = "ubereats"
    DOORDASH = "doordash"
    GRUBHUB = "grubhub"
    IFOOD = "ifood"
    RAPPI = "rappi"


class LineItem(BaseModel):
    description: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=100)
    unit_price: Decimal = Field(ge=Decimal("0"))
    modifiers: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class InvoiceData(BaseModel):
    invoice_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    vendor_type: VendorType
    restaurant_name: str = Field(min_length=1)
    restaurant_address: str
    restaurant_phone: str
    restaurant_ein: str
    restaurant_rating: float = Field(ge=0, le=5)
    cuisine_type: str
    order_date: datetime
    customer_name: str = Field(min_length=1)
    customer_phone: str
    line_items: list[LineItem] = Field(min_length=1)
    subtotal: Decimal = Field(ge=Decimal("0"))
    delivery_fee: Decimal = Field(ge=Decimal("0"))
    service_fee: Decimal = Field(ge=Decimal("0"))
    tip_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    discount_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    total_amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @computed_field
    @property
    def formatted_order_date(self) -> str:
        return self.order_date.strftime("%B %d, %Y at %I:%M %p")

    @computed_field
    @property
    def items_count(self) -> int:
        return sum(item.quantity for item in self.line_items)
