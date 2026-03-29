"""Partner brand configuration data model."""

from pydantic import BaseModel, Field


class PartnerBrand(BaseModel):
    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: str = Field(min_length=1)
    logo_path: str
    tagline: str = Field(default="")

    @property
    def css_variables(self) -> dict[str, str]:
        return {
            "--primary-color": self.primary_color,
            "--secondary-color": self.secondary_color,
            "--accent-color": self.accent_color,
            "--font-family": self.font_family,
        }

    @property
    def css_string(self) -> str:
        return "; ".join(f"{k}: {v}" for k, v in self.css_variables.items())
