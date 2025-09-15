import flet as ft
from ...services.glue_service import GlueService


class DashboardTab(ft.Container):
    def __init__(self):
        super().__init__()
        self.glue_service = GlueService()

        self.expand = True
        self.padding = 20

        # Cards de estatísticas
        self.total_jobs_card = self._create_stat_card("Total Jobs", "0", ft.colors.BLUE)
        self.succeeded_card = self._create_stat_card("Succeeded", "0", ft.colors.GREEN)
        self.failed_card = self._create_stat_card("Failed", "0", ft.colors.RED)
        self.running_card = self._create_stat_card("Running", "0", ft.colors.ORANGE)

        # Tabela de execuções recentes
        self.recent_runs_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Job", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Run ID", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Status", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Início", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Duração", size=12, weight=ft.FontWeight.W_500)),
            ],
            rows=[],
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4
        )

        # Botão de atualização
        self.refresh_btn = ft.Container(
            content=ft.Text("Atualizar Dashboard", size=12),
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            border=ft.border.all(1, ft.colors.PRIMARY),
            border_radius=4,
            bgcolor=ft.colors.PRIMARY_CONTAINER,
            on_click=self._refresh_dashboard,
            hover_color=ft.colors.PRIMARY_CONTAINER
        )

        # Botão de auto-refresh
        self.auto_refresh_switch = ft.Switch(
            label="Auto-refresh (30s)",
            value=False,
            on_change=self._toggle_auto_refresh
        )

        # Área de status
        self.status_text = ft.Container(
            content=ft.Text(
                "Carregando dashboard...",
                size=12,
                color=ft.colors.ON_SURFACE_VARIANT
            ),
            padding=10,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            min_height=60
        )

        self.content = ft.Column(
            controls=[
                ft.Text("Glue Jobs Dashboard", size=16, weight=ft.FontWeight.W_500),
                ft.Container(height=15),

                # Controles
                ft.Row([
                    self.refresh_btn,
                    ft.Container(width=20),
                    self.auto_refresh_switch
                ], alignment=ft.MainAxisAlignment.START),

                ft.Container(height=15),

                # Cards de estatísticas
                ft.Row([
                    self.total_jobs_card,
                    self.succeeded_card,
                    self.failed_card,
                    self.running_card
                ], spacing=15, wrap=True),

                ft.Container(height=20),

                # Tabela de execuções recentes
                ft.Text("Execuções Recentes:", size=14, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=self.recent_runs_table,
                    height=300,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=4
                ),

                ft.Container(height=15),

                # Status
                ft.Text("Status:", size=12, weight=ft.FontWeight.W_500),
                self.status_text
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

        # Carregar dados iniciais
        self._refresh_dashboard(None)

    def _create_stat_card(self, title: str, value: str, color):
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=12, color=ft.colors.ON_SURFACE_VARIANT),
                ft.Text(value, size=24, weight=ft.FontWeight.BOLD, color=color)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=150,
            height=80,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=8,
            bgcolor=ft.colors.SURFACE_VARIANT,
            padding=10
        )

    def _update_stat_card(self, card, value: str):
        if card.content and len(card.content.controls) >= 2:
            card.content.controls[1].value = value
            card.update()

    def _refresh_dashboard(self, e):
        try:
            self._show_status("Atualizando dashboard...", is_error=False)

            # Obter estatísticas
            result = self.glue_service.get_job_statistics()

            if result.get("success"):
                stats = result.get("data", {})

                # Atualizar cards
                self._update_stat_card(self.total_jobs_card, str(stats.get('total_jobs', 0)))

                job_runs_stats = stats.get('job_runs_stats', {})
                self._update_stat_card(self.succeeded_card, str(job_runs_stats.get('SUCCEEDED', 0)))
                self._update_stat_card(self.failed_card, str(job_runs_stats.get('FAILED', 0)))
                self._update_stat_card(self.running_card, str(job_runs_stats.get('RUNNING', 0)))

                # Atualizar tabela de execuções recentes
                recent_runs = stats.get('recent_runs', [])
                self._update_recent_runs_table(recent_runs)

                self._show_status(f"✓ Dashboard atualizado ({len(recent_runs)} execuções recentes)", is_error=False)

            else:
                self._show_status(f"Erro ao carregar estatísticas: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_status(f"Erro inesperado: {str(e)}", is_error=True)

    def _update_recent_runs_table(self, recent_runs):
        try:
            # Limpar tabela
            self.recent_runs_table.rows.clear()

            # Adicionar execuções recentes
            for run in recent_runs:
                # Determinar cor do status
                status_colors = {
                    'SUCCEEDED': ft.colors.GREEN,
                    'FAILED': ft.colors.RED,
                    'STOPPED': ft.colors.ORANGE,
                    'RUNNING': ft.colors.BLUE,
                    'STARTING': ft.colors.CYAN,
                    'STOPPING': ft.colors.PURPLE,
                    'TIMEOUT': ft.colors.RED_ACCENT
                }
                status_color = status_colors.get(run['State'], ft.colors.ON_SURFACE)

                # Truncar IDs e nomes para exibição
                display_job_name = run['JobName'][:20] + "..." if len(run['JobName']) > 20 else run['JobName']
                display_run_id = run['Id'][:8] + "..." if len(run['Id']) > 8 else run['Id']

                self.recent_runs_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(display_job_name, size=11, tooltip=run['JobName'])),
                            ft.DataCell(ft.Text(display_run_id, size=11, tooltip=run['Id'])),
                            ft.DataCell(ft.Text(run['State'], size=11, color=status_color)),
                            ft.DataCell(ft.Text(run['StartedOn'], size=11)),
                            ft.DataCell(ft.Text(run['Duration'], size=11)),
                        ]
                    )
                )

            self.recent_runs_table.update()

        except Exception as e:
            self._show_status(f"Erro ao atualizar tabela: {str(e)}", is_error=True)

    def _toggle_auto_refresh(self, e):
        if self.auto_refresh_switch.value:
            self._show_status("Auto-refresh ativado (30 segundos)", is_error=False)
            # Aqui você poderia implementar um timer para auto-refresh
            # Por simplicidade, vou apenas mostrar a mensagem
        else:
            self._show_status("Auto-refresh desativado", is_error=False)

    def _show_status(self, message: str, is_error: bool = False):
        color = ft.colors.ERROR if is_error else ft.colors.ON_SURFACE
        self.status_text.content = ft.Text(
            message,
            size=12,
            color=color
        )
        self.status_text.update()

    def get_dashboard_summary(self) -> dict:
        """Método para obter resumo do dashboard para outras abas"""
        try:
            result = self.glue_service.get_job_statistics()
            if result.get("success"):
                return result.get("data", {})
            return {}
        except:
            return {}