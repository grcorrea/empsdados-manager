#!/usr/bin/env python3

"""
Teste rápido da aplicação AWS SSO Manager
"""

try:
    import flet as ft
    print("✓ Flet importado com sucesso")
except ImportError as e:
    print(f"✗ Erro ao importar Flet: {e}")
    exit(1)

try:
    import boto3
    print("✓ Boto3 importado com sucesso")
except ImportError as e:
    print(f"✗ Erro ao importar Boto3: {e}")
    exit(1)

try:
    from src.components.main_window import MainWindow
    from src.config.settings import Settings
    print("✓ Componentes locais importados com sucesso")
except ImportError as e:
    print(f"✗ Erro ao importar componentes: {e}")
    exit(1)

def test_main(page: ft.Page):
    page.title = "Teste AWS SSO Manager"
    page.window_width = 1200
    page.window_height = 800

    try:
        settings = Settings()
        page.theme_mode = settings.get_theme_mode()

        main_window = MainWindow(page, settings)
        page.add(main_window)

        print("✓ Interface carregada com sucesso!")

    except Exception as e:
        print(f"✗ Erro ao carregar interface: {e}")
        page.add(ft.Text(f"Erro: {str(e)}", color=ft.colors.RED))

if __name__ == "__main__":
    print("Iniciando teste da aplicação...")
    ft.app(target=test_main, view=ft.AppView.FLET_APP)