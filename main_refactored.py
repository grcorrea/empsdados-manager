import flet as ft
import threading
import time
from pathlib import Path

# Imports dos módulos refatorados
from utils.config_manager import ConfigManager
from utils.cache_manager import CacheManager
from utils.helpers import WindowsHelper, SystemHelper
from services.aws_auth import AWSAuthService
from services.s3_service import S3Service
from services.glue_service import GlueService
from services.stepfunctions_service import StepFunctionsService
from services.eventbridge_service import EventBridgeService
from services.athena_service import AthenaService
from ui.components import UIComponents


class AWSManagerApp:
    def __init__(self, page: ft.Page):
        self.page = page

        # Inicializar managers primeiro
        self.config_manager = ConfigManager()
        self.cache_manager = CacheManager()

        # Configurar página após managers
        self.setup_page()

        # Inicializar serviços
        self.auth_service = AWSAuthService(self.config_manager)
        self.s3_service = S3Service(self.auth_service, self.config_manager)
        self.glue_service = GlueService(self.auth_service, self.cache_manager)
        self.stepfunctions_service = StepFunctionsService(self.auth_service, self.cache_manager)
        self.eventbridge_service = EventBridgeService(self.auth_service, self.cache_manager)
        self.athena_service = AthenaService(self.auth_service, self.cache_manager)

        # Estados da aplicação
        self.current_section = "Login"
        self.expanded_menus = {"Monitoring": False}
        self.export_folder = Path.home() / "Downloads"

        # Dados em cache
        self.glue_jobs_data = []
        self.step_functions_data = []
        self.tables_data = []
        self.eventbridge_rules_data = []

        # Configurar FilePicker
        self.folder_picker = ft.FilePicker(on_result=self.on_folder_selected)
        self.page.overlay.append(self.folder_picker)

        # Configurar ambiente e interface
        SystemHelper.setup_proxy_environment()  # Define variáveis de ambiente do proxy
        self.setup_layout()
        # self.check_initial_login()  # Não tentar conectar automaticamente no startup

    def setup_page(self):
        """Configura página principal"""
        self.page.title = "AWS EmpsDados Manager"
        self.page.window_width = int(self.config_manager.get('UI', 'window_width', '1200'))
        self.page.window_height = int(self.config_manager.get('UI', 'window_height', '800'))
        self.page.window_min_width = 800
        self.page.window_min_height = 600
        self.page.theme_mode = self.config_manager.get('UI', 'theme_mode', 'system')
        self.page.padding = 0
        self.page.spacing = 0

    def setup_layout(self):
        """Configura layout principal com sidebar"""
        # Criar sidebar
        self.sidebar = self.create_sidebar()

        # Criar área de conteúdo
        self.content_area = ft.Container(
            content=self.create_login_content(),
            expand=True,
            padding=20
        )

        # Layout principal
        main_layout = ft.Row([
            self.sidebar,
            ft.VerticalDivider(width=1),
            self.content_area
        ], spacing=0, expand=True)

        self.page.add(main_layout)

    def create_sidebar(self):
        """Cria sidebar de navegação"""
        menu_items = [
            # Login
            UIComponents.create_sidebar_item(
                ft.Icons.LOGIN, "Login AWS",
                lambda e: self.navigate_to("Login"),
                self.current_section == "Login"
            ),

            # S3
            UIComponents.create_sidebar_item(
                ft.Icons.CLOUD, "Sincronização S3",
                lambda e: self.navigate_to("S3"),
                self.current_section == "S3"
            ),

            # Monitoring (menu expansível)
            UIComponents.create_expandable_menu(
                "Monitoring", ft.Icons.MONITOR, [
                    UIComponents.create_sidebar_item(
                        ft.Icons.WORK, "Glue Jobs",
                        lambda e: self.navigate_to("Monitoring Glue"),
                        self.current_section == "Monitoring Glue"
                    ),
                    UIComponents.create_sidebar_item(
                        ft.Icons.ACCOUNT_TREE, "Step Functions",
                        lambda e: self.navigate_to("Monitoring STF"),
                        self.current_section == "Monitoring STF"
                    ),
                    UIComponents.create_sidebar_item(
                        ft.Icons.TABLE_VIEW, "Tables",
                        lambda e: self.navigate_to("Monitoring Tables"),
                        self.current_section == "Monitoring Tables"
                    ),
                    UIComponents.create_sidebar_item(
                        ft.Icons.EVENT, "EventBridge",
                        lambda e: self.navigate_to("EventBridge"),
                        self.current_section == "EventBridge"
                    )
                ],
                self.expanded_menus.get("Monitoring", False),
                lambda e: self.toggle_menu("Monitoring")
            ),

            # Relatórios (menu expansível)
            UIComponents.create_expandable_menu(
                "Relatórios", ft.Icons.ANALYTICS, [
                    UIComponents.create_sidebar_item(
                        ft.Icons.QUERY_STATS, "Custos Athena",
                        lambda e: self.navigate_to("Report Athena"),
                        self.current_section == "Report Athena"
                    ),
                    UIComponents.create_sidebar_item(
                        ft.Icons.WORK_OUTLINE, "Custos Glue",
                        lambda e: self.navigate_to("Report Glue"),
                        self.current_section == "Report Glue"
                    ),
                    UIComponents.create_sidebar_item(
                        ft.Icons.CALCULATE, "Simulador Custos",
                        lambda e: self.navigate_to("Cost Simulator"),
                        self.current_section == "Cost Simulator"
                    )
                ]
            )
        ]

        return ft.Container(
            content=ft.Column(
                controls=menu_items,
                spacing=5,
                scroll=ft.ScrollMode.AUTO
            ),
            width=250,
            bgcolor=ft.Colors.BLUE_800,
            padding=15
        )

    def navigate_to(self, section):
        """Navega para uma seção específica"""
        self.current_section = section
        self.update_content_area()
        self.update_sidebar()

    def toggle_menu(self, menu_id):
        """Alterna expansão de um menu"""
        self.expanded_menus[menu_id] = not self.expanded_menus.get(menu_id, False)
        self.update_sidebar()

    def update_sidebar(self):
        """Atualiza sidebar com estado atual"""
        self.sidebar.content = self.create_sidebar().content
        self.page.update()

    def update_content_area(self):
        """Atualiza área de conteúdo baseada na seção atual"""
        content_map = {
            "Login": self.create_login_content,
            "S3": self.create_s3_content,
            "Monitoring Glue": self.create_glue_monitoring_content,
            "Monitoring STF": self.create_stepfunctions_monitoring_content,
            "Monitoring Tables": self.create_tables_monitoring_content,
            "EventBridge": self.create_eventbridge_content,
            "Report Athena": self.create_athena_report_content,
            "Report Glue": self.create_glue_report_content,
            "Cost Simulator": self.create_cost_simulator_content
        }

        content_creator = content_map.get(self.current_section, self.create_login_content)
        self.content_area.content = content_creator()
        self.page.update()

    def create_login_content(self):
        """Cria conteúdo da tab de login"""
        # Status de autenticação
        auth_status = self.auth_service.get_status_info()

        if auth_status['authenticated']:
            status_text = f"Conectado como: {auth_status['profile']} (Conta: {auth_status['account_id']})"
            status_color = ft.Colors.GREEN
        else:
            status_text = "Não conectado"
            status_color = ft.Colors.RED

        # Carregar perfis SSO
        profiles = self.auth_service.load_sso_profiles()

        profile_dropdown = ft.Dropdown(
            label="Selecione o perfil AWS SSO",
            options=[ft.dropdown.Option(p['name']) for p in profiles],
            width=400
        )

        login_button = UIComponents.create_action_button(
            "Fazer Login", ft.Icons.LOGIN,
            lambda e: self.perform_login(profile_dropdown.value),
            ft.Colors.GREEN
        )

        logout_button = UIComponents.create_action_button(
            "Fazer Logout", ft.Icons.LOGOUT,
            lambda e: self.perform_logout(),
            ft.Colors.RED
        )

        return ft.Column([
            UIComponents.create_tab_header("Login AWS SSO", ft.Icons.LOGIN),
            UIComponents.create_status_container(status_text, status_color),
            ft.Divider(),
            UIComponents.create_form_field("Perfil AWS", profile_dropdown, required=True),
            ft.Row([login_button, logout_button], spacing=10),
        ], spacing=20)

    def create_s3_content(self):
        """Cria conteúdo da tab S3"""
        return ft.Column([
            UIComponents.create_tab_header("Sincronização S3", ft.Icons.CLOUD),
            ft.Text("Funcionalidade de sincronização S3 será implementada aqui."),
        ], spacing=20)

    def create_glue_monitoring_content(self):
        """Cria conteúdo do monitoramento Glue"""
        # Botões de ação
        refresh_button = UIComponents.create_action_button(
            "Atualizar", ft.Icons.REFRESH,
            lambda e: self.refresh_glue_jobs()
        )

        export_button = UIComponents.create_action_button(
            "Exportar Excel", ft.Icons.FILE_DOWNLOAD,
            lambda e: self.export_glue_jobs()
        )

        # Filtros
        filter_text = ft.TextField(
            label="Filtrar jobs...",
            width=300,
            on_change=lambda e: self.filter_glue_jobs()
        )

        # Tabela (será populada dinamicamente)
        jobs_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nome", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Última Execução", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Duração", weight=ft.FontWeight.BOLD))
            ],
            rows=[]
        )

        return ft.Column([
            UIComponents.create_tab_header("Monitoramento Glue Jobs", ft.Icons.WORK),
            UIComponents.create_filter_row(filter_text, refresh_button, [export_button]),
            ft.Container(
                content=jobs_table,
                expand=True,
                padding=10,
                border=ft.border.all(1, ft.Colors.OUTLINE),
                border_radius=8
            )
        ], spacing=20, expand=True)

    def create_stepfunctions_monitoring_content(self):
        """Cria conteúdo do monitoramento Step Functions"""
        return ft.Column([
            UIComponents.create_tab_header("Monitoramento Step Functions", ft.Icons.ACCOUNT_TREE),
            ft.Text("Funcionalidade de monitoramento Step Functions será implementada aqui."),
        ], spacing=20)

    def create_tables_monitoring_content(self):
        """Cria conteúdo do monitoramento de tabelas"""
        return ft.Column([
            UIComponents.create_tab_header("Monitoramento Tabelas", ft.Icons.TABLE_VIEW),
            ft.Text("Funcionalidade de monitoramento de tabelas será implementada aqui."),
        ], spacing=20)

    def create_eventbridge_content(self):
        """Cria conteúdo do EventBridge"""
        return ft.Column([
            UIComponents.create_tab_header("EventBridge Rules", ft.Icons.EVENT),
            ft.Text("Funcionalidade de gerenciamento EventBridge será implementada aqui."),
        ], spacing=20)

    def create_athena_report_content(self):
        """Cria conteúdo dos relatórios Athena"""
        return ft.Column([
            UIComponents.create_tab_header("Relatórios de Custos Athena", ft.Icons.QUERY_STATS),
            ft.Text("Funcionalidade de relatórios Athena será implementada aqui."),
        ], spacing=20)

    def create_glue_report_content(self):
        """Cria conteúdo dos relatórios Glue"""
        return ft.Column([
            UIComponents.create_tab_header("Relatórios de Custos Glue", ft.Icons.WORK_OUTLINE),
            ft.Text("Funcionalidade de relatórios Glue será implementada aqui."),
        ], spacing=20)

    def create_cost_simulator_content(self):
        """Cria conteúdo do simulador de custos"""
        return ft.Column([
            UIComponents.create_tab_header("Simulador de Custos", ft.Icons.CALCULATE),
            ft.Text("Funcionalidade de simulação de custos será implementada aqui."),
        ], spacing=20)

    def check_initial_login(self):
        """Verifica login inicial (com tratamento de erro de conectividade)"""
        try:
            self.auth_service.check_login_status()
        except Exception as e:
            print(f"Aviso: Não foi possível verificar status AWS inicial: {e}")
            print("App funcionará em modo offline. Conecte-se manualmente na aba Login.")

    def perform_login(self, profile_name):
        """Executa login com perfil selecionado"""
        if not profile_name:
            print("Selecione um perfil antes de fazer login")
            return

        def login_callback(success, message):
            print(f"Login result: {success} - {message}")
            if success:
                self.update_content_area()  # Atualizar interface

        self.auth_service.login_with_profile(profile_name, login_callback)

    def perform_logout(self):
        """Executa logout"""
        def logout_callback(success, message):
            print(f"Logout result: {success} - {message}")
            self.update_content_area()  # Atualizar interface

        self.auth_service.logout(logout_callback)

    def refresh_glue_jobs(self):
        """Atualiza jobs Glue"""
        def fetch_in_background():
            try:
                self.glue_jobs_data = self.glue_service.fetch_glue_jobs(use_cache=False)
                # Atualizar UI na thread principal
                self.page.run_task(self.update_glue_jobs_table)
            except Exception as e:
                print(f"Erro ao buscar jobs Glue: {e}")

        threading.Thread(target=fetch_in_background, daemon=True).start()

    def update_glue_jobs_table(self):
        """Atualiza tabela de jobs Glue"""
        # Esta função seria implementada para atualizar a tabela com os dados
        print(f"Atualizando tabela com {len(self.glue_jobs_data)} jobs")

    def filter_glue_jobs(self):
        """Filtra jobs Glue"""
        # Implementar filtro dos jobs
        pass

    def export_glue_jobs(self):
        """Exporta jobs Glue para Excel"""
        if not self.glue_jobs_data:
            print("Nenhum job para exportar")
            return

        success, message = UIComponents.export_to_excel(
            self.glue_jobs_data,
            "glue_jobs",
            self.export_folder,
            "jobs Glue"
        )
        print(message)

    def on_folder_selected(self, e: ft.FilePickerResultEvent):
        """Callback quando pasta é selecionada"""
        if e.path:
            self.export_folder = Path(e.path)
            print(f"Pasta para export selecionada: {self.export_folder}")

    def select_export_folder(self):
        """Abre seletor de pasta"""
        self.folder_picker.get_directory_path(
            dialog_title="Escolha a pasta para salvar arquivos"
        )


def main(page: ft.Page):
    """Função principal da aplicação"""
    app = AWSManagerApp(page)


if __name__ == "__main__":
    print("Iniciando AWS EmpsDados Manager Refatorado...")

    # Minimizar janelas existentes
    WindowsHelper.minimize_all_windows()

    # Aguardar um pouco e trazer app para frente
    def delayed_bring_to_front():
        time.sleep(2)
        WindowsHelper.bring_app_to_front()

    threading.Thread(target=delayed_bring_to_front, daemon=True).start()

    # Iniciar aplicação Flet
    ft.app(target=main, view=ft.AppView.FLET_APP, port=8080)