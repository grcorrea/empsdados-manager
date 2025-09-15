import flet as ft
import json
from datetime import datetime
from ...services.stepfunctions_service import StepFunctionsService


class StepFunctionsTab(ft.Container):
    def __init__(self):
        super().__init__()
        self.sf_service = StepFunctionsService()

        self.expand = True
        self.padding = 20

        # Dropdown para state machines
        self.state_machine_dropdown = ft.Dropdown(
            label="State Machine",
            width=300,
            options=[],
            on_change=self._on_state_machine_selected
        )

        # Filtro de status para execuções
        self.status_filter_dropdown = ft.Dropdown(
            label="Filtro de Status",
            width=150,
            options=[
                ft.dropdown.Option("", "Todos"),
                ft.dropdown.Option("RUNNING", "Em Execução"),
                ft.dropdown.Option("SUCCEEDED", "Sucesso"),
                ft.dropdown.Option("FAILED", "Falha"),
                ft.dropdown.Option("TIMED_OUT", "Timeout"),
                ft.dropdown.Option("ABORTED", "Abortado")
            ],
            value="",
            on_change=self._on_status_filter_changed
        )

        # Tabela de execuções
        self.executions_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nome", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Status", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Início", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Fim", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Ações", size=12, weight=ft.FontWeight.W_500)),
            ],
            rows=[],
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4
        )

        # Campos para nova execução
        self.execution_name_field = ft.TextField(
            label="Nome da Execução (opcional)",
            width=250
        )

        self.execution_input_field = ft.TextField(
            label="Input JSON",
            multiline=True,
            min_lines=3,
            max_lines=5,
            width=400,
            value='{}'
        )

        # Botões de ação
        self.load_machines_btn = ft.Container(
            content=ft.Text("Carregar State Machines", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            on_click=self._load_state_machines,
            hover_color=ft.colors.SURFACE_VARIANT
        )

        self.load_executions_btn = ft.Container(
            content=ft.Text("Carregar Execuções", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.PRIMARY),
            border_radius=4,
            bgcolor=ft.colors.PRIMARY_CONTAINER,
            on_click=self._load_executions
        )

        self.start_execution_btn = ft.Container(
            content=ft.Text("Iniciar Execução", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.SECONDARY),
            border_radius=4,
            bgcolor=ft.colors.SECONDARY_CONTAINER,
            on_click=self._start_execution
        )

        # Área de resultados
        self.result_text = ft.Container(
            content=ft.Text(
                "Carregue as state machines...",
                size=12,
                color=ft.colors.ON_SURFACE_VARIANT,
                selectable=True
            ),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            min_height=120
        )

        self.content = ft.Column(
            controls=[
                ft.Text("Step Functions Management", size=16, weight=ft.FontWeight.W_500),
                ft.Container(height=10),

                # Controles de seleção
                ft.Row([
                    self.state_machine_dropdown,
                    self.load_machines_btn
                ], spacing=10),

                ft.Row([
                    self.status_filter_dropdown,
                    self.load_executions_btn
                ], spacing=10),

                ft.Container(height=15),

                # Tabela de execuções
                ft.Text("Execuções:", size=12, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=self.executions_table,
                    height=250,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=4
                ),

                ft.Container(height=15),

                # Seção de nova execução
                ft.Text("Nova Execução:", size=12, weight=ft.FontWeight.W_500),
                ft.Row([
                    self.execution_name_field,
                    self.start_execution_btn
                ], spacing=10),
                self.execution_input_field,

                ft.Container(height=15),

                # Resultados
                ft.Text("Resultados:", size=12, weight=ft.FontWeight.W_500),
                self.result_text
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

        # Carregar dados iniciais
        self._load_state_machines(None)

    def _load_state_machines(self, e):
        try:
            self._show_result("Carregando state machines...", is_error=False)

            result = self.sf_service.list_state_machines()

            if result.get("success"):
                machines = result.get("data", [])
                self.state_machine_dropdown.options = [
                    ft.dropdown.Option(machine['stateMachineArn'], machine['name'])
                    for machine in machines
                ]

                if machines:
                    self.state_machine_dropdown.value = machines[0]['stateMachineArn']
                    self._on_state_machine_selected(None)

                self._show_result(f"✓ {len(machines)} state machines carregadas", is_error=False)
            else:
                self._show_result(f"Erro ao carregar state machines: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _on_state_machine_selected(self, e):
        self._load_executions(None)

    def _on_status_filter_changed(self, e):
        if self.state_machine_dropdown.value:
            self._load_executions(None)

    def _load_executions(self, e):
        if not self.state_machine_dropdown.value:
            self._show_result("Selecione uma state machine primeiro", is_error=True)
            return

        try:
            state_machine_arn = self.state_machine_dropdown.value
            status_filter = self.status_filter_dropdown.value if self.status_filter_dropdown.value else None

            self._show_result(f"Carregando execuções...", is_error=False)

            result = self.sf_service.list_executions(state_machine_arn, status_filter)

            if result.get("success"):
                executions = result.get("data", [])

                # Limpar tabela
                self.executions_table.rows.clear()

                # Adicionar execuções à tabela
                for execution in executions:
                    # Determinar cor do status
                    status_colors = {
                        'RUNNING': ft.colors.BLUE,
                        'SUCCEEDED': ft.colors.GREEN,
                        'FAILED': ft.colors.RED,
                        'TIMED_OUT': ft.colors.ORANGE,
                        'ABORTED': ft.colors.GREY
                    }
                    status_color = status_colors.get(execution['status'], ft.colors.ON_SURFACE)

                    # Botões de ação
                    detail_btn = ft.IconButton(
                        icon=ft.icons.INFO,
                        icon_size=16,
                        tooltip="Detalhes",
                        on_click=lambda e, arn=execution['executionArn']: self._show_execution_details(arn)
                    )

                    stop_btn = ft.IconButton(
                        icon=ft.icons.STOP,
                        icon_size=16,
                        icon_color=ft.colors.ERROR,
                        tooltip="Parar Execução",
                        on_click=lambda e, arn=execution['executionArn']: self._stop_execution(arn),
                        disabled=execution['status'] != 'RUNNING'
                    )

                    self.executions_table.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(execution['name'], size=11)),
                                ft.DataCell(ft.Text(execution['status'], size=11, color=status_color)),
                                ft.DataCell(ft.Text(execution['startDate'], size=11)),
                                ft.DataCell(ft.Text(execution['stopDate'], size=11)),
                                ft.DataCell(ft.Row([detail_btn, stop_btn], spacing=2))
                            ]
                        )
                    )

                self._show_result(f"✓ {len(executions)} execuções carregadas", is_error=False)
            else:
                self._show_result(f"Erro ao carregar execuções: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _start_execution(self, e):
        if not self.state_machine_dropdown.value:
            self._show_result("Selecione uma state machine primeiro", is_error=True)
            return

        try:
            state_machine_arn = self.state_machine_dropdown.value
            execution_name = self.execution_name_field.value or None
            input_data = self.execution_input_field.value or "{}"

            # Validar JSON
            try:
                json.loads(input_data)
            except json.JSONDecodeError as e:
                self._show_result(f"JSON inválido: {str(e)}", is_error=True)
                return

            # Gerar nome único se não fornecido
            if not execution_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                execution_name = f"execution_{timestamp}"

            self._show_result(f"Iniciando execução '{execution_name}'...", is_error=False)

            result = self.sf_service.start_execution(state_machine_arn, execution_name, input_data)

            if result.get("success"):
                self._show_result(result.get("message"), is_error=False)
                self._load_executions(None)  # Atualizar lista

                # Limpar campos
                self.execution_name_field.value = ""
                self.execution_input_field.value = "{}"
                self.update()
            else:
                self._show_result(f"Erro ao iniciar execução: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _stop_execution(self, execution_arn: str):
        try:
            self._show_result("Parando execução...", is_error=False)

            result = self.sf_service.stop_execution(execution_arn)

            if result.get("success"):
                self._show_result(result.get("message"), is_error=False)
                self._load_executions(None)  # Atualizar lista
            else:
                self._show_result(f"Erro ao parar execução: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _show_execution_details(self, execution_arn: str):
        try:
            result = self.sf_service.describe_execution(execution_arn)

            if result.get("success"):
                details = result.get("data", {})
                details_text = json.dumps(details, indent=2, ensure_ascii=False)
                self._show_result(f"Detalhes da execução:\n\n{details_text}", is_error=False)
            else:
                self._show_result(f"Erro ao obter detalhes: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _show_result(self, message: str, is_error: bool = False):
        color = ft.colors.ERROR if is_error else ft.colors.ON_SURFACE
        self.result_text.content = ft.Text(
            message,
            size=12,
            color=color,
            selectable=True
        )
        self.result_text.update()