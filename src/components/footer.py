import flet as ft
from ..services.sso_service import SSOService


class Footer(ft.Container):
    def __init__(self):
        super().__init__()
        self.sso_service = SSOService()

        self.profile_text = ft.Text(
            "Profile: Não logado",
            size=12,
            color=ft.colors.ON_SURFACE_VARIANT
        )

        self.account_text = ft.Text(
            "Account: -",
            size=12,
            color=ft.colors.ON_SURFACE_VARIANT
        )

        self.region_text = ft.Text(
            "Region: -",
            size=12,
            color=ft.colors.ON_SURFACE_VARIANT
        )

        self.height = 40
        self.bgcolor = ft.colors.SURFACE_VARIANT
        self.border = ft.border.only(top=ft.border.BorderSide(1, ft.colors.OUTLINE))
        self.padding = ft.padding.symmetric(horizontal=20, vertical=8)

        self.content = ft.Row(
            controls=[
                self.profile_text,
                ft.VerticalDivider(width=20),
                self.account_text,
                ft.VerticalDivider(width=20),
                self.region_text
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=10
        )

        self.update_status()

    def update_status(self):
        try:
            status = self.sso_service.get_current_session_info()

            if status.get("logged_in", False):
                self.profile_text.value = f"Profile: {status.get('profile', 'default')}"
                self.account_text.value = f"Account: {status.get('account_id', 'N/A')}"
                self.region_text.value = f"Region: {status.get('region', 'N/A')}"
                self.profile_text.color = ft.colors.PRIMARY
            else:
                self.profile_text.value = "Profile: Não logado"
                self.account_text.value = "Account: -"
                self.region_text.value = "Region: -"
                self.profile_text.color = ft.colors.ERROR

        except Exception as e:
            self.profile_text.value = f"Profile: Erro - {str(e)}"
            self.profile_text.color = ft.colors.ERROR

        self.update()

    def refresh(self):
        self.update_status()