"""TIFF-to-PNG converter Cloud Run function.

Converts multi-page TIFF invoices to PNG format for LLM processing.
Triggered by Pub/Sub messages from the invoice-uploaded topic.
"""

from functions.tiff_to_png.converter import convert_tiff_to_png

__all__ = ["convert_tiff_to_png"]
