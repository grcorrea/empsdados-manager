import flet as ft


class GlueTab(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.padding = 20

        self.content = ft.Column(
            controls=[
                ft.Text("Glue Management", size=16, weight=ft.FontWeight.W_500),
                ft.Container(height=10),
                ft.Text("Em desenvolvimento...", size=14, color=ft.colors.ON_SURFACE_VARIANT)
            ],
            spacing=5
        )