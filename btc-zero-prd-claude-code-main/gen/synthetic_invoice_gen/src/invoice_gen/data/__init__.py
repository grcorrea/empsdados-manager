"""Data generation module for synthetic invoice content."""

from invoice_gen.data.catalogs import get_menu_items, get_restaurant_names
from invoice_gen.data.faker_gen import InvoiceDataGenerator

__all__ = ["InvoiceDataGenerator", "get_restaurant_names", "get_menu_items"]
