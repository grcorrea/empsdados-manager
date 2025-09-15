import json
import os
from typing import Dict, Any
import flet as ft


class Settings:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

        return self._get_default_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        return {
            "theme": {
                "mode": "light",
                "primary_color": "#1976d2",
                "accent_color": "#03dac6"
            },
            "aws": {
                "default_region": "us-east-1",
                "profile": "default"
            },
            "ui": {
                "window_width": 1200,
                "window_height": 800,
                "sidebar_width": 250
            }
        }

    def _save_settings(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    def get_theme_mode(self) -> ft.ThemeMode:
        theme_mode = self.settings.get("theme", {}).get("mode", "light")
        return ft.ThemeMode.DARK if theme_mode == "dark" else ft.ThemeMode.LIGHT

    def is_dark_mode(self) -> bool:
        return self.settings.get("theme", {}).get("mode", "light") == "dark"

    def set_theme_mode(self, is_dark: bool):
        if "theme" not in self.settings:
            self.settings["theme"] = {}

        self.settings["theme"]["mode"] = "dark" if is_dark else "light"
        self._save_settings()

    def get_primary_color(self) -> str:
        return self.settings.get("theme", {}).get("primary_color", "#1976d2")

    def set_primary_color(self, color: str):
        if "theme" not in self.settings:
            self.settings["theme"] = {}

        self.settings["theme"]["primary_color"] = color
        self._save_settings()

    def get_aws_region(self) -> str:
        return self.settings.get("aws", {}).get("default_region", "us-east-1")

    def set_aws_region(self, region: str):
        if "aws" not in self.settings:
            self.settings["aws"] = {}

        self.settings["aws"]["default_region"] = region
        self._save_settings()

    def get_aws_profile(self) -> str:
        return self.settings.get("aws", {}).get("profile", "default")

    def set_aws_profile(self, profile: str):
        if "aws" not in self.settings:
            self.settings["aws"] = {}

        self.settings["aws"]["profile"] = profile
        self._save_settings()

    def get_window_size(self) -> tuple:
        ui_settings = self.settings.get("ui", {})
        width = ui_settings.get("window_width", 1200)
        height = ui_settings.get("window_height", 800)
        return width, height

    def set_window_size(self, width: int, height: int):
        if "ui" not in self.settings:
            self.settings["ui"] = {}

        self.settings["ui"]["window_width"] = width
        self.settings["ui"]["window_height"] = height
        self._save_settings()

    def get_sidebar_width(self) -> int:
        return self.settings.get("ui", {}).get("sidebar_width", 250)

    def set_sidebar_width(self, width: int):
        if "ui" not in self.settings:
            self.settings["ui"] = {}

        self.settings["ui"]["sidebar_width"] = width
        self._save_settings()