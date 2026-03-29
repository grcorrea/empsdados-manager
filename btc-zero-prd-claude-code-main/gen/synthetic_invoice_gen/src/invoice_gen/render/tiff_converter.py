"""Pillow + pdf2image TIFF converter with LZW compression."""

from pathlib import Path

from pdf2image import convert_from_bytes
from PIL import Image


class TiffConverter:
    def __init__(self, dpi: int = 200, compression: str = "tiff_lzw"):
        self.dpi = dpi
        self.compression = compression

    def pdf_to_tiff(self, pdf_bytes: bytes, output_path: Path) -> Path:
        images = convert_from_bytes(pdf_bytes, dpi=self.dpi)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if len(images) == 1:
            images[0].save(str(output_path), "TIFF", compression=self.compression)
        else:
            images[0].save(
                str(output_path),
                "TIFF",
                compression=self.compression,
                save_all=True,
                append_images=images[1:],
            )

        return output_path

    def html_to_tiff(
        self, html_content: str, output_path: Path, base_url: str | None = None
    ) -> Path:
        from invoice_gen.render.pdf_generator import PDFGenerator

        pdf_gen = PDFGenerator(base_url=base_url)
        pdf_bytes = pdf_gen.generate(html_content)
        return self.pdf_to_tiff(pdf_bytes, output_path)

    def images_to_multipage_tiff(self, images: list[Image.Image], output_path: Path) -> Path:
        if not images:
            raise ValueError("At least one image is required")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if len(images) == 1:
            images[0].save(str(output_path), "TIFF", compression=self.compression)
        else:
            images[0].save(
                str(output_path),
                "TIFF",
                compression=self.compression,
                save_all=True,
                append_images=images[1:],
            )

        return output_path
