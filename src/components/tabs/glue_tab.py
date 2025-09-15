import flet as ft
import json
from ...services.glue_service import GlueService


class GlueTab(ft.Container):
    def __init__(self):
        super().__init__()
        self.glue_service = GlueService()

        self.expand = True
        self.padding = 20

        # Dropdown para seleção de job
        self.job_dropdown = ft.Dropdown(
            label="Selecione um Job",
            width=300,
            options=[],
            on_change=self._on_job_selected
        )

        # Filtro de status para job runs
        self.status_filter_dropdown = ft.Dropdown(
            label="Filtro de Status",
            width=150,
            options=[
                ft.dropdown.Option("", "Todos"),
                ft.dropdown.Option("SUCCEEDED", "Sucesso"),
                ft.dropdown.Option("FAILED", "Falha"),
                ft.dropdown.Option("STOPPED", "Parado"),
                ft.dropdown.Option("RUNNING", "Executando"),
                ft.dropdown.Option("STARTING", "Iniciando"),
                ft.dropdown.Option("STOPPING", "Parando"),
                ft.dropdown.Option("TIMEOUT", "Timeout")
            ],
            value="",
            on_change=self._on_status_filter_changed
        )

        # Abas internas para Jobs e Crawlers
        self.internal_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(
                    text="Jobs",
                    content=self._create_jobs_content()
                ),
                ft.Tab(
                    text="Crawlers",
                    content=self._create_crawlers_content()
                )
            ]
        )

        self.content = ft.Column(
            controls=[
                ft.Text("AWS Glue Management", size=16, weight=ft.FontWeight.W_500),
                ft.Container(height=10),
                self.internal_tabs
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

        # Carregar dados iniciais
        self._load_jobs(None)

    def _create_jobs_content(self):
        # Tabela de job runs
        self.job_runs_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Run ID", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Status", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Início", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Duração", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Ações", size=12, weight=ft.FontWeight.W_500)),
            ],
            rows=[],
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4
        )

        # Campos para argumentos do job
        self.job_arguments_field = ft.TextField(
            label="Argumentos do Job (JSON)",
            multiline=True,
            min_lines=3,
            max_lines=5,
            width=400,
            value='{}',
            helper_text="Exemplo: {\"--job-language\": \"python\", \"--my-param\": \"value\"}"
        )

        # Botões de ação para jobs
        self.load_jobs_btn = ft.Container(
            content=ft.Text("Carregar Jobs", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            on_click=self._load_jobs,
            hover_color=ft.colors.SURFACE_VARIANT
        )

        self.load_runs_btn = ft.Container(
            content=ft.Text("Carregar Execuções", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.PRIMARY),
            border_radius=4,
            bgcolor=ft.colors.PRIMARY_CONTAINER,
            on_click=self._load_job_runs
        )

        self.start_job_btn = ft.Container(
            content=ft.Text("Iniciar Job", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.SECONDARY),
            border_radius=4,
            bgcolor=ft.colors.SECONDARY_CONTAINER,
            on_click=self._start_job
        )

        self.job_details_btn = ft.Container(
            content=ft.Text("Detalhes do Job", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.TERTIARY),
            border_radius=4,
            bgcolor=ft.colors.TERTIARY_CONTAINER,
            on_click=self._show_job_details
        )

        # Área de resultados para jobs
        self.jobs_result_text = ft.Container(
            content=ft.Text(
                "Carregue os jobs para começar...",
                size=12,
                color=ft.colors.ON_SURFACE_VARIANT,
                selectable=True
            ),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            min_height=120
        )

        return ft.Column(
            controls=[
                # Controles de seleção
                ft.Row([
                    self.job_dropdown,
                    self.load_jobs_btn,
                    self.job_details_btn
                ], spacing=10),

                ft.Row([
                    self.status_filter_dropdown,
                    self.load_runs_btn
                ], spacing=10),

                ft.Container(height=10),

                # Tabela de execuções
                ft.Text("Execuções do Job:", size=12, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=self.job_runs_table,
                    height=250,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=4
                ),

                ft.Container(height=10),

                # Seção para iniciar job
                ft.Text("Iniciar Nova Execução:", size=12, weight=ft.FontWeight.W_500),
                self.job_arguments_field,
                ft.Row([self.start_job_btn], spacing=10),

                ft.Container(height=10),

                # Resultados
                ft.Text("Resultados:", size=12, weight=ft.FontWeight.W_500),
                self.jobs_result_text
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

    def _create_crawlers_content(self):
        # Tabela de crawlers
        self.crawlers_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nome", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Estado", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Database", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Última Atualização", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Ações", size=12, weight=ft.FontWeight.W_500)),
            ],
            rows=[],
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4
        )

        # Botões para crawlers
        self.load_crawlers_btn = ft.Container(
            content=ft.Text("Carregar Crawlers", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            on_click=self._load_crawlers,
            hover_color=ft.colors.SURFACE_VARIANT
        )

        # Área de resultados para crawlers
        self.crawlers_result_text = ft.Container(
            content=ft.Text(
                "Carregue os crawlers...",
                size=12,
                color=ft.colors.ON_SURFACE_VARIANT,
                selectable=True
            ),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            min_height=120
        )

        return ft.Column(
            controls=[
                # Controles
                ft.Row([self.load_crawlers_btn], spacing=10),

                ft.Container(height=10),

                # Tabela de crawlers
                ft.Text("Crawlers:", size=12, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=self.crawlers_table,
                    height=350,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=4
                ),

                ft.Container(height=10),

                # Resultados
                ft.Text("Resultados:", size=12, weight=ft.FontWeight.W_500),
                self.crawlers_result_text
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

    def _load_jobs(self, e):
        try:
            self._show_jobs_result("Carregando jobs...", is_error=False)

            result = self.glue_service.list_jobs()

            if result.get("success"):
                jobs = result.get("data", [])
                self.job_dropdown.options = [
                    ft.dropdown.Option(job['Name'], job['Name'])
                    for job in jobs
                ]

                if jobs:
                    self.job_dropdown.value = jobs[0]['Name']
                    self._on_job_selected(None)

                self._show_jobs_result(f"✓ {len(jobs)} jobs carregados", is_error=False)
            else:
                self._show_jobs_result(f"Erro ao carregar jobs: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_jobs_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _on_job_selected(self, e):
        self._load_job_runs(None)

    def _on_status_filter_changed(self, e):
        if self.job_dropdown.value:
            self._load_job_runs(None)

    def _load_job_runs(self, e):
        if not self.job_dropdown.value:
            self._show_jobs_result("Selecione um job primeiro", is_error=True)
            return

        try:
            job_name = self.job_dropdown.value
            self._show_jobs_result(f"Carregando execuções do job {job_name}...", is_error=False)

            result = self.glue_service.list_job_runs(job_name)

            if result.get("success"):
                job_runs = result.get("data", [])

                # Filtrar por status se selecionado
                status_filter = self.status_filter_dropdown.value
                if status_filter:
                    job_runs = [run for run in job_runs if run['JobRunState'] == status_filter]

                # Limpar tabela
                self.job_runs_table.rows.clear()

                # Adicionar execuções à tabela
                for run in job_runs:
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
                    status_color = status_colors.get(run['JobRunState'], ft.colors.ON_SURFACE)

                    # Botões de ação
                    detail_btn = ft.IconButton(
                        icon=ft.icons.INFO,
                        icon_size=16,
                        tooltip="Detalhes",
                        on_click=lambda e, job_name=job_name, run_id=run['Id']: self._show_run_details(job_name, run_id)
                    )

                    stop_btn = ft.IconButton(
                        icon=ft.icons.STOP,
                        icon_size=16,
                        icon_color=ft.colors.ERROR,
                        tooltip="Parar Execução",
                        on_click=lambda e, job_name=job_name, run_id=run['Id']: self._stop_job_run(job_name, run_id),
                        disabled=run['JobRunState'] not in ['RUNNING', 'STARTING']
                    )

                    # Truncar ID para exibição
                    display_id = run['Id'][:8] + "..." if len(run['Id']) > 8 else run['Id']

                    self.job_runs_table.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(display_id, size=11, tooltip=run['Id'])),
                                ft.DataCell(ft.Text(run['JobRunState'], size=11, color=status_color)),
                                ft.DataCell(ft.Text(run['StartedOn'], size=11)),
                                ft.DataCell(ft.Text(run['Duration'], size=11)),
                                ft.DataCell(ft.Row([detail_btn, stop_btn], spacing=2))
                            ]
                        )
                    )

                self._show_jobs_result(f"✓ {len(job_runs)} execuções carregadas", is_error=False)
            else:
                self._show_jobs_result(f"Erro ao carregar execuções: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_jobs_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _start_job(self, e):
        if not self.job_dropdown.value:
            self._show_jobs_result("Selecione um job primeiro", is_error=True)
            return

        try:
            job_name = self.job_dropdown.value
            arguments_text = self.job_arguments_field.value or "{}"

            # Validar JSON
            try:
                arguments = json.loads(arguments_text)
            except json.JSONDecodeError as e:
                self._show_jobs_result(f"JSON inválido nos argumentos: {str(e)}", is_error=True)
                return

            self._show_jobs_result(f"Iniciando job '{job_name}'...", is_error=False)

            result = self.glue_service.start_job_run(job_name, arguments if arguments else None)

            if result.get("success"):
                self._show_jobs_result(result.get("message"), is_error=False)
                self._load_job_runs(None)  # Atualizar lista
            else:
                self._show_jobs_result(f"Erro ao iniciar job: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_jobs_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _stop_job_run(self, job_name: str, job_run_id: str):
        try:
            self._show_jobs_result(f"Parando execução {job_run_id[:8]}...", is_error=False)

            result = self.glue_service.stop_job_run(job_name, job_run_id)

            if result.get("success"):
                self._show_jobs_result(result.get("message"), is_error=False)
                self._load_job_runs(None)  # Atualizar lista
            else:
                self._show_jobs_result(f"Erro ao parar execução: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_jobs_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _show_job_details(self, e):
        if not self.job_dropdown.value:
            self._show_jobs_result("Selecione um job primeiro", is_error=True)
            return

        try:
            job_name = self.job_dropdown.value
            result = self.glue_service.get_job_details(job_name)

            if result.get("success"):
                details = result.get("data", {})
                details_text = json.dumps(details, indent=2, ensure_ascii=False)
                self._show_jobs_result(f"Detalhes do job '{job_name}':\n\n{details_text}", is_error=False)
            else:
                self._show_jobs_result(f"Erro ao obter detalhes: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_jobs_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _show_run_details(self, job_name: str, job_run_id: str):
        try:
            result = self.glue_service.get_job_run_details(job_name, job_run_id)

            if result.get("success"):
                details = result.get("data", {})
                details_text = json.dumps(details, indent=2, ensure_ascii=False)
                self._show_jobs_result(f"Detalhes da execução {job_run_id[:8]}:\n\n{details_text}", is_error=False)
            else:
                self._show_jobs_result(f"Erro ao obter detalhes: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_jobs_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _load_crawlers(self, e):
        try:
            self._show_crawlers_result("Carregando crawlers...", is_error=False)

            result = self.glue_service.list_crawlers()

            if result.get("success"):
                crawlers = result.get("data", [])

                # Limpar tabela
                self.crawlers_table.rows.clear()

                # Adicionar crawlers à tabela
                for crawler in crawlers:
                    # Determinar cor do estado
                    state_colors = {
                        'READY': ft.colors.GREEN,
                        'RUNNING': ft.colors.BLUE,
                        'STOPPING': ft.colors.ORANGE
                    }
                    state_color = state_colors.get(crawler['State'], ft.colors.ON_SURFACE)

                    # Botões de ação
                    start_btn = ft.IconButton(
                        icon=ft.icons.PLAY_ARROW,
                        icon_size=16,
                        icon_color=ft.colors.PRIMARY,
                        tooltip="Iniciar Crawler",
                        on_click=lambda e, name=crawler['Name']: self._start_crawler(name),
                        disabled=crawler['State'] == 'RUNNING'
                    )

                    stop_btn = ft.IconButton(
                        icon=ft.icons.STOP,
                        icon_size=16,
                        icon_color=ft.colors.ERROR,
                        tooltip="Parar Crawler",
                        on_click=lambda e, name=crawler['Name']: self._stop_crawler(name),
                        disabled=crawler['State'] != 'RUNNING'
                    )

                    self.crawlers_table.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(crawler['Name'], size=11)),
                                ft.DataCell(ft.Text(crawler['State'], size=11, color=state_color)),
                                ft.DataCell(ft.Text(crawler['DatabaseName'], size=11)),
                                ft.DataCell(ft.Text(crawler['LastUpdated'], size=11)),
                                ft.DataCell(ft.Row([start_btn, stop_btn], spacing=2))
                            ]
                        )
                    )

                self._show_crawlers_result(f"✓ {len(crawlers)} crawlers carregados", is_error=False)
            else:
                self._show_crawlers_result(f"Erro ao carregar crawlers: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_crawlers_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _start_crawler(self, crawler_name: str):
        try:
            self._show_crawlers_result(f"Iniciando crawler '{crawler_name}'...", is_error=False)

            result = self.glue_service.start_crawler(crawler_name)

            if result.get("success"):
                self._show_crawlers_result(result.get("message"), is_error=False)
                self._load_crawlers(None)  # Atualizar lista
            else:
                self._show_crawlers_result(f"Erro ao iniciar crawler: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_crawlers_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _stop_crawler(self, crawler_name: str):
        try:
            self._show_crawlers_result(f"Parando crawler '{crawler_name}'...", is_error=False)

            result = self.glue_service.stop_crawler(crawler_name)

            if result.get("success"):
                self._show_crawlers_result(result.get("message"), is_error=False)
                self._load_crawlers(None)  # Atualizar lista
            else:
                self._show_crawlers_result(f"Erro ao parar crawler: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_crawlers_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _show_jobs_result(self, message: str, is_error: bool = False):
        color = ft.colors.ERROR if is_error else ft.colors.ON_SURFACE
        self.jobs_result_text.content = ft.Text(
            message,
            size=12,
            color=color,
            selectable=True
        )
        self.jobs_result_text.update()

    def _show_crawlers_result(self, message: str, is_error: bool = False):
        color = ft.colors.ERROR if is_error else ft.colors.ON_SURFACE
        self.crawlers_result_text.content = ft.Text(
            message,
            size=12,
            color=color,
            selectable=True
        )
        self.crawlers_result_text.update()