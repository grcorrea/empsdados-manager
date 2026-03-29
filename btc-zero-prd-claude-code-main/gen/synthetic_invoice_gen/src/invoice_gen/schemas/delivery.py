"""Delivery information data model."""

from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class DeliveryInfo(BaseModel):
    customer_name: str = Field(min_length=1)
    customer_address: str = Field(min_length=1)
    customer_phone: str
    delivery_instructions: str = Field(default="")
    driver_name: str = Field(min_length=1)
    estimated_delivery: datetime
    actual_delivery: datetime | None = None
    distance_miles: float = Field(ge=0, le=50)

    @computed_field
    @property
    def formatted_estimated(self) -> str:
        return self.estimated_delivery.strftime("%I:%M %p")

    @computed_field
    @property
    def formatted_actual(self) -> str | None:
        if self.actual_delivery:
            return self.actual_delivery.strftime("%I:%M %p")
        return None

    @computed_field
    @property
    def formatted_distance(self) -> str:
        return f"{self.distance_miles:.1f} mi"
