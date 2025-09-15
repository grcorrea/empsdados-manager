import flet as ft
from src.components.main_window import MainWindow
from src.config.settings import Settings


def main(page: ft.Page):
    page.title = "AWS SSO Manager"
    page.window_width = 1400
    page.window_height = 900
    page.window_min_width = 1000
    page.window_min_height = 700

    settings = Settings()
    page.theme_mode = settings.get_theme_mode()

    main_window = MainWindow(page, settings)
    page.add(main_window)


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)