"""Payment information data model."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"


class PaymentInfo(BaseModel):
    method: PaymentMethod
    card_last_four: str = Field(pattern=r"^\d{4}$")
    card_brand: str = Field(default="Visa")
    transaction_id: str = Field(min_length=1)
    payment_date: datetime
    is_successful: bool = Field(default=True)

    @computed_field
    @property
    def masked_card(self) -> str:
        return f"**** **** **** {self.card_last_four}"

    @computed_field
    @property
    def formatted_method(self) -> str:
        method_display = {
            PaymentMethod.CREDIT_CARD: "Credit Card",
            PaymentMethod.DEBIT_CARD: "Debit Card",
            PaymentMethod.PAYPAL: "PayPal",
            PaymentMethod.APPLE_PAY: "Apple Pay",
            PaymentMethod.GOOGLE_PAY: "Google Pay",
        }
        return method_display.get(self.method, self.method.value)

    @computed_field
    @property
    def formatted_payment_date(self) -> str:
        return self.payment_date.strftime("%B %d, %Y")
