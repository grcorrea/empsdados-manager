"""WeasyPrint PDF generator for HTML content."""

from pathlib import Path

from weasyprint import CSS, HTML


class PDFGenerator:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url

    def generate(self, html_content: str, output_path: Path | None = None) -> bytes:
        html = HTML(string=html_content, base_url=self.base_url)
        pdf_bytes = html.write_pdf()

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(pdf_bytes)

        return pdf_bytes

    def generate_with_css(
        self, html_content: str, css_content: str, output_path: Path | None = None
    ) -> bytes:
        html = HTML(string=html_content, base_url=self.base_url)
        css = CSS(string=css_content)
        pdf_bytes = html.write_pdf(stylesheets=[css])

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(pdf_bytes)

        return pdf_bytes
