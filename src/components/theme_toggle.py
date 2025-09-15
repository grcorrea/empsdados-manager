import flet as ft


class ThemeToggle(ft.Container):
    def __init__(self, page: ft.Page, settings):
        super().__init__()
        self.page = page
        self.settings = settings

        self.theme_button = ft.TextButton(
            text="Dark" if not self.settings.is_dark_mode() else "Light",
            on_click=self.toggle_theme,
            style=ft.ButtonStyle(
                color=ft.colors.ON_SURFACE,
                overlay_color=ft.colors.SURFACE_VARIANT
            )
        )

        self.content = self.theme_button

    def toggle_theme(self, e):
        is_dark = not self.settings.is_dark_mode()
        self.settings.set_theme_mode(is_dark)

        self.theme_button.text = "Light" if is_dark else "Dark"

        if is_dark:
            self.page.theme_mode = ft.ThemeMode.DARK
        else:
            self.page.theme_mode = ft.ThemeMode.LIGHT

        self.page.update()