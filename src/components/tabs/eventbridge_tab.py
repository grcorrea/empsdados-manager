import flet as ft
import json
from ...services.eventbridge_service import EventBridgeService


class EventBridgeTab(ft.Container):
    def __init__(self):
        super().__init__()
        self.eventbridge_service = EventBridgeService()

        self.expand = True
        self.padding = 20

        # Dropdown para event buses
        self.event_bus_dropdown = ft.Dropdown(
            label="Event Bus",
            width=250,
            options=[],
            value="default",
            on_change=self._on_event_bus_selected
        )

        # Dropdown para rules
        self.rule_dropdown = ft.Dropdown(
            label="Regras",
            width=250,
            options=[],
            on_change=self._on_rule_selected
        )

        # Tabela de regras
        self.rules_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nome", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Estado", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Descrição", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Ações", size=12, weight=ft.FontWeight.W_500)),
            ],
            rows=[],
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4
        )

        # Seção de teste de evento
        self.event_source_field = ft.TextField(
            label="Source",
            width=200,
            value="custom.application"
        )

        self.event_detail_type_field = ft.TextField(
            label="Detail Type",
            width=200,
            value="Test Event"
        )

        self.event_detail_field = ft.TextField(
            label="Detail (JSON)",
            multiline=True,
            min_lines=3,
            max_lines=5,
            width=400,
            value='{"message": "Test event from AWS Manager"}'
        )

        # Botões de ação
        self.load_buses_btn = ft.Container(
            content=ft.Text("Carregar Event Buses", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            on_click=self._load_event_buses,
            hover_color=ft.colors.SURFACE_VARIANT
        )

        self.load_rules_btn = ft.Container(
            content=ft.Text("Carregar Regras", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.PRIMARY),
            border_radius=4,
            bgcolor=ft.colors.PRIMARY_CONTAINER,
            on_click=self._load_rules
        )

        self.send_event_btn = ft.Container(
            content=ft.Text("Enviar Evento", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.SECONDARY),
            border_radius=4,
            bgcolor=ft.colors.SECONDARY_CONTAINER,
            on_click=self._send_test_event
        )

        # Área de resultados
        self.result_text = ft.Container(
            content=ft.Text(
                "Carregue os event buses e regras...",
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
                ft.Text("EventBridge Management", size=16, weight=ft.FontWeight.W_500),
                ft.Container(height=10),

                # Controles de seleção
                ft.Row([
                    self.event_bus_dropdown,
                    self.load_buses_btn,
                    self.load_rules_btn
                ], spacing=10),

                ft.Container(height=15),

                # Tabela de regras
                ft.Text("Regras do Event Bus:", size=12, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=self.rules_table,
                    height=250,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=4
                ),

                ft.Container(height=15),

                # Seção de teste de evento
                ft.Text("Teste de Evento:", size=12, weight=ft.FontWeight.W_500),
                ft.Row([
                    self.event_source_field,
                    self.event_detail_type_field
                ], spacing=10),
                self.event_detail_field,
                ft.Row([self.send_event_btn], spacing=10),

                ft.Container(height=15),

                # Resultados
                ft.Text("Resultados:", size=12, weight=ft.FontWeight.W_500),
                self.result_text
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

        # Carregar dados iniciais
        self._load_event_buses(None)

    def _load_event_buses(self, e):
        try:
            self._show_result("Carregando event buses...", is_error=False)

            result = self.eventbridge_service.list_event_buses()

            if result.get("success"):
                buses = result.get("data", [])
                self.event_bus_dropdown.options = [
                    ft.dropdown.Option(bus['Name'], bus['Name'])
                    for bus in buses
                ]

                # Sempre incluir o default se não estiver na lista
                if not any(opt.key == "default" for opt in self.event_bus_dropdown.options):
                    self.event_bus_dropdown.options.insert(0, ft.dropdown.Option("default", "default"))

                self.event_bus_dropdown.value = "default"
                self._show_result(f"✓ {len(buses)} event buses carregados", is_error=False)

                # Carregar regras automaticamente
                self._load_rules(None)
            else:
                self._show_result(f"Erro ao carregar event buses: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _on_event_bus_selected(self, e):
        self._load_rules(None)

    def _load_rules(self, e):
        if not self.event_bus_dropdown.value:
            self._show_result("Selecione um event bus primeiro", is_error=True)
            return

        try:
            event_bus_name = self.event_bus_dropdown.value
            self._show_result(f"Carregando regras do event bus {event_bus_name}...", is_error=False)

            result = self.eventbridge_service.list_rules(event_bus_name)

            if result.get("success"):
                rules = result.get("data", [])

                # Limpar tabela
                self.rules_table.rows.clear()

                # Popular dropdown de regras
                self.rule_dropdown.options = [
                    ft.dropdown.Option(rule['Name'], rule['Name'])
                    for rule in rules
                ]

                # Adicionar regras à tabela
                for rule in rules:
                    enable_btn = ft.IconButton(
                        icon=ft.icons.PLAY_ARROW,
                        icon_size=16,
                        icon_color=ft.colors.PRIMARY,
                        tooltip="Habilitar",
                        on_click=lambda e, name=rule['Name']: self._enable_rule(name)
                    )

                    disable_btn = ft.IconButton(
                        icon=ft.icons.PAUSE,
                        icon_size=16,
                        icon_color=ft.colors.ERROR,
                        tooltip="Desabilitar",
                        on_click=lambda e, name=rule['Name']: self._disable_rule(name)
                    )

                    info_btn = ft.IconButton(
                        icon=ft.icons.INFO,
                        icon_size=16,
                        tooltip="Detalhes",
                        on_click=lambda e, name=rule['Name']: self._show_rule_details(name)
                    )

                    state_color = ft.colors.PRIMARY if rule['State'] == 'ENABLED' else ft.colors.ERROR

                    self.rules_table.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(rule['Name'], size=11)),
                                ft.DataCell(ft.Text(rule['State'], size=11, color=state_color)),
                                ft.DataCell(ft.Text(rule['Description'][:50] + "..." if len(rule['Description']) > 50 else rule['Description'], size=11)),
                                ft.DataCell(ft.Row([enable_btn, disable_btn, info_btn], spacing=2))
                            ]
                        )
                    )

                self._show_result(f"✓ {len(rules)} regras carregadas", is_error=False)
            else:
                self._show_result(f"Erro ao carregar regras: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _on_rule_selected(self, e):
        # Pode ser usado para mostrar detalhes da regra selecionada
        pass

    def _enable_rule(self, rule_name: str):
        try:
            event_bus_name = self.event_bus_dropdown.value
            result = self.eventbridge_service.enable_rule(rule_name, event_bus_name)

            if result.get("success"):
                self._show_result(result.get("message"), is_error=False)
                self._load_rules(None)  # Atualizar lista
            else:
                self._show_result(f"Erro ao habilitar regra: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _disable_rule(self, rule_name: str):
        try:
            event_bus_name = self.event_bus_dropdown.value
            result = self.eventbridge_service.disable_rule(rule_name, event_bus_name)

            if result.get("success"):
                self._show_result(result.get("message"), is_error=False)
                self._load_rules(None)  # Atualizar lista
            else:
                self._show_result(f"Erro ao desabilitar regra: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _show_rule_details(self, rule_name: str):
        try:
            event_bus_name = self.event_bus_dropdown.value
            result = self.eventbridge_service.describe_rule(rule_name, event_bus_name)

            if result.get("success"):
                details = result.get("data", {})
                details_text = json.dumps(details, indent=2, ensure_ascii=False)
                self._show_result(f"Detalhes da regra '{rule_name}':\n\n{details_text}", is_error=False)
            else:
                self._show_result(f"Erro ao obter detalhes: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _send_test_event(self, e):
        try:
            source = self.event_source_field.value
            detail_type = self.event_detail_type_field.value
            detail_text = self.event_detail_field.value
            event_bus_name = self.event_bus_dropdown.value

            if not all([source, detail_type, detail_text]):
                self._show_result("Preencha todos os campos do evento", is_error=True)
                return

            # Validar JSON
            try:
                detail = json.loads(detail_text)
            except json.JSONDecodeError as e:
                self._show_result(f"JSON inválido no campo Detail: {str(e)}", is_error=True)
                return

            self._show_result(f"Enviando evento para {event_bus_name}...", is_error=False)

            result = self.eventbridge_service.put_events(source, detail_type, detail, event_bus_name)

            if result.get("success"):
                self._show_result(result.get("message"), is_error=False)
            else:
                self._show_result(f"Erro ao enviar evento: {result.get('error')}", is_error=True)

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