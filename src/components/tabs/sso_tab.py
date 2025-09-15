import flet as ft
from ...services.sso_service import SSOService


class SSOTab(ft.Container):
    def __init__(self, footer):
        super().__init__()
        self.footer = footer
        self.sso_service = SSOService()

        self.expand = True
        self.padding = 20

        # Status atual
        self.status_text = ft.Text(
            "Verificando status...",
            size=14,
            color=ft.colors.ON_SURFACE_VARIANT
        )

        # Lista de profiles
        self.profiles_dropdown = ft.Dropdown(
            label="Selecione um Profile SSO",
            width=300,
            options=[],
            on_change=self._on_profile_selected
        )

        # Informações do profile selecionado
        self.profile_info = ft.Container(
            visible=False,
            content=ft.Column([]),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4
        )

        # Botões de ação
        self.login_button = ft.Container(
            content=ft.Text("Login SSO", size=12, color=ft.colors.ON_SURFACE),
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            border=ft.border.all(1, ft.colors.PRIMARY),
            border_radius=4,
            bgcolor=ft.colors.PRIMARY_CONTAINER,
            on_click=self._login_sso,
            visible=False
        )

        self.logout_button = ft.Container(
            content=ft.Text("Logout SSO", size=12, color=ft.colors.ON_SURFACE),
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            border=ft.border.all(1, ft.colors.ERROR),
            border_radius=4,
            bgcolor=ft.colors.ERROR_CONTAINER,
            on_click=self._logout_sso,
            visible=False
        )

        self.refresh_button = ft.Container(
            content=ft.Text("Atualizar Status", size=12, color=ft.colors.ON_SURFACE),
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            on_click=self._refresh_status,
            hover_color=ft.colors.SURFACE_VARIANT
        )

        # Área de resultados
        self.result_text = ft.Container(
            content=ft.Text(
                "Status e resultados aparecerão aqui...",
                size=12,
                color=ft.colors.ON_SURFACE_VARIANT,
                selectable=True
            ),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            min_height=150
        )

        self.content = ft.Column(
            controls=[
                ft.Text("AWS SSO Management", size=16, weight=ft.FontWeight.W_500),
                ft.Container(height=10),

                # Status atual
                ft.Row([
                    ft.Text("Status: ", size=12, weight=ft.FontWeight.W_500),
                    self.status_text
                ]),
                ft.Container(height=15),

                # Seleção de profile
                self.profiles_dropdown,
                ft.Container(height=10),
                self.profile_info,
                ft.Container(height=15),

                # Botões de ação
                ft.Row([
                    self.login_button,
                    self.logout_button,
                    self.refresh_button
                ], spacing=10),
                ft.Container(height=15),

                # Resultados
                ft.Text("Resultados:", size=12, weight=ft.FontWeight.W_500),
                self.result_text
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

        # Carregar dados iniciais
        self._load_initial_data()

    def _load_initial_data(self):
        self._refresh_status(None)
        self._load_profiles()

    def _load_profiles(self):
        try:
            profiles = self.sso_service.list_sso_profiles()
            self.profiles_dropdown.options = [
                ft.dropdown.Option(p['name'], f"{p['name']} ({p.get('sso_account_id', 'N/A')})")
                for p in profiles
            ]

            if profiles:
                self.profiles_dropdown.value = profiles[0]['name']
                self._on_profile_selected(None)

            self.update()

        except Exception as e:
            self._show_result(f"Erro ao carregar profiles: {str(e)}", is_error=True)

    def _on_profile_selected(self, e):
        if not self.profiles_dropdown.value:
            self.profile_info.visible = False
            self.login_button.visible = False
            self.update()
            return

        try:
            profiles = self.sso_service.list_sso_profiles()
            selected_profile = next((p for p in profiles if p['name'] == self.profiles_dropdown.value), None)

            if selected_profile:
                self.profile_info.content = ft.Column([
                    ft.Text(f"Account ID: {selected_profile.get('sso_account_id', 'N/A')}", size=11),
                    ft.Text(f"Role: {selected_profile.get('sso_role_name', 'N/A')}", size=11),
                    ft.Text(f"SSO Region: {selected_profile.get('sso_region', 'N/A')}", size=11),
                    ft.Text(f"Default Region: {selected_profile.get('region', 'N/A')}", size=11),
                    ft.Text(f"SSO URL: {selected_profile.get('sso_start_url', 'N/A')}", size=11)
                ])
                self.profile_info.visible = True
                self.login_button.visible = True

        except Exception as e:
            self._show_result(f"Erro ao carregar informações do profile: {str(e)}", is_error=True)

        self.update()

    def _login_sso(self, e):
        if not self.profiles_dropdown.value:
            self._show_result("Selecione um profile primeiro", is_error=True)
            return

        profile_name = self.profiles_dropdown.value
        self._show_result(f"Iniciando login SSO para {profile_name}...", is_error=False)

        try:
            result = self.sso_service.login_sso_profile(profile_name)

            if result.get("success"):
                self._show_result(result.get("message", "Login realizado com sucesso!"), is_error=False)
                self._refresh_status(None)
                self.footer.refresh()
            else:
                self._show_result(f"Erro no login: {result.get('error', 'Erro desconhecido')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado no login: {str(e)}", is_error=True)

    def _logout_sso(self, e):
        try:
            result = self.sso_service.logout_sso()

            if result.get("success"):
                self._show_result(result.get("message", "Logout realizado com sucesso!"), is_error=False)
                self._refresh_status(None)
                self.footer.refresh()
            else:
                self._show_result(f"Erro no logout: {result.get('error', 'Erro desconhecido')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado no logout: {str(e)}", is_error=True)

    def _refresh_status(self, e):
        try:
            session_info = self.sso_service.get_current_session_info()

            if session_info.get("logged_in"):
                self.status_text.value = f"Logado ({session_info.get('profile', 'default')})"
                self.status_text.color = ft.colors.PRIMARY
                self.logout_button.visible = True
            else:
                self.status_text.value = "Não logado"
                self.status_text.color = ft.colors.ERROR
                self.logout_button.visible = False

            if e:  # Se foi chamado por clique no botão
                self._show_result(f"Status atualizado: {self.status_text.value}", is_error=False)

            self.footer.refresh()
            self.update()

        except Exception as e:
            self.status_text.value = f"Erro: {str(e)}"
            self.status_text.color = ft.colors.ERROR
            self.update()

    def _show_result(self, message: str, is_error: bool = False):
        color = ft.colors.ERROR if is_error else ft.colors.ON_SURFACE
        self.result_text.content = ft.Text(
            message,
            size=12,
            color=color,
            selectable=True
        )
        self.result_text.update()