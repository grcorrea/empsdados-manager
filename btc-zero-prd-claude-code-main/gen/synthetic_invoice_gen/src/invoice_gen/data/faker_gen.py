"""Faker-based data generator for realistic invoice content."""

import random
from datetime import datetime, timedelta
from decimal import Decimal

from faker import Faker

from invoice_gen.data.catalogs import get_menu_items, get_random_modifiers, get_restaurant_names
from invoice_gen.schemas.delivery import DeliveryInfo
from invoice_gen.schemas.invoice import InvoiceData, LineItem, VendorType
from invoice_gen.schemas.payment import PaymentInfo, PaymentMethod


class InvoiceDataGenerator:
    CUISINE_TYPES = ["American", "Italian", "Mexican", "Asian", "Fast Food"]
    VENDOR_PREFIXES = {
        VendorType.UBEREATS: "UE",
        VendorType.DOORDASH: "DD",
        VendorType.GRUBHUB: "GH",
        VendorType.IFOOD: "IF",
        VendorType.RAPPI: "RP",
    }

    def __init__(
        self,
        locale: str = "en_US",
        seed: int | None = None,
        failure_rate: float = 0.0,
    ):
        self.fake = Faker(locale)
        self.seed = seed
        self.failure_rate = max(0.0, min(1.0, failure_rate))
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)

    def generate(self, vendor_type: VendorType) -> InvoiceData:
        cuisine_type = random.choice(self.CUISINE_TYPES)
        line_items = self._generate_line_items(cuisine_type, random.randint(2, 8))
        subtotal = sum(item.amount for item in line_items)
        delivery_fee = Decimal(str(round(random.uniform(2.99, 8.99), 2)))
        service_fee = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        tip_amount = (subtotal * Decimal(str(random.choice([0, 0.10, 0.15, 0.18, 0.20])))).quantize(
            Decimal("0.01")
        )
        discount_amount = Decimal("0")
        if random.random() < 0.2:
            discount_amount = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))

        total_amount = subtotal + delivery_fee + service_fee + tip_amount - discount_amount

        subtotal, total_amount = self._maybe_inject_failure(subtotal, total_amount)

        return InvoiceData(
            invoice_id=self._generate_invoice_id(vendor_type),
            order_id=self.fake.uuid4()[:8].upper(),
            vendor_type=vendor_type,
            restaurant_name=random.choice(get_restaurant_names(cuisine_type)),
            restaurant_address=self.fake.address().replace("\n", ", "),
            restaurant_phone=self.fake.phone_number(),
            restaurant_ein=self.fake.ein(),
            restaurant_rating=round(random.uniform(3.5, 5.0), 1),
            cuisine_type=cuisine_type,
            order_date=self.fake.date_time_between(start_date="-30d", end_date="now"),
            customer_name=self.fake.name(),
            customer_phone=self.fake.phone_number(),
            line_items=line_items,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            service_fee=service_fee,
            tip_amount=tip_amount,
            discount_amount=discount_amount,
            total_amount=total_amount,
            currency="USD",
        )

    def generate_delivery_info(self) -> DeliveryInfo:
        order_time = self.fake.date_time_between(start_date="-1d", end_date="now")
        estimated = order_time + timedelta(minutes=random.randint(30, 60))
        actual = estimated + timedelta(minutes=random.randint(-10, 15))

        return DeliveryInfo(
            customer_name=self.fake.name(),
            customer_address=self.fake.address().replace("\n", ", "),
            customer_phone=self.fake.phone_number(),
            delivery_instructions=random.choice(
                ["", "Leave at door", "Ring doorbell", "Call upon arrival", "Gate code: 1234"]
            ),
            driver_name=self.fake.first_name(),
            estimated_delivery=estimated,
            actual_delivery=actual,
            distance_miles=round(random.uniform(0.5, 10.0), 1),
        )

    def generate_payment_info(self, order_date: datetime) -> PaymentInfo:
        return PaymentInfo(
            method=random.choice(list(PaymentMethod)),
            card_last_four=self.fake.credit_card_number()[-4:],
            card_brand=random.choice(["Visa", "Mastercard", "Amex", "Discover"]),
            transaction_id=self.fake.uuid4()[:12].upper(),
            payment_date=order_date,
            is_successful=True,
        )

    def _generate_invoice_id(self, vendor_type: VendorType) -> str:
        prefix = self.VENDOR_PREFIXES[vendor_type]
        suffix = self.fake.hexify(text="^^^^^^").upper()
        return f"INV-{prefix}-{suffix}"

    def _generate_line_items(self, cuisine_type: str, count: int) -> list[LineItem]:
        menu_items = get_menu_items(cuisine_type)
        modifiers = get_random_modifiers()
        items = []

        selected_items = random.sample(menu_items, min(count, len(menu_items)))
        for item in selected_items:
            quantity = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
            item_modifiers = []
            if random.random() < 0.3:
                item_modifiers = random.sample(modifiers, random.randint(1, 2))

            items.append(
                LineItem(
                    description=str(item["name"]),
                    quantity=quantity,
                    unit_price=Decimal(str(item["price"])),
                    modifiers=item_modifiers,
                )
            )

        return items

    def _maybe_inject_failure(
        self,
        subtotal: Decimal,
        total_amount: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Inject calculation errors to test extraction validation.

        Creates invoices with intentionally wrong totals that will be
        rendered into TIFF images. When extracted, these should trigger
        Pydantic business rule validation failures.
        """
        if self.failure_rate <= 0 or random.random() > self.failure_rate:
            return subtotal, total_amount

        corruption_type = random.choice([
            "total_mismatch",
            "subtotal_mismatch",
            "both_corrupted",
        ])

        if corruption_type == "total_mismatch":
            offset = Decimal(str(round(random.uniform(10, 50), 2)))
            total_amount = total_amount + offset

        elif corruption_type == "subtotal_mismatch":
            offset = Decimal(str(round(random.uniform(5, 25), 2)))
            subtotal = subtotal + offset

        elif corruption_type == "both_corrupted":
            subtotal = subtotal + Decimal(str(round(random.uniform(3, 15), 2)))
            total_amount = total_amount - Decimal(str(round(random.uniform(5, 20), 2)))

        return subtotal, total_amount
