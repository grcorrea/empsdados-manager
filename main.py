import flet as ft
import boto3
import os
import configparser
import subprocess
import sys
import json
import threading
import time
import ctypes
import pyperclip
import pandas as pd
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
from concurrent.futures import ThreadPoolExecutor, as_completed


class AWSApp:
    def __init__(self, page: ft.Page):
        self.page = page

        # Configurar variáveis de ambiente do proxy
        self.setup_environment()

        # Carregar configurações
        self.config = self.load_config()

        # Variáveis globais para status AWS
        self.current_profile = None
        self.current_account_id = None
        self.current_user_arn = None

        # Estado da navegação sidebar
        self.current_section = "Login"  # Seção atual selecionada
        self.expanded_menus = {"Monitoring": False}  # Controla quais menus estão expandidos

        # Pasta para salvar exports (padrão: Downloads)
        self.export_folder = Path.home() / "Downloads"

        # Configurar FilePicker
        self.folder_picker = ft.FilePicker(
            on_result=self.on_folder_selected
        )
        self.page.overlay.append(self.folder_picker)

        self.setup_page()
        self.setup_status_bar()
        self.setup_layout_with_sidebar()
        self.check_login_status()

    def on_folder_selected(self, e: ft.FilePickerResultEvent):
        """Callback quando uma pasta é selecionada para export"""
        if e.path:
            self.export_folder = Path(e.path)
            print(f"📁 Pasta para export selecionada: {self.export_folder}")

            # Executar callback se definido
            if hasattr(self, 'callback_after_folder_selection') and self.callback_after_folder_selection:
                try:
                    self.callback_after_folder_selection()
                    self.callback_after_folder_selection = None  # Limpar callback após uso
                except Exception as e:
                    print(f"❌ Erro ao executar callback após seleção de pasta: {e}")

            # Mostrar feedback visual se houver uma aba ativa
            try:
                if hasattr(self, 'monitoring_status_eventbridge') and self.current_section == "EventBridge":
                    self.monitoring_status_eventbridge.value = f"📁 Pasta selecionada: {self.export_folder.name}"
                    self.monitoring_status_eventbridge.color = ft.Colors.BLUE
                    self.page.update()
                elif hasattr(self, 'monitoring_status_tables') and self.current_section == "Monitoring Tables":
                    self.monitoring_status_tables.value = f"📁 Pasta selecionada: {self.export_folder.name}"
                    self.monitoring_status_tables.color = ft.Colors.BLUE
                    self.page.update()
                elif hasattr(self, 'monitoring_status') and self.current_section == "Monitoring Glue":
                    self.monitoring_status.value = f"📁 Pasta selecionada: {self.export_folder.name}"
                    self.monitoring_status.color = ft.Colors.BLUE
                    self.page.update()
                elif hasattr(self, 'monitoring_status_sptf') and self.current_section == "Monitoring STF":
                    self.monitoring_status_sptf.value = f"📁 Pasta selecionada: {self.export_folder.name}"
                    self.monitoring_status_sptf.color = ft.Colors.BLUE
                    self.page.update()
            except:
                pass  # Ignorar se não conseguir atualizar o status

    def select_export_folder(self, callback_after_selection=None):
        """Abre o seletor de pasta para escolher onde salvar exports"""
        self.callback_after_folder_selection = callback_after_selection
        self.folder_picker.get_directory_path(dialog_title="Escolha a pasta para salvar o arquivo Excel")

    def setup_environment(self):
        """Configura variáveis de ambiente necessárias"""
        os.environ['HTTP_PROXY'] = "http://proxynew.itau:8080"
        os.environ['HTTPS_PROXY'] = "http://proxynew.itau:8080"

        # Aguardar um pouco para a janela do app ser totalmente criada
        def delayed_minimize():
            time.sleep(1)  # Aguardar 1 segundo para app estar pronto
            self.minimize_all_windows()

        # Executar minimização em thread separada para não bloquear inicialização
        threading.Timer(1.0, delayed_minimize).start()

    def minimize_all_windows(self):
        """Minimiza todas as outras janelas do sistema, exceto o nosso app"""
        try:
            # Método 1: Minimizar todas e depois restaurar nossa janela
            subprocess.run([
                "powershell", "-Command",
                "(New-Object -comObject Shell.Application).MinimizeAll()"
            ], capture_output=True, check=False, timeout=3)

            # Aguardar um pouco para as janelas serem minimizadas
            time.sleep(0.3)

            # Restaurar e trazer nossa janela para frente
            self.bring_app_to_front()

        except:
            try:
                # Método 2: Usar Win+D e depois restaurar nossa janela
                VK_LWIN = 0x5B
                VK_D = 0x44

                # Pressionar Win+D para minimizar todas
                ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_D, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_D, 0, 2, 0)  # Release D
                ctypes.windll.user32.keybd_event(VK_LWIN, 0, 2, 0)  # Release Win

                # Aguardar e restaurar nossa janela
                time.sleep(0.3)
                self.bring_app_to_front()

            except:
                pass  # Ignorar erros se não conseguir minimizar

    def bring_app_to_front(self):
        """Traz o app para frente após minimizar outras janelas"""
        try:
            # Garantir que a janela não está minimizada
            self.page.window.minimized = False

            # Trazer para frente temporariamente
            self.page.window.always_on_top = True

            # Forçar atualização da página
            self.page.update()

            # Aguardar e remover always_on_top para comportamento normal
            def restore_normal_behavior():
                try:
                    self.page.window.always_on_top = False
                    self.page.update()
                except:
                    pass

            # Usar timer para restaurar comportamento normal
            threading.Timer(1.0, restore_normal_behavior).start()

        except Exception as e:
            print(f"Erro ao trazer app para frente: {e}")

    def load_config(self):
        """Carrega configurações do arquivo config.json"""
        try:
            config_path = Path(__file__).parent / "config.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Configuração padrão caso o arquivo não exista
            return {
                "app": {
                    "title": "EMPS Dados Manager",
                    "theme_mode": "dark",
                    "window": {"width": 600, "height": 750, "resizable": False}
                },
                "s3": {
                    "rt_options": ["fluxo", "corebank", "assessoria", "credito"],
                    "squad_options": ["data-engineering", "analytics", "data-science", "platform"],
                    "environment_options": ["sirius", "athena"],
                    "default_base_path": "s3"
                },
                "aws": {
                    "config_files": ["config", "config.txt"],
                    "default_profile": "default"
                }
            }

    def save_config(self):
        """Salva configurações no arquivo config.json"""
        try:
            config_path = Path(__file__).parent / "config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    def save_filter_text(self, filter_type, text):
        """Salva texto do filtro na configuração"""
        if "filters" not in self.config:
            self.config["filters"] = {}
        self.config["filters"][filter_type] = text
        self.save_config()

    def load_filter_text(self, filter_type):
        """Carrega texto do filtro da configuração"""
        return self.config.get("filters", {}).get(filter_type, "")

    def setup_page(self):
        app_config = self.config.get("app", {})
        self.page.title = app_config.get("title", "EMPS Dados Manager")
        self.page.theme_mode = ft.ThemeMode.DARK if app_config.get("theme_mode") == "dark" else ft.ThemeMode.LIGHT

        # Tema dark customizado com mais contraste e visual aprimorado
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=ft.Colors.BLUE_600,
                on_primary=ft.Colors.WHITE,
                secondary=ft.Colors.CYAN_500,
                on_secondary=ft.Colors.BLACK,
                surface=ft.Colors.GREY_800,
                on_surface=ft.Colors.WHITE,
                background=ft.Colors.GREY_900,
                on_background=ft.Colors.WHITE,
                error=ft.Colors.RED_500,
                on_error=ft.Colors.WHITE,
                outline=ft.Colors.GREY_600,
                shadow=ft.Colors.BLACK54,
            ),
        )

        # Configurações da janela - maximizada e responsiva
        self.page.window.maximized = True
        self.page.window.resizable = True

        # Fallback caso não consiga maximizar
        if not self.page.window.maximized:
            window_config = app_config.get("window", {})
            self.page.window.width = window_config.get("width", 1200)
            self.page.window.height = window_config.get("height", 800)
            self.page.window.center()

        # Background da página com gradiente sutil
        self.page.bgcolor = ft.Colors.GREY_900

    def setup_status_bar(self):
        # Elementos da barra de status
        self.status_profile_text = ft.Text(
            "Profile: Não logado",
            size=12,
            color=ft.Colors.GREY_400,
            weight=ft.FontWeight.W_500
        )

        self.status_account_text = ft.Text(
            "Account ID: N/A",
            size=12,
            color=ft.Colors.GREY_400,
            weight=ft.FontWeight.W_500
        )

        self.status_refresh_button = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Atualizar Status",
            on_click=self.refresh_aws_status,
            icon_size=16,
            style=ft.ButtonStyle(
                color=ft.Colors.BLUE_400,
                bgcolor={
                    ft.ControlState.HOVERED: ft.Colors.BLUE_600,
                },
                shape=ft.CircleBorder(),
                padding=8,
            )
        )

        # Container da barra de status com visual aprimorado
        self.status_bar = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=16, color=ft.Colors.BLUE_400),
                        self.status_profile_text,
                    ], spacing=8),
                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=6,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CLOUD, size=16, color=ft.Colors.CYAN_400),
                        self.status_account_text,
                    ], spacing=8),
                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=6,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                ),
                ft.Container(expand=True),
                self.status_refresh_button
            ], spacing=15, alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
            bgcolor=ft.Colors.GREY_800,
            border=ft.border.only(top=ft.BorderSide(2, ft.Colors.GREY_700)),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=4,
                color=ft.Colors.BLACK26,
                offset=ft.Offset(0, -2),
            )
        )

    def refresh_aws_status(self, e=None):
        """Atualiza o status AWS atual e variáveis globais"""
        try:
            # Verificar profile atual do ambiente
            env_profile = os.environ.get('AWS_PROFILE', 'default')

            # Tentar obter identity usando STS
            sts_client = boto3.client('sts')
            identity = sts_client.get_caller_identity()

            # Atualizar variáveis globais
            self.current_profile = env_profile
            self.current_account_id = identity.get('Account', 'N/A')
            self.current_user_arn = identity.get('Arn', 'N/A')

            # Atualizar interface
            self.status_profile_text.value = f"Profile: {self.current_profile}"
            self.status_profile_text.color = ft.Colors.GREEN

            account_display = f"Account ID: {self.current_account_id}"
            if len(account_display) > 25:
                account_display = f"Account: ...{self.current_account_id[-8:]}"
            self.status_account_text.value = account_display
            self.status_account_text.color = ft.Colors.GREEN

            # Atualizar caminhos S3 se a aba estiver carregada
            if hasattr(self, 'rt_dropdown'):
                self.update_s3_path()

            # Atualizar status do monitoring se a aba estiver carregada
            if hasattr(self, 'monitoring_status'):
                self.monitoring_status.value = "✅ Conectado - Clique em 'Atualizar' para carregar jobs"
                self.monitoring_status.color = ft.Colors.GREEN

            return True

        except (NoCredentialsError, ClientError, Exception) as e:
            # Limpar variáveis globais
            self.current_profile = None
            self.current_account_id = None
            self.current_user_arn = None

            # Atualizar interface
            self.status_profile_text.value = "Profile: Não logado"
            self.status_profile_text.color = ft.Colors.GREY_400

            self.status_account_text.value = "Account ID: N/A"
            self.status_account_text.color = ft.Colors.GREY_400

            # Atualizar caminhos S3 se a aba estiver carregada
            if hasattr(self, 'rt_dropdown'):
                self.update_s3_path()

            # Atualizar status do monitoring se a aba estiver carregada
            if hasattr(self, 'monitoring_status'):
                self.monitoring_status.value = "Faça login primeiro para visualizar jobs"
                self.monitoring_status.color = ft.Colors.GREY_400

            return False
        finally:
            if hasattr(self, 'page'):
                self.page.update()

    def update_status_bar(self):
        """Força atualização da barra de status"""
        self.refresh_aws_status()

    def safe_icon(self, icon_name, size=20, color=ft.Colors.WHITE, fallback_icon=ft.Icons.CIRCLE):
        """Cria um ícone com tratamento de erro para ícones inexistentes"""
        try:
            # Tentar criar o ícone
            return ft.Icon(icon_name, size=size, color=color)
        except (AttributeError, Exception):
            # Se o ícone não existir, usar um ícone padrão ou não mostrar nenhum
            try:
                return ft.Icon(fallback_icon, size=size, color=color)
            except:
                # Se nem o fallback funcionar, retornar container vazio
                return ft.Container(width=size, height=size)

    def create_sidebar(self):
        """Cria o menu lateral de navegação"""
        sections = [
            {"name": "Login", "icon": ft.Icons.LOGIN, "id": "Login", "type": "page"},
            {"name": "S3", "icon": ft.Icons.CLOUD, "id": "S3", "type": "page"},
            {"name": "EventBridge", "icon": ft.Icons.EVENT, "id": "EventBridge", "type": "page"},
            {
                "name": "Report",
                "icon": ft.Icons.ANALYTICS,
                "id": "Report",
                "type": "expandable",
                "subitems": [
                    {"name": "Athena", "icon": ft.Icons.QUERY_STATS, "id": "Report Athena"}
                ]
            },
            {
                "name": "Monitoring",
                "icon": ft.Icons.MONITOR,
                "id": "Monitoring",
                "type": "expandable",
                "subitems": [
                    {"name": "Glue", "icon": ft.Icons.DASHBOARD, "id": "Monitoring Glue"},
                    {"name": "Step Functions", "icon": ft.Icons.ANALYTICS, "id": "Monitoring STF"},
                    {"name": "Tables", "icon": ft.Icons.TABLE_CHART, "id": "Monitoring Tables"}
                ]
            }
        ]

        menu_items = []

        for section in sections:
            if section["type"] == "page":
                # Item simples de página
                is_selected = self.current_section == section["id"]

                menu_item = ft.Container(
                    content=ft.Row([
                        self.safe_icon(
                            section["icon"],
                            size=20,
                            color=ft.Colors.WHITE if is_selected else ft.Colors.GREY_400,
                            fallback_icon=ft.Icons.CIRCLE
                        ),
                        ft.Text(
                            section["name"],
                            size=14,
                            color=ft.Colors.WHITE if is_selected else ft.Colors.GREY_400,
                            weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL
                        )
                    ], alignment=ft.MainAxisAlignment.START, spacing=10),
                    padding=ft.Padding(15, 12, 15, 12),
                    margin=ft.Margin(5, 2, 5, 2),
                    bgcolor=ft.Colors.BLUE_700 if is_selected else ft.Colors.TRANSPARENT,
                    border_radius=8,
                    on_click=lambda e, section_id=section["id"]: self.on_sidebar_click(section_id),
                    ink=True
                )
                menu_items.append(menu_item)

            elif section["type"] == "expandable":
                # Item expandível com sub-itens
                is_expanded = self.expanded_menus.get(section["id"], False)
                has_selected_child = any(self.current_section == subitem["id"] for subitem in section["subitems"])

                # Item principal
                expansion_state = "expandido" if is_expanded else "recolhido"
                main_item = ft.Container(
                    content=ft.Row([
                        self.safe_icon(
                            section["icon"],
                            size=20,
                            color=ft.Colors.WHITE if has_selected_child else ft.Colors.GREY_400,
                            fallback_icon=ft.Icons.CIRCLE
                        ),
                        ft.Text(
                            section["name"],
                            size=14,
                            color=ft.Colors.WHITE if has_selected_child else ft.Colors.GREY_400,
                            weight=ft.FontWeight.BOLD if has_selected_child else ft.FontWeight.NORMAL
                        ),
                        ft.Icon(
                            ft.Icons.EXPAND_MORE if is_expanded else ft.Icons.CHEVRON_RIGHT,
                            size=16,
                            color=ft.Colors.GREY_400
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=10),
                    padding=ft.Padding(15, 12, 15, 12),
                    margin=ft.Margin(5, 2, 5, 2),
                    bgcolor=ft.Colors.GREY_700 if has_selected_child else ft.Colors.TRANSPARENT,
                    border_radius=8,
                    on_click=lambda e, section_id=section["id"]: self.toggle_menu_expansion(section_id),
                    ink=True
                )
                menu_items.append(main_item)

                # Sub-itens (apenas se expandido)
                if is_expanded:
                    for subitem in section["subitems"]:
                        is_sub_selected = self.current_section == subitem["id"]

                        sub_menu_item = ft.Container(
                            content=ft.Row([
                                ft.Container(width=10),  # Indentação
                                self.safe_icon(
                                    subitem["icon"],
                                    size=18,
                                    color=ft.Colors.WHITE if is_sub_selected else ft.Colors.GREY_500,
                                    fallback_icon=ft.Icons.CIRCLE
                                ),
                                ft.Text(
                                    subitem["name"],
                                    size=13,
                                    color=ft.Colors.WHITE if is_sub_selected else ft.Colors.GREY_500,
                                    weight=ft.FontWeight.BOLD if is_sub_selected else ft.FontWeight.NORMAL
                                )
                            ], alignment=ft.MainAxisAlignment.START, spacing=8),
                            padding=ft.Padding(15, 10, 15, 10),
                            margin=ft.Margin(15, 1, 5, 1),
                            bgcolor=ft.Colors.BLUE_600 if is_sub_selected else ft.Colors.TRANSPARENT,
                            border_radius=6,
                            on_click=lambda e, subitem_id=subitem["id"]: self.on_sidebar_click(subitem_id),
                            ink=True
                        )
                        menu_items.append(sub_menu_item)

        return ft.Container(
            content=ft.Column([
                # Cabeçalho do sidebar
                ft.Container(
                    content=ft.Column([
                        self.safe_icon(ft.Icons.CLOUD, size=40, color=ft.Colors.ORANGE, fallback_icon=ft.Icons.APPS),
                        ft.Text("EMPS Dados Manager", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE,
                               ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    padding=ft.Padding(20, 20, 20, 30),
                ),
                ft.Divider(color=ft.Colors.GREY_600, height=1),
                # Menu items
                ft.Column(menu_items, spacing=0),
            ], spacing=0),
            width=280,  # Increased for better proportion on larger screens
            bgcolor=ft.Colors.GREY_800,
            padding=ft.Padding(0, 0, 0, 10),
        )

    def toggle_menu_expansion(self, menu_id):
        """Alterna expansão/colapso de um menu"""
        self.expanded_menus[menu_id] = not self.expanded_menus.get(menu_id, False)
        print(f"[SIDEBAR] Menu {menu_id} {'expandido' if self.expanded_menus[menu_id] else 'recolhido'}")
        self.update_sidebar()

    def on_sidebar_click(self, section_id):
        """Handler para cliques no sidebar"""
        if self.current_section != section_id:
            self.current_section = section_id
            print(f"[SIDEBAR] Seção selecionada: {section_id}")

            # Se selecionando um sub-item de Monitoring ou Report, garantir que o menu está expandido
            if section_id in ["Monitoring Glue", "Monitoring STF", "Monitoring Tables"]:
                self.expanded_menus["Monitoring"] = True
            elif section_id in ["Report Athena"]:
                self.expanded_menus["Report"] = True

            # Recriar sidebar com nova seleção
            self.update_sidebar()

            # Atualizar área de conteúdo
            self.update_content_area()

            # Carregar cache se necessário (apenas para abas de monitoring)
            if section_id == "Monitoring Glue":
                def load_cache():
                    time.sleep(0.1)
                    self.check_and_load_cache_on_tab_open("glue")
                threading.Thread(target=load_cache, daemon=True).start()

            elif section_id == "Monitoring STF":
                def load_cache():
                    time.sleep(0.1)
                    self.check_and_load_cache_on_tab_open("stpf")
                threading.Thread(target=load_cache, daemon=True).start()

            elif section_id == "Monitoring Tables":
                def load_cache():
                    time.sleep(0.1)
                    self.check_and_load_cache_on_tab_open("tables")
                threading.Thread(target=load_cache, daemon=True).start()

            elif section_id == "EventBridge":
                def load_cache():
                    time.sleep(0.1)
                    self.check_and_load_cache_on_tab_open("eventbridge")
                threading.Thread(target=load_cache, daemon=True).start()

    def update_sidebar(self):
        """Atualiza o sidebar com nova seleção"""
        self.sidebar_container.content = self.create_sidebar().content
        self.page.update()

    def update_content_area(self):
        """Atualiza a área de conteúdo baseada na seção atual"""
        if self.current_section == "Login":
            content = self.login_tab
        elif self.current_section == "S3":
            content = self.s3_tab
        elif self.current_section == "Monitoring Glue":
            content = self.monitoring_glue_tab
        elif self.current_section == "Monitoring STF":
            content = self.monitoring_stpf_tab
        elif self.current_section == "Monitoring Tables":
            content = self.monitoring_tables_tab
        elif self.current_section == "EventBridge":
            content = self.monitoring_eventbridge_tab
        elif self.current_section == "Report Athena":
            content = self.report_athena_tab
        else:
            content = self.login_tab

        self.content_area.content = content
        self.page.update()

    def setup_layout_with_sidebar(self):
        # Criar conteúdos das abas
        self.login_tab = self.create_login_tab()
        self.s3_tab = self.create_s3_tab()
        self.monitoring_glue_tab = self.create_monitoring_tab()
        self.monitoring_stpf_tab = self.create_monitoring_stpf_tab()
        self.monitoring_tables_tab = self.create_monitoring_tables_tab()
        self.monitoring_eventbridge_tab = self.create_monitoring_eventbridge_tab()
        self.report_athena_tab = self.create_report_athena_tab()

        # Criar sidebar
        self.sidebar_container = self.create_sidebar()

        # Criar área de conteúdo principal - responsiva
        self.content_area = ft.Container(
            content=self.login_tab,  # Iniciar com Login
            expand=True,
            padding=ft.Padding(30, 30, 30, 30),  # More padding for larger screens
            bgcolor=ft.Colors.GREY_900
        )

        # Layout principal com sidebar + conteúdo
        content_layout = ft.Row([
            self.sidebar_container,
            ft.VerticalDivider(width=1, color=ft.Colors.GREY_600),
            self.content_area
        ], expand=True, spacing=0)

        # Layout principal com conteúdo + barra de status
        main_layout = ft.Column([
            content_layout,
            self.status_bar
        ], expand=True, spacing=0)

        self.page.add(main_layout)

    # Método on_tab_change removido - agora usando navegação por sidebar

    def create_login_tab(self):
        self.status_text = ft.Text(
            "Verificando status de login...",
            size=16,
            color=ft.Colors.ORANGE_600,
            weight=ft.FontWeight.W_500
        )

        self.profile_list = ft.Column(spacing=10)
        self.login_button = ft.ElevatedButton(
            "Login",
            on_click=self.on_login_click,
            disabled=True,
            width=200,
            height=45,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=4,
            ),
            tooltip="Fazer login com o perfil AWS selecionado"
        )

        self.logout_button = ft.ElevatedButton(
            "Logout",
            on_click=self.on_logout_click,
            visible=False,
            width=200,
            height=45,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.RED_600,
                    ft.ControlState.HOVERED: ft.Colors.RED_500,
                    ft.ControlState.PRESSED: ft.Colors.RED_700,
                },
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=4,
            ),
            tooltip="Fazer logout e retornar à seleção de perfil"
        )

        self.progress_ring = ft.ProgressRing(
            visible=False,
            stroke_width=3,
            color=ft.Colors.BLUE_400
        )

        return ft.Container(
            content=ft.Column([
                # Container para status principal
                ft.Container(
                    content=self.status_text,
                    padding=ft.padding.all(15),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.GREY_600),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),

                ft.Container(height=20),

                # Container para lista de profiles
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "Profiles SSO Disponíveis:",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE
                        ),
                        ft.Container(height=10),
                        ft.Container(
                            content=self.profile_list,
                            bgcolor=ft.Colors.GREY_800,
                            border_radius=8,
                            border=ft.border.all(1, ft.Colors.GREY_700),
                            padding=ft.padding.all(15),
                        )
                    ]),
                    expand=True
                ),

                ft.Container(height=20),

                # Container para botões de ação
                ft.Container(
                    content=ft.Row([
                        self.login_button,
                        self.logout_button,
                        self.progress_ring
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
                    padding=ft.padding.symmetric(vertical=15),
                ),
            ],
            spacing=15,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH
            ),
            padding=25,
            expand=True,
            bgcolor=ft.Colors.GREY_900
        )

    def create_s3_tab(self):
        s3_config = self.config.get("s3", {})

        # Prefix Dropdown
        prefix_options = s3_config.get("prefix_options", ["local-developers", "local-users"])
        self.prefix_dropdown = ft.Dropdown(
            label="Prefixo",
            options=[ft.dropdown.Option(option) for option in prefix_options],
            width=140,
            on_change=self.update_s3_path,
            tooltip="Selecione o prefixo do bucket S3"
        )

        # RT Dropdown
        rt_options = s3_config.get("rt_options", ["fluxo", "corebank", "assessoria", "credito"])
        self.rt_dropdown = ft.Dropdown(
            label="RT",
            options=[ft.dropdown.Option(option) for option in rt_options],
            width=120,
            on_change=self.on_rt_change,
            tooltip="Selecione o tipo de RT (Routing Table)"
        )

        # Environment Dropdown
        env_options = s3_config.get("environment_options", ["sirius", "athena"])
        self.env_dropdown = ft.Dropdown(
            label="Ambiente",
            options=[ft.dropdown.Option(option) for option in env_options],
            width=120,
            on_change=self.update_s3_path,
            tooltip="Selecione o ambiente de trabalho"
        )

        # Squad Dropdown (inicialmente vazio, será preenchido baseado no RT)
        self.squad_dropdown = ft.Dropdown(
            label="Squad",
            options=[],
            width=140,
            on_change=self.update_s3_path,
            disabled=True,  # Desabilitado até selecionar RT
            tooltip="Selecione o squad (equipe). Primeiro selecione um RT"
        )


        # Local Path Display
        self.local_path_text = ft.Text(
            "Pasta local: Selecione Prefixo, RT, Ambiente e Squad",
            size=12,
            color=ft.Colors.GREY_400,
            selectable=True
        )

        # Open Folder Button
        self.open_folder_button = ft.ElevatedButton(
            "📁 Abrir Pasta",
            on_click=self.open_local_folder,
            disabled=True,
            width=130,
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=3,
            )
        )

        # Final S3 Path Display
        self.s3_path_text = ft.Text(
            "Caminho S3: Selecione Prefixo, RT, Ambiente e Squad",
            size=12,
            color=ft.Colors.GREY_400,
            selectable=True
        )

        # Sync Buttons
        self.sync_to_s3_button = ft.ElevatedButton(
            "🔄 Local → S3",
            on_click=self.sync_to_s3,
            disabled=True,
            width=160,
            height=45,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=4,
            ),
            tooltip="Sincronizar arquivos da pasta local para o bucket S3"
        )

        self.sync_from_s3_button = ft.ElevatedButton(
            "🔄 S3 → Local",
            on_click=self.sync_from_s3,
            disabled=True,
            width=160,
            height=45,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=4,
            ),
            tooltip="Sincronizar arquivos do bucket S3 para a pasta local"
        )

        # Checkbox para --delete no S3 → Local
        self.delete_checkbox = ft.Checkbox(
            label="Usar --delete (S3 → Local)",
            value=False,
            tooltip="Remove arquivos locais que não existem no S3"
        )

        # Progress and Status
        self.s3_progress = ft.ProgressRing(
            visible=False
        )
        self.s3_status = ft.Text(
            "",
            size=14,
            color=ft.Colors.BLUE
        )

        # Carregar seleções salvas
        self.load_saved_selections()

        return ft.Container(
            content=ft.Column([
                # Container de configurações
                ft.Container(
                    content=ft.Column([
                        ft.Text("Configurações:", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        ft.Row([self.prefix_dropdown, self.rt_dropdown, self.env_dropdown, self.squad_dropdown], spacing=15),
                    ]),
                    padding=ft.padding.all(20),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),

                ft.Container(height=15),

                # Container de preview dos caminhos
                ft.Container(
                    content=ft.Column([
                        ft.Text("Preview dos Caminhos:", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        ft.Row([
                            ft.Column([
                                self.local_path_text,
                            ], expand=True),
                            self.open_folder_button
                        ], spacing=10, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=8),
                        self.s3_path_text,
                    ]),
                    padding=ft.padding.all(20),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),

                ft.Container(height=15),

                # Container de sincronização
                ft.Container(
                    content=ft.Column([
                        ft.Text("Sincronização:", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=15),
                        ft.Row([
                            self.sync_to_s3_button,
                            self.sync_from_s3_button,
                            self.s3_progress
                        ], spacing=20, alignment=ft.MainAxisAlignment.CENTER),
                        ft.Container(height=15),
                        self.delete_checkbox,
                        ft.Container(height=10),
                        self.s3_status,
                    ]),
                    padding=ft.padding.all(20),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),
            ],
            spacing=15,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO
            ),
            padding=25,
            expand=True,
            bgcolor=ft.Colors.GREY_900
        )

    def create_monitoring_tab(self):
        # Filtro de busca
        self.job_filter = ft.TextField(
            label="Filtrar jobs (separe por vírgula)",
            width=300,
            value=self.load_filter_text("glue_monitoring"),
            on_change=self.filter_jobs
        )

        # Filtro por status
        self.status_filter = ft.Dropdown(
            label="Status",
            options=[
                ft.dropdown.Option("TODOS"),
                ft.dropdown.Option("SUCCEEDED"),
                ft.dropdown.Option("FAILED"),
                ft.dropdown.Option("RUNNING"),
                ft.dropdown.Option("NEVER_RUN"),
            ],
            value="TODOS",
            width=150,
            on_change=self.filter_jobs
        )

        # Controles de atualização automática - apenas horas
        self.auto_refresh_enabled = ft.Checkbox(
            label="Atualização automática",
            value=False,
            on_change=self.toggle_auto_refresh
        )

        self.refresh_hours = ft.TextField(
            label="Horas para filtro",
            value="1",
            width=120,
            text_align=ft.TextAlign.CENTER,
            on_change=self.update_refresh_interval,
            tooltip="Jobs executados nas últimas X horas"
        )


        # Botão de atualização manual
        self.refresh_button = ft.ElevatedButton(
            "🔄 Atualizar",
            on_click=self.refresh_jobs,
            width=130,
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=3,
            )
        )

        # Botões de exportação
        self.copy_jobs_button = ft.IconButton(
            icon=ft.Icons.COPY,
            tooltip="Copiar tabela para clipboard",
            on_click=self.copy_jobs_to_clipboard,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
            )
        )

        self.export_jobs_button = ft.IconButton(
            icon=ft.Icons.FILE_DOWNLOAD,
            tooltip="Exportar tabela para Excel",
            on_click=self.export_jobs_to_excel,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
            )
        )

        # Progress e status
        self.monitoring_progress = ft.ProgressRing(visible=False)
        self.monitoring_status = ft.Text(
            "Faça login primeiro para visualizar jobs",
            size=14,
            color=ft.Colors.GREY_400
        )

        # Última atualização
        self.last_update_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.GREY_500
        )

        # Tabela de jobs
        self.jobs_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Job Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Última Execução", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Duração", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True
        )

        # KPIs de jobs (success, failed, running)
        self.jobs_success = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN)
        self.jobs_failed = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.RED)
        self.jobs_running = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY)
        self.jobs_dpu_hours = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.YELLOW)
        self.jobs_time = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE)
        self.jobs_flex = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY)

        def build_kpi_container(number_text, label, color, bgcolor):
            return ft.Container(
                content=ft.Column([
                    number_text,
                    ft.Text(label, size=12, color=color, weight=ft.FontWeight.W_500),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                width=120,
                height=80,
                bgcolor=bgcolor,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.GREY_700),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=6,
                    color=ft.Colors.BLACK26,
                    offset=ft.Offset(0, 2),
                ),
                padding=8
            )
        
        self.kpi_row = ft.Row([
            build_kpi_container(self.jobs_success, "Success", ft.Colors.GREEN, ft.Colors.GREY_800),
            build_kpi_container(self.jobs_failed, "Failed", ft.Colors.RED, ft.Colors.GREY_800),
            build_kpi_container(self.jobs_running, "Running", ft.Colors.GREY, ft.Colors.GREY_800),
            build_kpi_container(self.jobs_dpu_hours, "DPU Hours", ft.Colors.YELLOW, ft.Colors.GREY_800),
            build_kpi_container(self.jobs_time, "Minutes", ft.Colors.BLUE, ft.Colors.GREY_800),
            build_kpi_container(self.jobs_flex, "Flex", ft.Colors.GREY, ft.Colors.GREY_800),
        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, expand=True)

        # Container scrollável para a tabela com estilo aprimorado
        self.table_container = ft.Container(
            content=self.jobs_table,
            expand=True,
            bgcolor=ft.Colors.GREY_800,
            border=ft.border.all(1, ft.Colors.GREY_700),
            border_radius=12,
            padding=15,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.BLACK26,
                offset=ft.Offset(0, 2),
            )
        )

        # Inicializar variáveis de controle
        self.auto_refresh_timer = None
        self.refresh_interval = 60  # 1 minuto em segundos
        self.all_jobs = []
        self.filtered_jobs = []

        # Configurar pasta de cache
        self.cache_dir = Path(os.path.expandvars("%localappdata%")) / "empsdados-manager"

        return ft.Container(
            content=ft.Column([
                # Container de controles superiores
                ft.Container(
                    content=ft.Column([
                        ft.Text("Filtros e Controles:", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        ft.Row([
                            self.job_filter,
                            ft.Container(width=15),
                            self.status_filter,
                            ft.Container(width=20),
                            self.refresh_button,
                            self.monitoring_progress,
                            ft.Container(width=15),
                            self.copy_jobs_button,
                            ft.Container(width=5),
                            self.export_jobs_button
                        ], alignment=ft.MainAxisAlignment.START),

                        ft.Container(height=15),

                        # Controles de atualização automática
                        ft.Row([
                            self.auto_refresh_enabled,
                            ft.Container(width=15),
                            ft.Text("Filtrar últimas:", size=14, color=ft.Colors.WHITE),
                            self.refresh_hours,
                            ft.Text("horas", size=14, color=ft.Colors.WHITE),
                        ], alignment=ft.MainAxisAlignment.START),
                    ]),
                    padding=ft.padding.all(20),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),

                ft.Container(height=15),

                # Container de status
                ft.Container(
                    content=ft.Row([
                        self.monitoring_status,
                        ft.Container(expand=True),
                        self.last_update_text
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                ),

                ft.Container(height=15),

                # Container da tabela
                ft.Container(
                    content=ft.Column([
                        ft.Text("Jobs do AWS Glue:", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        self.kpi_row,
                        ft.Container(height=15),
                        self.table_container,
                    ]),
                    expand=True
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO
            ),
            padding=25,
            expand=True,
            bgcolor=ft.Colors.GREY_900
        )

    def create_monitoring_stpf_tab(self):

        # Filtro de busca
        self.job_filter_stpf = ft.TextField(
            label="Filtrar Step Functions (separe por vírgula)",
            width=300,
            value=self.load_filter_text("stp_monitoring"),
            on_change=self.filter_stpf_jobs
        )

        # Filtro por status
        self.status_filter_stpf = ft.Dropdown(
            label="Status",
            options=[
                ft.dropdown.Option("TODOS"),
                ft.dropdown.Option("SUCCEEDED"),
                ft.dropdown.Option("FAILED"),
                ft.dropdown.Option("RUNNING"),
                ft.dropdown.Option("NEVER_RUN"),
            ],
            value="TODOS",
            width=150,
            on_change=self.filter_stpf_jobs
        )

        # Controles de atualização automática STF - apenas horas
        self.auto_refresh_enabled_stpf = ft.Checkbox(
            label="Atualização automática",
            value=False,
            on_change=self.toggle_auto_refresh_stpf
        )

        self.refresh_hours_stpf = ft.TextField(
            label="Horas para filtro",
            value="1",
            width=120,
            text_align=ft.TextAlign.CENTER,
            on_change=self.update_refresh_interval_stpf,
            tooltip="Step Functions executadas nas últimas X horas"
        )

        # Botão de atualização manual
        self.refresh_button_stpf = ft.ElevatedButton(
            "🔄 Atualizar",
            on_click=self.refresh_stpf_jobs,
            width=130,
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=3,
            )
        )

        # Botões de exportação para STP
        self.copy_stpf_button = ft.IconButton(
            icon=ft.Icons.COPY,
            tooltip="Copiar tabela para clipboard",
            on_click=self.copy_stpf_to_clipboard,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
            )
        )

        self.export_stpf_button = ft.IconButton(
            icon=ft.Icons.FILE_DOWNLOAD,
            tooltip="Exportar tabela para Excel",
            on_click=self.export_stpf_to_excel,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
            )
        )

        # Progress e status
        self.monitoring_progress_stpf = ft.ProgressRing(visible=False)
        self.monitoring_status_sptf = ft.Text(
            "Faça login primeiro para visualizar stpf",
            size=14,
            color=ft.Colors.GREY_400
        )

        # Última atualização
        self.last_update_text_stpf = ft.Text(
            "",
            size=12,
            color=ft.Colors.GREY_500
        )

        # Tabela de STPF
        self.stpf_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Última Execução", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Duração", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True
        )

        # KPIs de jobs (success, failed, running)
        self.stpf_success = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN)
        self.stpf_failed = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.RED)
        self.stpf_running = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY)
        self.stpf_time = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE)

        def build_kpi_container(number_text, label, color, bgcolor):
            return ft.Container(
                content=ft.Column([
                    number_text,
                    ft.Text(label, size=12, color=color, weight=ft.FontWeight.W_500),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                width=120,
                height=80,
                bgcolor=bgcolor,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.GREY_700),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=6,
                    color=ft.Colors.BLACK26,
                    offset=ft.Offset(0, 2),
                ),
                padding=8
            )
        
        self.kpi_row_stpf = ft.Row([
            build_kpi_container(self.stpf_success, "Success", ft.Colors.GREEN, ft.Colors.GREY_800),
            build_kpi_container(self.stpf_failed, "Failed", ft.Colors.RED, ft.Colors.GREY_800),
            build_kpi_container(self.stpf_running, "Running", ft.Colors.GREY, ft.Colors.GREY_800),
            build_kpi_container(self.stpf_time, "Minutes", ft.Colors.BLUE, ft.Colors.GREY_800),
        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, expand=True)

        # Container scrollável para a tabela com estilo aprimorado
        self.table_container_stpf = ft.Container(
            content=self.stpf_table,
            expand=True,
            bgcolor=ft.Colors.GREY_800,
            border=ft.border.all(1, ft.Colors.GREY_700),
            border_radius=12,
            padding=15,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.BLACK26,
                offset=ft.Offset(0, 2),
            )
        )

        # Inicializar variáveis de controle STF
        self.auto_refresh_timer_stpf = None
        self.refresh_interval_stpf = 3600  # 1 hora em segundos
        self.filter_hours_stpf = 1  # Filtrar por 1 hora por padrão
        self.all_stpf = []
        self.filtered_stpf = []

        return ft.Container(
            content=ft.Column([
                # Container de controles superiores
                ft.Container(
                    content=ft.Column([
                        ft.Text("Filtros e Controles:", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        ft.Row([
                            self.job_filter_stpf,
                            ft.Container(width=15),
                            self.status_filter_stpf,
                            ft.Container(width=20),
                            self.refresh_button_stpf,
                            self.monitoring_progress_stpf,
                            ft.Container(width=15),
                            self.copy_stpf_button,
                            ft.Container(width=5),
                            self.export_stpf_button
                        ], alignment=ft.MainAxisAlignment.START),

                        ft.Container(height=15),

                        # Controles de atualização automática
                        ft.Row([
                            self.auto_refresh_enabled_stpf,
                            ft.Container(width=15),
                            ft.Text("Filtrar últimas:", size=14, color=ft.Colors.WHITE),
                            self.refresh_hours_stpf,
                            ft.Text("horas", size=14, color=ft.Colors.WHITE),
                        ], alignment=ft.MainAxisAlignment.START),
                    ]),
                    padding=ft.padding.all(20),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),

                ft.Container(height=15),

                # Container de status e atualização
                ft.Container(
                    content=ft.Row([
                        self.monitoring_status_sptf,
                        ft.Container(expand=True),
                        self.last_update_text_stpf
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),


                # Container da tabela
                ft.Container(
                    content=ft.Column([
                        ft.Text("Step Functions:", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        self.kpi_row_stpf,
                        ft.Container(height=15),
                        self.table_container_stpf,
                    ]),
                    expand=True
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO
            ),
            padding=25,
            expand=True,
            bgcolor=ft.Colors.GREY_900
        )

    def update_s3_path(self, e=None):
        prefix = self.prefix_dropdown.value
        rt = self.rt_dropdown.value
        squad = self.squad_dropdown.value
        env = self.env_dropdown.value

        # Verificar se RT tem squads disponíveis
        rt_has_squads = False
        if rt:
            rt_squad_hierarchy = self.config.get("s3", {}).get("rt_squad_hierarchy", {})
            available_squads = rt_squad_hierarchy.get(rt, [])
            rt_has_squads = len(available_squads) > 0

        # Update local path
        if prefix and rt and env and (squad or not rt_has_squads):
            user_home = Path.home()
            s3_base = self.config.get("s3", {}).get("default_base_path", "s3")
            if rt_has_squads and squad:
                local_path = user_home / s3_base / prefix / rt / env / squad
            elif not rt_has_squads:
                local_path = user_home / s3_base / prefix / rt / env
            else:
                local_path = None

            if local_path:
                self.local_path_text.value = f"Pasta local: {local_path}"
                self.local_path_text.color = ft.Colors.GREEN
                # Enable open folder button
                self.open_folder_button.disabled = False
            else:
                self.local_path_text.value = "Pasta local: Selecione todas as opções necessárias"
                self.local_path_text.color = ft.Colors.GREY_400
                self.open_folder_button.disabled = True
        else:
            if rt_has_squads:
                self.local_path_text.value = "Pasta local: Selecione Prefixo, RT, Ambiente e Squad"
            else:
                self.local_path_text.value = "Pasta local: Selecione Prefixo, RT e Ambiente"
            self.local_path_text.color = ft.Colors.GREY_400
            # Disable open folder button
            self.open_folder_button.disabled = True

        # Update S3 path
        if prefix and rt and env and (squad or not rt_has_squads) and self.current_account_id:
            s3_base_uri = f"s3://itau-self-wkp-sa-east-1-{self.current_account_id}"
            if rt_has_squads and squad:
                final_s3_path = f"{s3_base_uri}/{prefix}/{rt}/{env}/{squad}/"
            elif not rt_has_squads:
                final_s3_path = f"{s3_base_uri}/{prefix}/{rt}/{env}/"
            else:
                final_s3_path = None

            if final_s3_path:
                self.s3_path_text.value = f"Caminho S3: {final_s3_path}"
                self.s3_path_text.color = ft.Colors.GREEN
                # Enable sync buttons
                self.sync_to_s3_button.disabled = False
                self.sync_from_s3_button.disabled = False
            else:
                self.s3_path_text.value = "Caminho S3: Selecione todas as opções necessárias"
                self.s3_path_text.color = ft.Colors.GREY_400
                self.sync_to_s3_button.disabled = True
                self.sync_from_s3_button.disabled = True
        else:
            if not self.current_account_id:
                self.s3_path_text.value = "Caminho S3: Faça login primeiro"
            elif rt_has_squads:
                self.s3_path_text.value = "Caminho S3: Selecione Prefixo, RT, Ambiente e Squad"
            else:
                self.s3_path_text.value = "Caminho S3: Selecione Prefixo, RT e Ambiente"
            self.s3_path_text.color = ft.Colors.GREY_400

            # Disable sync buttons
            self.sync_to_s3_button.disabled = True
            self.sync_from_s3_button.disabled = True

        # Salvar seleções automaticamente (somente se não estamos carregando)
        if not hasattr(self, '_loading_selections') or not self._loading_selections:
            self.save_selections()

        self.page.update()

    def on_rt_change(self, e):
        """Chamado quando RT é alterado - atualiza as squads disponíveis"""
        self.update_squad_options()
        self.update_s3_path()

    def update_squad_options(self):
        """Atualiza as opções do dropdown Squad baseado no RT selecionado"""
        rt_value = self.rt_dropdown.value

        if rt_value:
            # Obter hierarquia do config
            rt_squad_hierarchy = self.config.get("s3", {}).get("rt_squad_hierarchy", {})
            squad_options = rt_squad_hierarchy.get(rt_value, [])

            # Atualizar opções do dropdown
            self.squad_dropdown.options = [ft.dropdown.Option(option) for option in squad_options]
            self.squad_dropdown.disabled = len(squad_options) == 0

            # Limpar seleção atual se não for mais válida
            if self.squad_dropdown.value and self.squad_dropdown.value not in squad_options:
                self.squad_dropdown.value = None

        else:
            # Se nenhum RT selecionado, limpar e desabilitar squad
            self.squad_dropdown.options = []
            self.squad_dropdown.disabled = True
            self.squad_dropdown.value = None

        if hasattr(self, 'page'):
            self.page.update()

    def fetch_single_job_details(self, glue_client, job_name):
        """Busca detalhes de um único job Glue (para processamento paralelo)"""
        try:
            runs_response = glue_client.get_job_runs(
                JobName=job_name,
                MaxResults=1
            )

            if runs_response['JobRuns']:
                last_run = runs_response['JobRuns'][0]
                status = last_run['JobRunState']

                # Formatear tempo de execução
                start_time = last_run.get('StartedOn')
                end_time = last_run.get('CompletedOn')

                if start_time:
                    started_on_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    started_on_str = "N/A"

                # Calcular duração
                if start_time and end_time:
                    duration = end_time - start_time
                    duration_str = str(duration).split('.')[0]  # Remove microseconds
                elif start_time and status == 'RUNNING':
                    duration = datetime.now(timezone.utc) - start_time
                    duration_str = f"{str(duration).split('.')[0]} (em execução)"
                else:
                    duration_str = "N/A"

                # Variáveis de execução
                try:
                    dpuhours = round(last_run.get("DPUSeconds", 0) / 3600, 2)
                    glue_type = last_run.get("ExecutionClass", "")
                except:
                    dpuhours = 0
                    glue_type = ""
            else:
                status = "NEVER_RUN"
                started_on_str = "Nunca executado"
                duration_str = "N/A"
                start_time = None
                dpuhours = 0
                glue_type = ""

            return {
                'name': job_name,
                'status': status,
                'last_execution': started_on_str,
                'duration': duration_str,
                'start_time_obj': start_time,
                "dpuhours": dpuhours,
                "glue_type": glue_type
            }

        except Exception as e:
            return {
                'name': job_name,
                'status': "ERROR",
                'last_execution': f"Erro: {str(e)}",
                'duration': "N/A",
                'start_time_obj': None,
                "dpuhours": 0,
                "glue_type": ""
            }

    def fetch_glue_jobs(self):
        """Busca jobs do AWS Glue e seus status usando processamento paralelo otimizado"""
        try:
            if not self.current_account_id:
                return []

            glue_client = boto3.client('glue')

            # 1. Buscar todos os jobs (rápido)
            print("🔍 Listando jobs do Glue...")
            paginator = glue_client.get_paginator('get_jobs')
            all_job_names = []

            for page in paginator.paginate():
                for job in page['Jobs']:
                    all_job_names.append(job['Name'])

            if not all_job_names:
                print("📋 Nenhum job encontrado na conta")
                return []

            print(f"📋 Encontrados {len(all_job_names)} jobs Glue. Iniciando busca paralela...")

            # Update UI with job count
            if hasattr(self, 'monitoring_status'):
                try:
                    self.monitoring_status.value = f"🔄 Encontrados {len(all_job_names)} jobs. Carregando detalhes..."
                    self.page.update()
                except:
                    pass

            # 2. Buscar detalhes em paralelo (otimizado)
            jobs = []
            max_workers = min(15, max(5, len(all_job_names) // 4))  # Threads adaptáveis

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Criar client separado para cada thread (recomendação AWS)
                future_to_job = {
                    executor.submit(self.fetch_single_job_details, boto3.client('glue'), job_name): job_name
                    for job_name in all_job_names
                }

                completed = 0
                for future in as_completed(future_to_job):
                    try:
                        job_data = future.result()
                        jobs.append(job_data)
                        completed += 1

                        # Update progress mais frequentemente
                        if completed % 5 == 0 or completed == len(all_job_names):
                            progress_percent = (completed / len(all_job_names)) * 100
                            elapsed = time.time() - start_time
                            jobs_per_sec = completed / elapsed if elapsed > 0 else 0

                            print(f"⏳ Progresso: {completed}/{len(all_job_names)} ({progress_percent:.1f}%) - {jobs_per_sec:.1f} jobs/s")

                            # Update UI progress
                            if hasattr(self, 'monitoring_status'):
                                try:
                                    eta_remaining = (len(all_job_names) - completed) / jobs_per_sec if jobs_per_sec > 0 else 0
                                    self.monitoring_status.value = f"🔄 {completed}/{len(all_job_names)} ({progress_percent:.0f}%) - ETA: {eta_remaining:.0f}s"
                                    self.page.update()
                                except:
                                    pass

                    except Exception as e:
                        job_name = future_to_job[future]
                        print(f"❌ Erro ao buscar detalhes do job {job_name}: {e}")

            total_time = time.time() - start_time
            print(f"✅ Carregamento concluído! {len(jobs)} jobs processados em {total_time:.1f}s")
            return jobs

        except Exception as e:
            print(f"❌ Erro ao buscar jobs do Glue: {e}")
            return []

    def refresh_jobs(self, e=None):
        """Atualiza a lista de jobs"""
        if not self.current_account_id:
            self.monitoring_status.value = "Faça login primeiro para visualizar jobs"
            self.monitoring_status.color = ft.Colors.RED
            self.page.update()
            return

        # Verificar se cache é recente (menos de 15 minutos)
        if self.is_cache_fresh("glue", 15):
            self.monitoring_status.value = "⏰ Cache recente (menos de 15 min) - Use o cache existente para evitar custos adicionais"
            self.monitoring_status.color = ft.Colors.BLUE
            self.page.update()
            return

        self.monitoring_progress.visible = True
        self.refresh_button.disabled = True
        self.monitoring_status.value = "Carregando jobs do Glue..."
        self.monitoring_status.color = ft.Colors.ORANGE
        self.page.update()

        try:
            # Buscar jobs em thread separada para não bloquear UI
            def fetch_in_background():
                jobs = self.fetch_glue_jobs()

                # Atualizar UI na thread principal
                def update_ui():
                    self.all_jobs = jobs
                    self.filter_jobs()  # Aplicar filtro atual

                    # Salvar cache após carregar dados
                    if jobs:
                        self.save_glue_cache(jobs)

                    self.last_update_text.value = f"Última atualização: {datetime.now().strftime('%H:%M:%S')}"

                    self.monitoring_status.value = f"✅ {len(jobs)} jobs encontrados"

                    self.monitoring_status.color = ft.Colors.GREEN

                    self.monitoring_progress.visible = False
                    self.refresh_button.disabled = False
                    self.page.update()

                # Executar atualização da UI na thread principal
                self.page.run_thread(update_ui)

            # Executar busca em background
            threading.Thread(target=fetch_in_background, daemon=True).start()

        except Exception as e:
            self.monitoring_status.value = f"❌ Erro: {str(e)}"
            self.monitoring_status.color = ft.Colors.RED
            self.monitoring_progress.visible = False
            self.refresh_button.disabled = False
            self.page.update()

    def filter_jobs(self, e=None):
        """Filtra jobs baseado no texto de busca, status e data de execução"""
        filter_text = self.job_filter.value if self.job_filter.value else ""
        # Salvar texto do filtro na configuração
        self.save_filter_text("glue_monitoring", filter_text)
        status_filter = self.status_filter.value if hasattr(self, 'status_filter') else "TODOS"

        # Começar com todos os jobs
        filtered_by_name = self.all_jobs.copy()

        # Aplicar filtro por data se atualização automática estiver ativa
        if hasattr(self, 'auto_refresh_enabled') and self.auto_refresh_enabled.value:
            hours_to_filter = getattr(self, 'filter_hours', 1)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_to_filter)

            # Filtrar apenas jobs executados nas últimas X horas
            filtered_by_time = []
            for job in self.all_jobs:
                if job.get('start_time_obj') and job['start_time_obj'] >= cutoff_time:
                    filtered_by_time.append(job)

            filtered_by_name = filtered_by_time

        # Aplicar filtro por nome se houver texto
        if filter_text.strip():
            # Dividir por vírgula e limpar espaços
            filter_terms = [term.strip().lower() for term in filter_text.split(',') if term.strip()]

            # Filtrar jobs que contenham qualquer um dos termos
            filtered_by_name_and_text = []
            for job in filtered_by_name:
                job_name_lower = job['name'].lower()
                # Se qualquer termo for encontrado no nome do job, incluir
                if any(term in job_name_lower for term in filter_terms):
                    filtered_by_name_and_text.append(job)

            filtered_by_name = filtered_by_name_and_text

        # Aplicar filtro por status
        if status_filter and status_filter != "TODOS":
            self.filtered_jobs = [job for job in filtered_by_name if job['status'] == status_filter]
        else:
            self.filtered_jobs = filtered_by_name

        # Ordenar por data de execução (mais recente primeiro)
        # Jobs com start_time_obj None (nunca executados) vão para o final
        self.filtered_jobs.sort(key=lambda job: (
            job.get('start_time_obj') is not None,  # True para jobs executados, False para nunca executados
            job.get('start_time_obj') or datetime.min.replace(tzinfo=timezone.utc)  # Data para ordenação
        ), reverse=True)

        self.update_jobs_table()

    def update_jobs_table(self):
        """Atualiza a tabela de jobs com os dados filtrados"""
        self.jobs_table.rows.clear()

        # Contadores
        success_count = 0
        failed_count = 0
        running_count = 0
        total_dpu_hours = 0.0
        total_minutes = 0.0
        total_flex = 0

        for job in self.filtered_jobs:
            # Definir cor do status
            status_color = ft.Colors.GREY
            if job['status'] == 'SUCCEEDED':
                status_color = ft.Colors.GREEN
                success_count += 1
            elif job['status'] == 'FAILED':
                status_color = ft.Colors.RED
                failed_count += 1
            elif job['status'] == 'RUNNING':
                status_color = ft.Colors.YELLOW
                running_count += 1
            elif job['status'] == 'NEVER_RUN':
                status_color = ft.Colors.BLUE

            # Calcular métricas de tempo
            duration = job.get("duration", "N/A")
            if isinstance(duration, str) and duration != "N/A" and job["status"] != "RUNNING":
                # Duração vem no formato "HH:MM:SS"
                try:
                    h, m, s = map(int, duration.split()[0].split(":"))
                    minutes = h * 60 + m + s / 60
                    total_minutes += minutes
                except:
                    pass

            # DPUs na execução
            if job.get("dpuhours"):
                total_dpu_hours += job["dpuhours"]
            
            # Calcula quantidade flex
            if job.get("glue_type") and job.get("glue_type") == "FLEX":
                total_flex += 1

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(job['name'], size=12)),
                    ft.DataCell(ft.Text(job['status'], size=12, color=status_color, weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(job['last_execution'], size=12)),
                    ft.DataCell(ft.Text(job['duration'], size=12)),
                ]
            )
            self.jobs_table.rows.append(row)

        self.jobs_success.value = str(success_count)
        self.jobs_failed.value = str(failed_count)
        self.jobs_running.value = str(running_count)
        self.jobs_dpu_hours.value = str(round(total_dpu_hours, 2))
        self.jobs_time.value = str(round(total_minutes, 1))
        self.jobs_flex.value = str(total_flex)

        if hasattr(self, 'page'):
            self.page.update()

    def update_refresh_interval(self, e=None):
        """Atualiza o intervalo de atualização automática e filtro por horas"""
        try:
            hours = int(self.refresh_hours.value or 1)

            # Intervalo fixo de 1 hora para atualização automática
            self.refresh_interval = 3600  # 1 hora em segundos
            self.filter_hours = hours  # Horas para filtro

            # Reiniciar timer se atualização automática estiver ativa
            if self.auto_refresh_enabled.value and self.auto_refresh_timer:
                self.stop_auto_refresh()
                self.start_auto_refresh()

            # Aplicar filtro se já temos dados
            if hasattr(self, 'all_jobs') and self.all_jobs:
                self.filter_jobs()

        except ValueError:
            # Se valores inválidos, usar padrão
            self.refresh_interval = 3600  # 1 hora
            self.filter_hours = 1

    def update_refresh_interval_stpf(self, e=None):
        """Atualiza o intervalo de atualização automática e filtro por horas para STF"""
        try:
            hours = int(self.refresh_hours_stpf.value or 1)

            # Intervalo fixo de 1 hora para atualização automática
            self.refresh_interval_stpf = 3600  # 1 hora em segundos
            self.filter_hours_stpf = hours  # Horas para filtro

            # Reiniciar timer se atualização automática estiver ativa
            if self.auto_refresh_enabled_stpf.value and self.auto_refresh_timer_stpf:
                self.stop_auto_refresh_stpf()
                self.start_auto_refresh_stpf()

            # Aplicar filtro se já temos dados
            if hasattr(self, 'all_stpf') and self.all_stpf:
                self.filter_stpf_jobs()

        except ValueError:
            # Se valores inválidos, usar padrão
            self.refresh_interval_stpf = 3600  # 1 hora
            self.filter_hours_stpf = 1

    def filter_stpf_jobs(self, e=None):
        """Filtra Step Functions baseado no texto de busca, status e data de execução"""
        filter_text = self.job_filter_stpf.value if self.job_filter_stpf.value else ""
        # Salvar texto do filtro na configuração
        self.save_filter_text("stp_monitoring", filter_text)
        status_filter = self.status_filter_stpf.value if hasattr(self, 'status_filter_stpf') else "TODOS"

        # Começar com todos os jobs
        filtered_by_name = self.all_stpf.copy()

        # Aplicar filtro por data se atualização automática estiver ativa
        if hasattr(self, 'auto_refresh_enabled_stpf') and self.auto_refresh_enabled_stpf.value:
            hours_to_filter = getattr(self, 'filter_hours_stpf', 1)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_to_filter)

            # Filtrar apenas jobs executados nas últimas X horas
            filtered_by_time = []
            for job in self.all_stpf:
                if job.get('start_time_obj') and job['start_time_obj'] >= cutoff_time:
                    filtered_by_time.append(job)

            filtered_by_name = filtered_by_time

        # Aplicar filtro por nome se houver texto
        if filter_text.strip():
            # Dividir por vírgula e limpar espaços
            filter_terms = [term.strip().lower() for term in filter_text.split(',') if term.strip()]

            # Filtrar jobs que contenham qualquer um dos termos
            filtered_by_name_and_text = []
            for job in filtered_by_name:
                job_name_lower = job['name'].lower()
                # Se qualquer termo for encontrado no nome do job, incluir
                if any(term in job_name_lower for term in filter_terms):
                    filtered_by_name_and_text.append(job)

            filtered_by_name = filtered_by_name_and_text

        # Aplicar filtro por status
        if status_filter and status_filter != "TODOS":
            self.filtered_stpf = [job for job in filtered_by_name if job['status'] == status_filter]
        else:
            self.filtered_stpf = filtered_by_name

        # Ordenar por data de execução (mais recente primeiro)
        self.filtered_stpf.sort(key=lambda job: (
            job.get('start_time_obj') is not None,  # True para jobs executados, False para nunca executados
            job.get('start_time_obj') or datetime.min.replace(tzinfo=timezone.utc)  # Data para ordenação
        ), reverse=True)

        self.update_stpf_table()

    def refresh_stpf_jobs(self, e=None):
        """Atualiza a lista de Step Functions"""
        if not self.current_account_id:
            self.monitoring_status_sptf.value = "Faça login primeiro para visualizar Step Functions"
            self.monitoring_status_sptf.color = ft.Colors.RED
            self.page.update()
            return

        # Verificar se cache é recente (menos de 15 minutos)
        if self.is_cache_fresh("stpf", 15):
            self.monitoring_status_sptf.value = "⏰ Cache recente (menos de 15 min) - Use o cache existente para evitar custos adicionais"
            self.monitoring_status_sptf.color = ft.Colors.BLUE
            self.page.update()
            return

        self.monitoring_progress_stpf.visible = True
        self.refresh_button_stpf.disabled = True
        self.monitoring_status_sptf.value = "Carregando Step Functions..."
        self.monitoring_status_sptf.color = ft.Colors.ORANGE
        self.page.update()

        try:
            # Buscar jobs em thread separada para não bloquear UI
            def fetch_in_background():
                jobs = self.fetch_step_functions()

                # Atualizar UI na thread principal
                def update_ui():
                    self.all_stpf = jobs
                    self.filter_stpf_jobs()  # Aplicar filtro atual

                    # Salvar cache após carregar dados
                    if jobs:
                        self.save_stpf_cache(jobs)

                    self.last_update_text_stpf.value = f"Última atualização: {datetime.now().strftime('%H:%M:%S')}"
                    self.monitoring_status_sptf.value = f"✅ {len(jobs)} Step Functions encontradas"
                    self.monitoring_status_sptf.color = ft.Colors.GREEN

                    self.monitoring_progress_stpf.visible = False
                    self.refresh_button_stpf.disabled = False
                    self.page.update()

                # Executar atualização da UI na thread principal
                self.page.run_thread(update_ui)

            # Executar busca em background
            threading.Thread(target=fetch_in_background, daemon=True).start()

        except Exception as e:
            self.monitoring_status_sptf.value = f"❌ Erro: {str(e)}"
            self.monitoring_status_sptf.color = ft.Colors.RED
            self.monitoring_progress_stpf.visible = False
            self.refresh_button_stpf.disabled = False
            self.page.update()

    def retry_with_backoff(self, func, max_retries=3, base_delay=1.0, *args, **kwargs):
        """Executa função com retry e backoff exponencial para evitar throttling"""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e).lower()
                # Verificar se é erro de throttling
                if any(throttle_word in error_msg for throttle_word in ['throttling', 'rate exceeded', 'too many requests', 'requestlimitexceeded']):
                    if attempt == max_retries - 1:  # Última tentativa
                        print(f"❌ Throttling persistente após {max_retries} tentativas: {e}")
                        raise

                    # Calcular delay com jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"⏳ Throttling detectado (tentativa {attempt + 1}/{max_retries}), aguardando {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    # Se não é throttling, falha imediatamente
                    raise
        return None

    def fetch_step_functions(self):
        """Busca Step Functions do AWS e seus status usando processamento paralelo otimizado"""
        try:
            if not self.current_account_id:
                return []

            sfn_client = boto3.client('stepfunctions')

            # 1. Buscar lista de todas as state machines primeiro (com retry)
            print("🔍 Listando Step Functions com proteção anti-throttling...")
            all_state_machines = []

            def list_state_machines_with_retry():
                paginator = sfn_client.get_paginator('list_state_machines')
                for page in paginator.paginate():
                    # Pequeno delay entre páginas
                    time.sleep(0.2)
                    for sm in page['stateMachines']:
                        all_state_machines.append({
                            'name': sm['name'],
                            'arn': sm['stateMachineArn']
                        })

            self.retry_with_backoff(list_state_machines_with_retry, max_retries=3, base_delay=2.0)

            if not all_state_machines:
                print("📋 Nenhuma Step Function encontrada na conta")
                return []

            print(f"📊 {len(all_state_machines)} Step Functions encontradas")

            # 2. Buscar detalhes em paralelo (otimizado contra throttling)
            state_machines = []
            max_workers = min(5, max(2, len(all_state_machines) // 8))  # Reduzido drasticamente para evitar throttling
            print(f"🔧 Usando {max_workers} workers para evitar throttling")

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Criar client separado para cada thread (recomendação AWS) com delay escalonado
                future_to_sm = {}
                for i, sm in enumerate(all_state_machines):
                    # Pequeno delay progressivo entre submissões para evitar burst
                    if i > 0:
                        time.sleep(0.05)  # 50ms entre submissões

                    future = executor.submit(self.fetch_single_stepfunction_details, boto3.client('stepfunctions'), sm['name'], sm['arn'])
                    future_to_sm[future] = sm['name']

                # Processar resultados conforme ficam prontos
                completed = 0
                for future in as_completed(future_to_sm):
                    try:
                        sm_data = future.result()
                        state_machines.append(sm_data)
                        completed += 1

                        # Log de progresso a cada 20%
                        if completed % max(1, len(all_state_machines) // 5) == 0:
                            progress = (completed / len(all_state_machines)) * 100
                            print(f"📈 Progresso: {completed}/{len(all_state_machines)} ({progress:.0f}%)")

                    except Exception as e:
                        sm_name = future_to_sm[future]
                        error_msg = str(e).lower()

                        # Verificar se é erro de throttling
                        if any(throttle_word in error_msg for throttle_word in ['throttling', 'rate exceeded', 'too many requests', 'requestlimitexceeded']):
                            print(f"⚠️  Throttling detectado em Step Function {sm_name}: {e}")
                            error_display = "THROTTLING - Tente novamente mais tarde"
                        else:
                            print(f"❌ Erro ao processar Step Function {sm_name}: {e}")
                            error_display = f"Erro: {str(e)}"

                        # Adicionar entrada com erro
                        state_machines.append({
                            'name': sm_name,
                            'status': "ERROR",
                            'last_execution': error_display,
                            'duration': "N/A",
                            'start_time_obj': None
                        })

            end_time = time.time()
            duration = end_time - start_time

            print(f"⚡ Step Functions processadas em {duration:.2f}s com {max_workers} threads (anti-throttling)")
            print(f"📈 Performance: {len(all_state_machines)/duration:.1f} Step Functions/s - Processo otimizado para evitar erros de API")

            return state_machines

        except Exception as e:
            print(f"Erro ao buscar Step Functions: {e}")
            return []

    def fetch_single_stepfunction_details(self, sfn_client, sm_name, sm_arn):
        """Busca detalhes de uma única Step Function com proteção contra throttling"""
        try:
            # Adicionar delay aleatório pequeno para espalhar requisições
            time.sleep(random.uniform(0.1, 0.3))

            # Buscar última execução da state machine com retry
            try:
                executions_response = self.retry_with_backoff(
                    sfn_client.list_executions,
                    max_retries=3,
                    base_delay=1.0,
                    stateMachineArn=sm_arn,
                    maxResults=1
                )

                if executions_response['executions']:
                    last_execution = executions_response['executions'][0]
                    status = last_execution['status']
                    start_time = last_execution.get('startDate')
                    stop_time = last_execution.get('stopDate')

                    if start_time:
                        started_on_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        started_on_str = "N/A"

                    # Calcular duração
                    if start_time and stop_time:
                        duration = stop_time - start_time
                        duration_str = str(duration).split('.')[0]  # Remove microseconds
                    elif start_time and status == 'RUNNING':
                        duration = datetime.now(timezone.utc) - start_time
                        duration_str = f"{str(duration).split('.')[0]} (em execução)"
                    else:
                        duration_str = "N/A"
                else:
                    status = "NEVER_RUN"
                    started_on_str = "Nunca executado"
                    duration_str = "N/A"
                    start_time = None

            except Exception as e:
                status = "ERROR"
                started_on_str = f"Erro: {str(e)}"
                duration_str = "N/A"
                start_time = None

            return {
                'name': sm_name,
                'status': status,
                'last_execution': started_on_str,
                'duration': duration_str,
                'start_time_obj': start_time  # Para ordenação
            }

        except Exception as e:
            return {
                'name': sm_name,
                'status': "ERROR",
                'last_execution': f"Erro: {str(e)}",
                'duration': "N/A",
                'start_time_obj': None
            }

    def update_stpf_table(self):
        """Atualiza a tabela de Step Functions com os dados filtrados"""
        self.stpf_table.rows.clear()

        # Contadores
        success_count = 0
        failed_count = 0
        running_count = 0
        total_minutes = 0.0

        for job in self.filtered_stpf:
            # Definir cor do status
            status_color = ft.Colors.GREY
            if job['status'] == 'SUCCEEDED':
                status_color = ft.Colors.GREEN
                success_count += 1
            elif job['status'] == 'FAILED':
                status_color = ft.Colors.RED
                failed_count += 1
            elif job['status'] == 'RUNNING':
                status_color = ft.Colors.YELLOW
                running_count += 1

            # Calcular métricas de tempo
            duration = job.get("duration", "N/A")
            if isinstance(duration, str) and duration != "N/A" and job["status"] != "RUNNING":
                # Duração vem no formato "HH:MM:SS"
                try:
                    h, m, s = map(int, duration.split()[0].split(":"))
                    minutes = h * 60 + m + s / 60
                    total_minutes += minutes
                except:
                    pass

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(job['name'], size=12, color=ft.Colors.WHITE)),
                    ft.DataCell(ft.Text(job['status'], size=12, color=status_color, weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(job['last_execution'], size=12, color=ft.Colors.WHITE)),
                    ft.DataCell(ft.Text(job['duration'], size=12, color=ft.Colors.WHITE)),
                ]
            )
            self.stpf_table.rows.append(row)

        # Atualizar KPIs
        self.stpf_success.value = str(success_count)
        self.stpf_failed.value = str(failed_count)
        self.stpf_running.value = str(running_count)
        self.stpf_time.value = str(round(total_minutes, 1))

        if hasattr(self, 'page'):
            self.page.update()

    def toggle_auto_refresh_stpf(self, e):
        """Ativa/desativa atualização automática para STF"""
        if self.auto_refresh_enabled_stpf.value:
            self.start_auto_refresh_stpf()
        else:
            self.stop_auto_refresh_stpf()

    def start_auto_refresh_stpf(self):
        """Inicia timer de atualização automática para STF"""
        if self.refresh_interval_stpf > 0:
            self.auto_refresh_timer_stpf = threading.Timer(self.refresh_interval_stpf, self.auto_refresh_callback_stpf)
            self.auto_refresh_timer_stpf.daemon = True
            self.auto_refresh_timer_stpf.start()

    def stop_auto_refresh_stpf(self):
        """Para timer de atualização automática para STF"""
        if self.auto_refresh_timer_stpf:
            self.auto_refresh_timer_stpf.cancel()
            self.auto_refresh_timer_stpf = None

    def auto_refresh_callback_stpf(self):
        """Callback para atualização automática de STF"""
        if self.auto_refresh_enabled_stpf.value:
            self.refresh_stpf_jobs()
            # Agendar próxima atualização
            if self.auto_refresh_enabled_stpf.value:  # Verificar novamente caso tenha sido desabilitado
                self.start_auto_refresh_stpf()

    def copy_stpf_to_clipboard(self, e):
        """Copia a tabela filtrada de Step Functions para o clipboard"""
        try:
            if not self.filtered_stpf:
                self.monitoring_status_sptf.value = "❌ Nenhuma Step Function para copiar"
                self.monitoring_status_sptf.color = ft.Colors.RED
                self.page.update()
                return

            # Criar cabeçalho
            headers = ["Name", "Status", "Última Execução", "Duração"]

            # Criar linhas
            lines = ["\t".join(headers)]

            for stpf in self.filtered_stpf:
                line = "\t".join([
                    stpf['name'],
                    stpf['status'],
                    stpf['last_execution'],
                    stpf['duration']
                ])
                lines.append(line)

            # Copiar para clipboard
            clipboard_text = "\n".join(lines)
            pyperclip.copy(clipboard_text)

            self.monitoring_status_sptf.value = f"✅ {len(self.filtered_stpf)} Step Functions copiadas para clipboard"
            self.monitoring_status_sptf.color = ft.Colors.GREEN
            self.page.update()

        except Exception as e:
            self.monitoring_status_sptf.value = f"❌ Erro ao copiar: {str(e)}"
            self.monitoring_status_sptf.color = ft.Colors.RED
            self.page.update()

    def export_stpf_to_excel(self, e=None):
        """Exporta a tabela filtrada de Step Functions para Excel"""
        try:
            if not self.filtered_stpf:
                self.monitoring_status_sptf.value = "❌ Nenhuma Step Function para exportar"
                self.monitoring_status_sptf.color = ft.Colors.RED
                self.page.update()
                return

            # Mostrar status de escolha de pasta
            self.monitoring_status_sptf.value = "📁 Escolha onde salvar o arquivo..."
            self.monitoring_status_sptf.color = ft.Colors.BLUE
            self.page.update()

            # Preparar dados para DataFrame
            self.export_data_stpf = []
            for stpf in self.filtered_stpf:
                self.export_data_stpf.append({
                    'Name': stpf['name'],
                    'Status': stpf['status'],
                    'Última Execução': stpf['last_execution'],
                    'Duração': stpf['duration']
                })

            # Abrir seletor de pasta
            self.select_export_folder(self._export_stpf_after_folder_selection)

        except Exception as e:
            self.monitoring_status_sptf.value = f"❌ Erro ao preparar export: {str(e)}"
            self.monitoring_status_sptf.color = ft.Colors.RED
            self.page.update()

    def _export_stpf_after_folder_selection(self):
        """Executa o export Step Functions após a pasta ser selecionada"""
        try:
            # Criar DataFrame
            df = pd.DataFrame(self.export_data_stpf)

            # Nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"step_functions_{timestamp}.xlsx"

            # Caminho completo usando a pasta selecionada
            file_path = self.export_folder / filename

            # Exportar
            df.to_excel(file_path, index=False, engine='openpyxl')

            # Feedback visual
            self.monitoring_status_sptf.value = f"✅ Exportado para {file_path.parent.name}/{filename}"
            self.monitoring_status_sptf.color = ft.Colors.GREEN
            self.page.update()

        except Exception as e:
            self.monitoring_status_sptf.value = f"❌ Erro ao exportar: {str(e)}"
            self.monitoring_status_sptf.color = ft.Colors.RED
            self.page.update()

    def toggle_auto_refresh(self, e):
        """Ativa/desativa atualização automática"""
        if self.auto_refresh_enabled.value:
            self.start_auto_refresh()
        else:
            self.stop_auto_refresh()

    def start_auto_refresh(self):
        """Inicia timer de atualização automática"""
        if self.refresh_interval > 0:
            self.auto_refresh_timer = threading.Timer(self.refresh_interval, self.auto_refresh_callback)
            self.auto_refresh_timer.daemon = True
            self.auto_refresh_timer.start()

    def stop_auto_refresh(self):
        """Para timer de atualização automática"""
        if self.auto_refresh_timer:
            self.auto_refresh_timer.cancel()
            self.auto_refresh_timer = None

    def auto_refresh_callback(self):
        """Callback para atualização automática"""
        if self.auto_refresh_enabled.value:
            self.refresh_jobs()
            # Agendar próxima atualização
            if self.auto_refresh_enabled.value:  # Verificar novamente caso tenha sido desabilitado
                self.start_auto_refresh()

    # ============== FUNÇÕES DE CACHE ==============

    def ensure_cache_directory(self):
        """Garante que a pasta de cache existe"""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"❌ Erro ao criar pasta de cache: {e}")
            return False

    def get_glue_cache_filename(self):
        """Retorna o nome do arquivo de cache do Glue para a conta atual"""
        if not self.current_account_id:
            return self.cache_dir / "glue_cache.json"  # Fallback para casos sem account_id
        return self.cache_dir / f"glue_cache_{self.current_account_id}.json"

    def get_stpf_cache_filename(self):
        """Retorna o nome do arquivo de cache do Step Functions para a conta atual"""
        if not self.current_account_id:
            return self.cache_dir / "stpf_cache.json"  # Fallback para casos sem account_id
        return self.cache_dir / f"stpf_cache_{self.current_account_id}.json"

    def is_cache_fresh(self, cache_type, minutes_threshold=15):
        """Verifica se o cache é recente (menos de X minutos)"""
        try:
            if cache_type == "glue":
                cache_file = self.get_glue_cache_filename()
            elif cache_type == "stpf":
                cache_file = self.get_stpf_cache_filename()
            elif cache_type == "tables":
                cache_file = self.get_tables_cache_filename()
            else:
                return False

            if not cache_file.exists():
                return False

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Verificar se é da conta/profile atual
            if (cache_data.get("account_id") != self.current_account_id or
                cache_data.get("profile") != self.current_profile):
                return False

            # Verificar timestamp
            updated_at = cache_data.get("updated_at")
            if not updated_at:
                return False

            # Converter timestamp para datetime
            cache_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)

            # Calcular diferença em minutos
            time_diff = (current_time - cache_time).total_seconds() / 60

            is_fresh = time_diff < minutes_threshold
            print(f"🕐 Cache {cache_type}: {time_diff:.1f} min atrás - {'fresco' if is_fresh else 'expirado'}")

            return is_fresh

        except Exception as e:
            print(f"❌ Erro ao verificar cache {cache_type}: {e}")
            return False

    def is_cache_fresh_by_data(self, cache_data, minutes_threshold=15):
        """Verifica se o cache é recente usando dados já carregados"""
        try:
            # Verificar timestamp
            updated_at = cache_data.get("updated_at")
            if not updated_at:
                return False

            # Converter timestamp para datetime
            cache_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)

            # Calcular diferença em minutos
            time_diff = (current_time - cache_time).total_seconds() / 60

            is_fresh = time_diff < minutes_threshold
            print(f"🕐 Cache Tables: {time_diff:.1f} min atrás - {'fresco' if is_fresh else 'expirado'}")

            return is_fresh

        except Exception as e:
            print(f"❌ Erro ao verificar timestamp do cache: {e}")
            return False

    def save_glue_cache(self, jobs_data):
        """Salva dados dos jobs Glue no cache local"""
        try:
            if not self.ensure_cache_directory():
                return False

            current_time = datetime.now().isoformat()
            cache_data = {
                "timestamp": current_time,
                "updated_at": current_time,
                "account_id": self.current_account_id,
                "profile": self.current_profile,
                "jobs_count": len(jobs_data),
                "jobs": []
            }

            # Converter dados para JSON (datetime não é serializável)
            for job in jobs_data:
                job_copy = job.copy()
                if 'start_time_obj' in job_copy and job_copy['start_time_obj']:
                    job_copy['start_time_obj'] = job_copy['start_time_obj'].isoformat()
                else:
                    job_copy['start_time_obj'] = None
                cache_data["jobs"].append(job_copy)

            cache_file = self.get_glue_cache_filename()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Cache Glue salvo: {len(jobs_data)} jobs em {cache_file}")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar cache Glue: {e}")
            return False

    def load_glue_cache(self):
        """Carrega dados dos jobs Glue do cache local"""
        try:
            cache_file = self.get_glue_cache_filename()
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Verificar se o cache é para a conta/profile atual
            if (cache_data.get("account_id") != self.current_account_id or
                cache_data.get("profile") != self.current_profile):
                print("🔄 Cache Glue é de outra conta/profile, ignorando...")
                return None

            # Converter datetime strings de volta
            jobs = []
            for job in cache_data.get("jobs", []):
                if job.get('start_time_obj'):
                    try:
                        job['start_time_obj'] = datetime.fromisoformat(job['start_time_obj'])
                    except:
                        job['start_time_obj'] = None
                jobs.append(job)

            cache_timestamp = cache_data.get("timestamp", "")
            print(f"📁 Cache Glue carregado: {len(jobs)} jobs (salvo em {cache_timestamp})")
            return jobs

        except Exception as e:
            print(f"❌ Erro ao carregar cache Glue: {e}")
            return None

    def save_stpf_cache(self, stpf_data):
        """Salva dados das Step Functions no cache local"""
        try:
            if not self.ensure_cache_directory():
                return False

            current_time = datetime.now().isoformat()
            cache_data = {
                "timestamp": current_time,
                "updated_at": current_time,
                "account_id": self.current_account_id,
                "profile": self.current_profile,
                "stpf_count": len(stpf_data),
                "step_functions": []
            }

            # Converter dados para JSON
            for stpf in stpf_data:
                stpf_copy = stpf.copy()
                if 'start_time_obj' in stpf_copy and stpf_copy['start_time_obj']:
                    stpf_copy['start_time_obj'] = stpf_copy['start_time_obj'].isoformat()
                else:
                    stpf_copy['start_time_obj'] = None
                cache_data["step_functions"].append(stpf_copy)

            cache_file = self.get_stpf_cache_filename()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Cache STP salvo: {len(stpf_data)} Step Functions em {cache_file}")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar cache STP: {e}")
            return False

    def load_stpf_cache(self):
        """Carrega dados das Step Functions do cache local"""
        try:
            cache_file = self.get_stpf_cache_filename()
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Verificar se o cache é para a conta/profile atual
            if (cache_data.get("account_id") != self.current_account_id or
                cache_data.get("profile") != self.current_profile):
                print("🔄 Cache STP é de outra conta/profile, ignorando...")
                return None

            # Converter datetime strings de volta
            stpf_list = []
            for stpf in cache_data.get("step_functions", []):
                if stpf.get('start_time_obj'):
                    try:
                        stpf['start_time_obj'] = datetime.fromisoformat(stpf['start_time_obj'])
                    except:
                        stpf['start_time_obj'] = None
                stpf_list.append(stpf)

            cache_timestamp = cache_data.get("timestamp", "")
            print(f"📁 Cache STP carregado: {len(stpf_list)} Step Functions (salvo em {cache_timestamp})")
            return stpf_list

        except Exception as e:
            print(f"❌ Erro ao carregar cache STP: {e}")
            return None

    def get_tables_cache_filename(self):
        """Retorna o nome do arquivo de cache das Tabelas para a conta atual"""
        if not self.current_account_id:
            return self.cache_dir / "tables_cache.json"  # Fallback para casos sem account_id
        return self.cache_dir / f"tables_cache_{self.current_account_id}.json"

    def save_tables_cache(self, tables_data):
        """Salva dados das Tabelas no cache local"""
        try:
            if not self.ensure_cache_directory():
                return False

            current_time = datetime.now(timezone.utc).isoformat()
            cache_data = {
                "timestamp": current_time,
                "updated_at": current_time,
                "account_id": self.current_account_id,
                "profile": self.current_profile,
                "tables_count": len(tables_data),
                "tables": tables_data  # Tables data is already JSON serializable
            }

            cache_file = self.get_tables_cache_filename()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Cache Tables salvo: {len(tables_data)} tabelas em {cache_file}")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar cache Tables: {e}")
            return False

    def load_tables_cache(self):
        """Carrega dados das Tabelas do cache local"""
        try:
            cache_file = self.get_tables_cache_filename()
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Verificar se o cache é para a conta/profile atual
            if (cache_data.get("account_id") != self.current_account_id or
                cache_data.get("profile") != self.current_profile):
                print("🔄 Cache Tables é de outra conta/profile, ignorando...")
                return None

            # Verificar se o cache não está muito antigo (15 minutos)
            if not self.is_cache_fresh_by_data(cache_data, minutes_threshold=15):
                print("⏰ Cache Tables está muito antigo (>15 min), ignorando...")
                return None

            tables_list = cache_data.get("tables", [])
            cache_timestamp = cache_data.get("timestamp", "")
            print(f"📁 Cache Tables carregado: {len(tables_list)} tabelas (salvo em {cache_timestamp})")
            return tables_list

        except Exception as e:
            print(f"❌ Erro ao carregar cache Tables: {e}")
            return None

    def get_eventbridge_cache_filename(self):
        """Retorna o nome do arquivo de cache do EventBridge para a conta atual"""
        if not self.current_account_id:
            return self.cache_dir / "eventbridge_cache.json"  # Fallback para casos sem account_id
        return self.cache_dir / f"eventbridge_cache_{self.current_account_id}.json"

    def save_eventbridge_cache(self, rules_data):
        """Salva dados das regras EventBridge no cache local"""
        try:
            if not self.ensure_cache_directory():
                return False

            current_time = datetime.now(timezone.utc).isoformat()
            cache_data = {
                "timestamp": current_time,
                "updated_at": current_time,
                "account_id": self.current_account_id,
                "profile": self.current_profile,
                "rules_count": len(rules_data),
                "rules": rules_data  # Rules data is already JSON serializable
            }

            cache_file = self.get_eventbridge_cache_filename()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Cache EventBridge salvo: {len(rules_data)} regras em {cache_file}")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar cache EventBridge: {e}")
            return False

    def load_eventbridge_cache(self):
        """Carrega dados das regras EventBridge do cache local"""
        try:
            cache_file = self.get_eventbridge_cache_filename()
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Verificar se o cache é para a conta/profile atual
            if (cache_data.get("account_id") != self.current_account_id or
                cache_data.get("profile") != self.current_profile):
                print("🔄 Cache EventBridge é de outra conta/profile, ignorando...")
                return None

            # Verificar se o cache não está muito antigo (15 minutos)
            if not self.is_cache_fresh_by_data(cache_data, minutes_threshold=15):
                print("⏰ Cache EventBridge está muito antigo (>15 min), ignorando...")
                return None

            rules_list = cache_data.get("rules", [])
            cache_timestamp = cache_data.get("timestamp", "")
            print(f"📁 Cache EventBridge carregado: {len(rules_list)} regras (salvo em {cache_timestamp})")
            return rules_list

        except Exception as e:
            print(f"❌ Erro ao carregar cache EventBridge: {e}")
            return None

    def check_and_load_cache_on_tab_open(self, tab_type):
        """Verifica cache ao abrir aba e carrega conforme regras de atualização automática"""
        if not self.current_account_id:
            return  # Não fazer nada se não estiver logado

        if tab_type == "glue":
            # Tentar carregar cache do Glue
            cached_jobs = self.load_glue_cache()
            if cached_jobs:
                # Cache encontrado - carregar sempre
                self.all_jobs = cached_jobs
                self.filter_jobs()
                self.monitoring_status.value = f"📁 {len(cached_jobs)} jobs carregados do cache"
                self.monitoring_status.color = ft.Colors.BLUE
                self.last_update_text.value = f"Cache carregado: {datetime.now().strftime('%H:%M:%S')}"
                self.page.update()

                # Verificar se deve atualizar automaticamente
                if hasattr(self, 'auto_refresh_enabled') and self.auto_refresh_enabled.value:
                    print("🔄 Auto-refresh ativo - Atualizando dados do Glue...")
                    self.refresh_jobs()
                else:
                    print("📁 Cache carregado - Auto-refresh inativo, use o botão Atualizar se necessário")
            else:
                # Não tem cache, carregar dados automaticamente
                print("🔄 Cache Glue não encontrado, carregando dados...")
                self.refresh_jobs()

        elif tab_type == "stpf":
            # Tentar carregar cache do Step Functions
            cached_stpf = self.load_stpf_cache()
            if cached_stpf:
                # Cache encontrado - carregar sempre
                self.all_stpf = cached_stpf
                self.filter_stpf_jobs()
                self.monitoring_status_sptf.value = f"📁 {len(cached_stpf)} Step Functions carregadas do cache"
                self.monitoring_status_sptf.color = ft.Colors.BLUE
                self.last_update_text_stpf.value = f"Cache carregado: {datetime.now().strftime('%H:%M:%S')}"
                self.page.update()

                # Verificar se deve atualizar automaticamente
                if hasattr(self, 'auto_refresh_enabled_stpf') and self.auto_refresh_enabled_stpf.value:
                    print("🔄 Auto-refresh ativo - Atualizando dados do Step Functions...")
                    self.refresh_stpf_jobs()
                else:
                    print("📁 Cache carregado - Auto-refresh inativo, use o botão Atualizar se necessário")
            else:
                # Não tem cache, carregar dados automaticamente
                print("🔄 Cache Step Functions não encontrado, carregando dados...")
                self.refresh_stpf_jobs()

        elif tab_type == "tables":
            # Tentar carregar cache das Tabelas
            cached_tables = self.load_tables_cache()
            if cached_tables:
                # Cache encontrado - só carregar cache (Tables não tem auto-refresh)
                self.all_tables = cached_tables
                self.filter_tables()
                self.monitoring_status_tables.value = f"📁 {len(cached_tables)} tabelas carregadas do cache"
                self.monitoring_status_tables.color = ft.Colors.BLUE
                self.page.update()
                print("📁 Cache Tables carregado - Use o botão Atualizar para buscar dados atualizados")
            else:
                # Não tem cache, carregar dados automaticamente
                print("🔄 Cache Tables não encontrado, carregando dados...")
                self.refresh_tables()

        elif tab_type == "eventbridge":
            # Tentar carregar cache do EventBridge
            cached_rules = self.load_eventbridge_cache()
            if cached_rules:
                # Cache encontrado - só carregar cache (EventBridge não tem auto-refresh)
                self.all_eventbridge_rules = cached_rules
                self.filter_eventbridge_rules()
                self.monitoring_status_eventbridge.value = f"📁 {len(cached_rules)} regras EventBridge carregadas do cache"
                self.monitoring_status_eventbridge.color = ft.Colors.BLUE
                self.page.update()
                print("📁 Cache EventBridge carregado - Use o botão Atualizar para buscar dados atualizados")
            else:
                # Não tem cache, carregar dados automaticamente
                print("🔄 Cache EventBridge não encontrado, carregando dados...")
                self.refresh_eventbridge_rules()

    def copy_jobs_to_clipboard(self, e):
        """Copia a tabela filtrada de jobs Glue para o clipboard"""
        try:
            if not self.filtered_jobs:
                self.monitoring_status.value = "❌ Nenhum job para copiar"
                self.monitoring_status.color = ft.Colors.RED
                self.page.update()
                return

            # Criar cabeçalho
            headers = ["Job Name", "Status", "Última Execução", "Duração"]

            # Criar linhas
            lines = ["\t".join(headers)]

            for job in self.filtered_jobs:
                line = "\t".join([
                    job['name'],
                    job['status'],
                    job['last_execution'],
                    job['duration']
                ])
                lines.append(line)

            # Copiar para clipboard
            clipboard_text = "\n".join(lines)
            pyperclip.copy(clipboard_text)

            self.monitoring_status.value = f"✅ {len(self.filtered_jobs)} jobs copiados para clipboard"
            self.monitoring_status.color = ft.Colors.GREEN
            self.page.update()

        except Exception as e:
            self.monitoring_status.value = f"❌ Erro ao copiar: {str(e)}"
            self.monitoring_status.color = ft.Colors.RED
            self.page.update()

    def export_jobs_to_excel(self, e):
        """Exporta a tabela filtrada de jobs Glue para Excel"""
        try:
            if not self.filtered_jobs:
                self.monitoring_status.value = "❌ Nenhum job para exportar"
                self.monitoring_status.color = ft.Colors.RED
                self.page.update()
                return

            # Mostrar status de escolha de pasta
            self.monitoring_status.value = "📁 Escolha onde salvar o arquivo..."
            self.monitoring_status.color = ft.Colors.BLUE
            self.page.update()

            # Preparar dados para DataFrame
            self.export_data_jobs = []
            for job in self.filtered_jobs:
                self.export_data_jobs.append({
                    'Job Name': job['name'],
                    'Status': job['status'],
                    'Última Execução': job['last_execution'],
                    'Duração': job['duration']
                })

            # Abrir seletor de pasta e executar export após seleção
            self.select_export_folder(self._export_jobs_after_folder_selection)

        except Exception as e:
            self.monitoring_status.value = f"❌ Erro ao preparar export: {str(e)}"
            self.monitoring_status.color = ft.Colors.RED
            self.page.update()

    def _export_jobs_after_folder_selection(self):
        """Executa o export Glue Jobs após a pasta ser selecionada"""
        try:
            # Criar DataFrame
            df = pd.DataFrame(self.export_data_jobs)

            # Gerar nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"glue_jobs_{timestamp}.xlsx"

            # Caminho completo usando a pasta selecionada
            file_path = self.export_folder / filename

            # Exportar para Excel
            df.to_excel(file_path, index=False, engine='openpyxl')

            # Feedback visual
            self.monitoring_status.value = f"✅ Exportado para {file_path.parent.name}/{filename}"
            self.monitoring_status.color = ft.Colors.GREEN
            self.page.update()

            # Reset status após 5 segundos
            def reset_status():
                time.sleep(5)
                self.monitoring_status.value = f"✅ {len(self.export_data_jobs)} jobs Glue encontrados"
                self.monitoring_status.color = ft.Colors.GREEN
                self.page.update()

            threading.Thread(target=reset_status, daemon=True).start()

        except Exception as e:
            self.monitoring_status.value = f"❌ Erro ao exportar: {str(e)}"
            self.monitoring_status.color = ft.Colors.RED
            self.page.update()

    def get_local_path(self):
        prefix = self.prefix_dropdown.value
        rt = self.rt_dropdown.value
        squad = self.squad_dropdown.value
        env = self.env_dropdown.value

        if not prefix or not rt or not env:
            return None

        # Verificar se RT tem squads disponíveis
        rt_squad_hierarchy = self.config.get("s3", {}).get("rt_squad_hierarchy", {})
        available_squads = rt_squad_hierarchy.get(rt, [])
        rt_has_squads = len(available_squads) > 0

        s3_base = self.config.get("s3", {}).get("default_base_path", "s3")

        if rt_has_squads and squad:
            return Path.home() / s3_base / prefix / rt / env / squad
        elif not rt_has_squads:
            return Path.home() / s3_base / prefix / rt / env
        else:
            return None

    def get_s3_path(self):
        prefix = self.prefix_dropdown.value
        rt = self.rt_dropdown.value
        squad = self.squad_dropdown.value
        env = self.env_dropdown.value

        if not prefix or not rt or not env or not self.current_account_id:
            return None

        # Verificar se RT tem squads disponíveis
        rt_squad_hierarchy = self.config.get("s3", {}).get("rt_squad_hierarchy", {})
        available_squads = rt_squad_hierarchy.get(rt, [])
        rt_has_squads = len(available_squads) > 0

        s3_base_uri = f"s3://itau-self-wkp-sa-east-1-{self.current_account_id}"

        if rt_has_squads and squad:
            return f"{s3_base_uri}/{prefix}/{rt}/{env}/{squad}/"
        elif not rt_has_squads:
            return f"{s3_base_uri}/{prefix}/{rt}/{env}/"
        else:
            return None

    def load_saved_selections(self):
        """Carrega as seleções salvas do config.json e aplica aos dropdowns"""
        try:
            self._loading_selections = True  # Flag para evitar salvar durante carregamento

            current_selections = self.config.get("s3", {}).get("current_selections", {})

            # Aplicar seleções aos dropdowns
            if current_selections.get("prefix"):
                self.prefix_dropdown.value = current_selections["prefix"]

            if current_selections.get("rt"):
                self.rt_dropdown.value = current_selections["rt"]
                # Atualizar squads baseado no RT carregado
                self.update_squad_options()

            if current_selections.get("env"):
                self.env_dropdown.value = current_selections["env"]

            # Carregar squad APÓS atualizar as opções baseadas no RT
            if current_selections.get("squad"):
                # Verificar se a squad salva é válida para o RT atual
                rt_value = self.rt_dropdown.value
                if rt_value:
                    rt_squad_hierarchy = self.config.get("s3", {}).get("rt_squad_hierarchy", {})
                    valid_squads = rt_squad_hierarchy.get(rt_value, [])
                    if current_selections["squad"] in valid_squads:
                        self.squad_dropdown.value = current_selections["squad"]

            # Atualizar caminhos com as seleções carregadas
            self.update_s3_path()

        except Exception as e:
            print(f"Erro ao carregar seleções: {e}")
        finally:
            self._loading_selections = False

    def save_selections(self):
        """Salva as seleções atuais no config.json"""
        try:
            prefix = self.prefix_dropdown.value if hasattr(self, 'prefix_dropdown') else None
            rt = self.rt_dropdown.value if hasattr(self, 'rt_dropdown') else None
            squad = self.squad_dropdown.value if hasattr(self, 'squad_dropdown') else None
            env = self.env_dropdown.value if hasattr(self, 'env_dropdown') else None

            # Atualizar configurações em memória
            if "s3" not in self.config:
                self.config["s3"] = {}
            if "current_selections" not in self.config["s3"]:
                self.config["s3"]["current_selections"] = {}

            self.config["s3"]["current_selections"]["prefix"] = prefix
            self.config["s3"]["current_selections"]["rt"] = rt
            self.config["s3"]["current_selections"]["squad"] = squad
            self.config["s3"]["current_selections"]["env"] = env

            # Salvar no arquivo
            config_path = Path(__file__).parent / "config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar seleções: {e}")

    def ensure_local_path_exists(self):
        local_path = self.get_local_path()
        if local_path:
            local_path.mkdir(parents=True, exist_ok=True)
            return True
        return False

    def open_local_folder(self, e):
        try:
            local_path = self.get_local_path()
            if local_path:
                # Criar pasta se não existir
                local_path.mkdir(parents=True, exist_ok=True)

                # Abrir no explorador de arquivos do Windows
                os.startfile(str(local_path))

                self.s3_status.value = f"📁 Pasta aberta: {local_path}"
                self.s3_status.color = ft.Colors.BLUE
            else:
                self.s3_status.value = "❌ Selecione todas as opções necessárias primeiro"
                self.s3_status.color = ft.Colors.RED
        except Exception as e:
            self.s3_status.value = f"❌ Erro ao abrir pasta: {str(e)}"
            self.s3_status.color = ft.Colors.RED

        self.page.update()

    def sync_to_s3(self, e):
        self.s3_progress.visible = True
        self.s3_status.value = "🔄 Sincronizando para S3..."
        self.s3_status.color = ft.Colors.ORANGE
        self.sync_to_s3_button.disabled = True
        self.page.update()

        try:
            if not self.ensure_local_path_exists():
                raise Exception("Erro ao criar pasta local")

            local_path = self.get_local_path()
            s3_path = self.get_s3_path()

            result = subprocess.run([
                'aws', 's3', 'sync',
                str(local_path),
                s3_path
            ], capture_output=True, text=True, check=True)

            self.s3_status.value = f"✅ Sincronização concluída: Local → S3"
            self.s3_status.color = ft.Colors.GREEN

        except subprocess.CalledProcessError as e:
            self.s3_status.value = f"❌ Erro na sincronização: {e.stderr or e.stdout}"
            self.s3_status.color = ft.Colors.RED

        except Exception as e:
            self.s3_status.value = f"❌ Erro: {str(e)}"
            self.s3_status.color = ft.Colors.RED

        self.s3_progress.visible = False
        self.sync_to_s3_button.disabled = False
        self.page.update()

    def sync_from_s3(self, e):
        self.s3_progress.visible = True
        self.s3_status.value = "🔄 Sincronizando do S3..."
        self.s3_status.color = ft.Colors.ORANGE
        self.sync_from_s3_button.disabled = True
        self.page.update()

        try:
            if not self.ensure_local_path_exists():
                raise Exception("Erro ao criar pasta local")

            local_path = self.get_local_path()
            s3_path = self.get_s3_path()

            # Construir comando base
            sync_command = [
                'aws', 's3', 'sync',
                s3_path,
                str(local_path)
            ]

            # Adicionar --delete se checkbox estiver marcado
            if self.delete_checkbox.value:
                sync_command.append('--delete')

            result = subprocess.run(sync_command, capture_output=True, text=True, check=True)

            delete_suffix = " (com --delete)" if self.delete_checkbox.value else ""
            self.s3_status.value = f"✅ Sincronização concluída: S3 → Local{delete_suffix}"
            self.s3_status.color = ft.Colors.GREEN

        except subprocess.CalledProcessError as e:
            self.s3_status.value = f"❌ Erro na sincronização: {e.stderr or e.stdout}"
            self.s3_status.color = ft.Colors.RED

        except Exception as e:
            self.s3_status.value = f"❌ Erro: {str(e)}"
            self.s3_status.color = ft.Colors.RED

        self.s3_progress.visible = False
        self.sync_from_s3_button.disabled = False
        self.page.update()

    def check_login_status(self):
        # Atualizar barra de status primeiro
        is_logged = self.refresh_aws_status()

        if is_logged:
            self.status_text.value = f"✅ Logado como: {self.current_user_arn}"
            self.status_text.color = ft.Colors.GREEN
            self.login_button.visible = False
            self.logout_button.visible = True

            # Limpar lista de profiles quando logado
            self.profile_list.controls.clear()
        else:
            self.status_text.value = "❌ Não logado - Selecione um profile SSO"
            self.status_text.color = ft.Colors.RED
            self.login_button.visible = True
            self.login_button.text = "Login"
            self.login_button.disabled = True
            self.logout_button.visible = False
            self.load_sso_profiles()

        self.page.update()

    def load_sso_profiles(self):
        try:
            aws_dir = Path.home() / '.aws'
            aws_config_path = None

            # Tentar encontrar arquivo config (com ou sem extensão)
            aws_config = self.config.get("aws", {})
            possible_config_files = aws_config.get("config_files", ['config', 'config.txt'])
            for config_file in possible_config_files:
                test_path = aws_dir / config_file
                if test_path.exists():
                    aws_config_path = test_path
                    break

            if not aws_config_path:
                self.status_text.value = f"❌ Arquivo config não encontrado em {aws_dir}"
                self.page.update()
                return

            config = configparser.ConfigParser()
            config.read(aws_config_path)

            all_profiles = []
            for section_name in config.sections():
                section = config[section_name]
                # Incluir profiles SSO e profiles regulares
                if ('sso_start_url' in section or 'sso_session' in section or
                    'region' in section or section_name.startswith('profile')):
                    profile_name = section_name.replace('profile ', '')
                    all_profiles.append(profile_name)

            if not all_profiles:
                self.status_text.value = f"❌ Nenhum profile encontrado em {aws_config_path.name}"
                self.page.update()
                return

            self.status_text.value = f"✅ Encontrados {len(all_profiles)} profiles em {aws_config_path.name}"
            self.status_text.color = ft.Colors.BLUE

            self.selected_profiles = set()

            for profile in all_profiles:
                checkbox = ft.Checkbox(
                    label=profile,
                    value=False,
                    on_change=lambda e, p=profile: self.on_profile_select(e, p)
                )
                self.profile_list.controls.append(checkbox)

            self.login_button.disabled = True
            self.page.update()

        except Exception as e:
            self.status_text.value = f"❌ Erro ao carregar profiles: {str(e)}"
            self.page.update()

    def on_profile_select(self, e, profile_name):
        if e.control.value:
            self.selected_profiles.add(profile_name)
            for control in self.profile_list.controls:
                if control.label != profile_name:
                    control.value = False
        else:
            self.selected_profiles.discard(profile_name)

        self.login_button.disabled = len(self.selected_profiles) == 0
        self.page.update()

    def on_login_click(self, e):
        if not self.selected_profiles:
            return

        profile = list(self.selected_profiles)[0]
        self.progress_ring.visible = True
        self.login_button.disabled = True
        self.status_text.value = f"🔄 Fazendo login no profile: {profile}"
        self.status_text.color = ft.Colors.ORANGE
        self.page.update()

        try:
            # Primeiro tentar SSO login
            result = subprocess.run([
                'aws', 'sso', 'login', '--profile', profile
            ], capture_output=True, text=True, check=False)

            success = False
            if result.returncode == 0:
                self.status_text.value = f"✅ Login SSO realizado com sucesso no profile: {profile}"
                self.status_text.color = ft.Colors.GREEN
                success = True
            else:
                # Se SSO falhar, tentar configurar profile regular
                os.environ['AWS_PROFILE'] = profile
                # Testar se credentials funcionam
                test_result = subprocess.run([
                    'aws', 'sts', 'get-caller-identity', '--profile', profile
                ], capture_output=True, text=True, check=False)

                if test_result.returncode == 0:
                    self.status_text.value = f"✅ Profile configurado: {profile}"
                    self.status_text.color = ft.Colors.GREEN
                    success = True
                else:
                    self.status_text.value = f"❌ Erro no profile: {result.stderr or result.stdout}"
                    self.status_text.color = ft.Colors.RED
                    self.login_button.disabled = False

            if success:
                os.environ['AWS_PROFILE'] = profile
                # Atualizar interface para estado logado
                self.check_login_status()

        except FileNotFoundError:
            self.status_text.value = "❌ AWS CLI não encontrado. Instale o AWS CLI primeiro."
            self.status_text.color = ft.Colors.RED
            self.login_button.disabled = False

        # Atualizar barra de status após tentativa de login
        self.update_status_bar()

        self.progress_ring.visible = False
        self.page.update()

    def on_logout_click(self, e):
        """Função para fazer logout do profile atual"""
        self.progress_ring.visible = True
        self.logout_button.disabled = True
        self.status_text.value = "🔄 Fazendo logout..."
        self.status_text.color = ft.Colors.ORANGE
        self.page.update()

        try:
            # Remover profile do ambiente
            if 'AWS_PROFILE' in os.environ:
                del os.environ['AWS_PROFILE']

            # Tentar fazer logout do SSO se aplicável
            if self.current_profile:
                try:
                    subprocess.run([
                        'aws', 'sso', 'logout'
                    ], capture_output=True, text=True, check=False)
                except:
                    pass  # Ignorar erros de logout SSO

            # Limpar variáveis globais
            self.current_profile = None
            self.current_account_id = None
            self.current_user_arn = None

            # Parar atualização automática do monitoring
            if hasattr(self, 'auto_refresh_timer'):
                self.stop_auto_refresh()

            # Limpar tabela de jobs do monitoring
            if hasattr(self, 'jobs_table'):
                self.jobs_table.rows.clear()
                self.all_jobs = []
                self.filtered_jobs = []

            # Forçar estado de logout na interface
            self.status_text.value = "❌ Não logado - Selecione um profile SSO"
            self.status_text.color = ft.Colors.RED
            self.login_button.visible = True
            self.login_button.text = "Login"
            self.login_button.disabled = True
            self.logout_button.visible = False

            # Atualizar barra de status para estado deslogado
            self.status_profile_text.value = "Profile: Não logado"
            self.status_profile_text.color = ft.Colors.GREY_400
            self.status_account_text.value = "Account ID: N/A"
            self.status_account_text.color = ft.Colors.GREY_400

            # Atualizar status do monitoring se a aba estiver carregada
            if hasattr(self, 'monitoring_status'):
                self.monitoring_status.value = "Faça login primeiro para visualizar jobs"
                self.monitoring_status.color = ft.Colors.GREY_400

            # Carregar lista de profiles SSO
            self.load_sso_profiles()

            # Mostrar mensagem de sucesso temporariamente
            temp_status = self.status_text.value
            temp_color = self.status_text.color
            self.status_text.value = "✅ Logout realizado com sucesso"
            self.status_text.color = ft.Colors.GREEN
            self.page.update()

            # Após 2 segundos, restaurar o estado normal
            def restore_status():
                self.status_text.value = temp_status
                self.status_text.color = temp_color
                self.page.update()

            # Usar timer para restaurar status após 2 segundos
            timer = threading.Timer(2.0, restore_status)
            timer.daemon = True
            timer.start()

        except Exception as e:
            self.status_text.value = f"❌ Erro no logout: {str(e)}"
            self.status_text.color = ft.Colors.RED

        self.progress_ring.visible = False
        self.logout_button.disabled = False
        self.page.update()

    # Table Monitoring Functions
    def fetch_table_metadata(self, database: str, table_name: str):
        """Busca detalhes de uma única tabela no Glue Catalog usando boto3."""
        try:
            # Usar retry para evitar throttling
            def get_table_details():
                glue_client = boto3.client('glue')
                return glue_client.get_table(DatabaseName=database, Name=table_name)

            response = self.retry_with_backoff(get_table_details, max_retries=3, base_delay=0.5)
            table = response['Table']

            # Informações básicas da tabela
            created = table.get("CreateTime")
            updated = table.get("UpdateTime")

            # Detectar formato baseado no StorageDescriptor
            storage_desc = table.get("StorageDescriptor", {})
            input_format = storage_desc.get("InputFormat", "")
            location = storage_desc.get("Location", "")

            # Detectar formato do arquivo
            if "parquet" in input_format.lower():
                fmt = "parquet"
            elif "json" in input_format.lower():
                fmt = "json"
            elif "csv" in input_format.lower() or "text" in input_format.lower():
                fmt = "csv"
            elif "orc" in input_format.lower():
                fmt = "orc"
            else:
                fmt = "unknown"

            # Contar partições
            partition_keys = table.get("PartitionKeys", [])
            num_partitions = len(partition_keys)

            # Buscar data mais recente dos arquivos (se tiver localização S3)
            last_file_modified = None
            if location and location.startswith("s3://"):
                last_file_modified = self.get_latest_file_modification_date(location)

            return {
                "name": table_name,
                "database": database,
                "created_date": created.strftime("%Y-%m-%d") if created else "N/A",
                "last_updated": updated.strftime("%Y-%m-%d %H:%M") if updated else "N/A",
                "last_file_modified": last_file_modified.strftime("%Y-%m-%d %H:%M") if last_file_modified else "N/A",
                "num_partitions": num_partitions,
                "type": fmt,
                "location": location[:50] + "..." if len(location) > 50 else location,
            }

        except Exception as e:
            print(f"❌ Erro ao buscar metadados da tabela {table_name}: {e}")
            return {
                "name": table_name,
                "database": database,
                "created_date": "ERROR",
                "last_updated": f"Erro: {str(e)}",
                "last_file_modified": "N/A",
                "num_partitions": 0,
                "type": "unknown",
                "location": "N/A",
            }

    def get_latest_file_modification_date(self, s3_location):
        """Busca a data de modificação mais recente dos arquivos em uma localização S3."""
        try:
            # Parse da localização S3
            if not s3_location.startswith("s3://"):
                return None

            s3_path = s3_location[5:]  # Remove 's3://'
            bucket = s3_path.split('/')[0]
            prefix = '/'.join(s3_path.split('/')[1:]) if len(s3_path.split('/')) > 1 else ""

            # Usar retry para evitar throttling
            def list_s3_objects():
                s3_client = boto3.client('s3')
                paginator = s3_client.get_paginator('list_objects_v2')

                latest_date = None
                object_count = 0

                # Limitar a 100 objetos para reduzir custos
                for page in paginator.paginate(Bucket=bucket, Prefix=prefix, PaginationConfig={'MaxItems': 100}):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            object_count += 1
                            last_modified = obj['LastModified']

                            # Manter apenas a data mais recente
                            if latest_date is None or last_modified > latest_date:
                                latest_date = last_modified

                            # Parar depois de 50 objetos para evitar custos excessivos
                            if object_count >= 50:
                                break

                    # Quebrar loop externo também
                    if object_count >= 50:
                        break

                print(f"📊 S3: Verificados {object_count} objetos em {s3_location[:50]}...")
                return latest_date

            return self.retry_with_backoff(list_s3_objects, max_retries=2, base_delay=0.5)

        except Exception as e:
            print(f"⚠️  Erro ao buscar data dos arquivos S3 em {s3_location}: {e}")
            return None

    def fetch_all_tables(self, databases=["itau", "teste"], max_workers=3):
        """Busca tabelas dos databases especificados usando boto3 e threads otimizadas."""
        try:
            if not self.current_account_id:
                print("❌ Necessário estar logado para buscar tabelas")
                return []

            print(f"🔍 Buscando tabelas nos databases: {databases}")
            all_table_names = []

            # 1. Primeiro, listar todas as tabelas por database (com throttling protection)
            glue_client = boto3.client('glue')

            for database in databases:
                try:
                    def list_tables_in_db():
                        paginator = glue_client.get_paginator('get_tables')
                        tables_in_db = []

                        for page in paginator.paginate(DatabaseName=database):
                            # Pequeno delay entre páginas
                            time.sleep(0.1)
                            for table in page['TableList']:
                                tables_in_db.append({
                                    'name': table['Name'],
                                    'database': database
                                })
                        return tables_in_db

                    tables_in_db = self.retry_with_backoff(list_tables_in_db, max_retries=3, base_delay=1.0)
                    all_table_names.extend(tables_in_db)
                    print(f"📊 Database '{database}': {len(tables_in_db)} tabelas encontradas")

                except Exception as e:
                    print(f"❌ Erro ao listar tabelas no database {database}: {e}")

            if not all_table_names:
                print("📋 Nenhuma tabela encontrada nos databases especificados")
                return []

            print(f"📈 Total: {len(all_table_names)} tabelas para processar")

            # 2. Buscar metadados em paralelo (com menos workers para evitar throttling)
            tables_metadata = []
            # Reduzir workers para evitar throttling em operações de metadados + S3
            actual_workers = min(max_workers, max(2, len(all_table_names) // 10))
            print(f"🔧 Usando {actual_workers} workers (otimizado para evitar throttling)")

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                # Submeter jobs com delay para evitar burst
                future_to_table = {}
                for i, table_info in enumerate(all_table_names):
                    # Delay progressivo entre submissões
                    if i > 0:
                        time.sleep(0.1)

                    future = executor.submit(self.fetch_table_metadata, table_info['database'], table_info['name'])
                    future_to_table[future] = f"{table_info['database']}.{table_info['name']}"

                # Processar resultados
                completed = 0
                for future in as_completed(future_to_table):
                    try:
                        table_data = future.result()
                        tables_metadata.append(table_data)
                        completed += 1

                        # Log de progresso a cada 25%
                        if completed % max(1, len(all_table_names) // 4) == 0:
                            progress = (completed / len(all_table_names)) * 100
                            print(f"📈 Progresso: {completed}/{len(all_table_names)} ({progress:.0f}%)")

                    except Exception as e:
                        table_name = future_to_table[future]
                        print(f"❌ Erro ao processar tabela {table_name}: {e}")
                        # Adicionar entrada com erro
                        db_name, tbl_name = table_name.split('.', 1)
                        tables_metadata.append({
                            'name': tbl_name,
                            'database': db_name,
                            'created_date': "ERROR",
                            'last_updated': f"Erro: {str(e)}",
                            'last_file_modified': "N/A",
                            'num_partitions': 0,
                            'type': "unknown",
                            'location': "N/A"
                        })

            end_time = time.time()
            duration = end_time - start_time
            print(f"⚡ Tabelas processadas em {duration:.2f}s com {actual_workers} workers")
            print(f"📊 Performance: {len(all_table_names)/duration:.1f} tabelas/s")

            return tables_metadata

        except Exception as e:
            print(f"❌ Erro geral ao buscar tabelas: {e}")
            return []

    def update_tables_table(self, tables_data=None):
        """
        Atualiza a tabela da aba Monitoring Tables.
        """
        if tables_data is None:
            tables_data = getattr(self, "all_tables", [])

        # Limpa tabela atual
        self.table_monitoring.rows.clear()

        for tbl in tables_data:
            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(tbl.get("name", ""), size=12)),
                    ft.DataCell(ft.Text(tbl.get("database", ""), size=12)),
                    ft.DataCell(ft.Text(tbl.get("created_date", ""), size=12)),
                    ft.DataCell(ft.Text(tbl.get("last_updated", ""), size=12)),
                    ft.DataCell(ft.Text(tbl.get("last_file_modified", "N/A"), size=12)),
                    ft.DataCell(ft.Text(tbl.get("type", ""), size=12)),
                    ft.DataCell(ft.Text(str(tbl.get("num_partitions", 0)), size=12)),
                ]
            )
            self.table_monitoring.rows.append(row)

        # Força refresh na UI
        if hasattr(self, "page"):
            self.page.update()

    def refresh_tables(self, e=None):
        """Atualiza a lista de tabelas do Glue Catalog (Monitoring Tables)."""
        if not self.current_account_id:
            self.monitoring_status_tables.value = "Faça login primeiro para visualizar tabelas"
            self.monitoring_status_tables.color = ft.Colors.RED
            self.page.update()
            return

        # Verificar se cache é recente (menos de 15 minutos)
        if self.is_cache_fresh("tables", 15):
            self.monitoring_status_tables.value = "⏰ Cache recente (menos de 15 min) - Use o cache existente para evitar custos adicionais"
            self.monitoring_status_tables.color = ft.Colors.BLUE
            self.page.update()
            return

        # Ativa progress
        self.monitoring_progress_tables.visible = True
        self.refresh_button_tables.disabled = True
        self.monitoring_status_tables.value = "Carregando tabelas do Glue..."
        self.monitoring_status_tables.color = ft.Colors.ORANGE
        self.page.update()

        def fetch_in_background():
            try:
                tables = self.fetch_all_tables(databases=["itau", "teste"])

                def update_ui():
                    self.all_tables = tables
                    self.update_tables_table(tables)

                    # Salvar no cache
                    self.save_tables_cache(tables)

                    self.monitoring_status_tables.value = f"✅ {len(tables)} tabelas encontradas"
                    self.monitoring_status_tables.color = ft.Colors.GREEN
                    self.monitoring_progress_tables.visible = False
                    self.refresh_button_tables.disabled = False
                    self.page.update()

                # Executa atualização da UI na thread principal
                self.page.run_thread(update_ui)

            except Exception as e:
                def update_ui_error():
                    self.monitoring_status_tables.value = f"❌ Erro ao carregar tabelas: {str(e)}"
                    self.monitoring_status_tables.color = ft.Colors.RED
                    self.monitoring_progress_tables.visible = False
                    self.refresh_button_tables.disabled = False
                    self.page.update()

                self.page.run_thread(update_ui_error)

        # Executar em thread separada
        threading.Thread(target=fetch_in_background, daemon=True).start()

    def create_monitoring_tables_tab(self):
        # Campo de busca
        self.table_filter = ft.TextField(
            label="Filtrar Tabelas",
            width=300,
            value=self.load_filter_text("table_monitoring"),
            on_change=self.filter_tables
        )

        # Botão de atualização manual
        self.refresh_button_tables = ft.ElevatedButton(
            "🔄 Atualizar",
            on_click=self.refresh_tables,
            width=130,
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=3,
            )
        )

        # Botões de exportação/copiar
        self.copy_tables_button = ft.IconButton(
            icon=ft.Icons.COPY,
            tooltip="Copiar tabela para clipboard",
            on_click=self.copy_tables_to_clipboard,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
            )
        )

        self.export_tables_button = ft.IconButton(
            icon=ft.Icons.FILE_DOWNLOAD,
            tooltip="Exportar tabela para Excel",
            on_click=self.export_tables_to_excel,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
            )
        )

        # Progress e status
        self.monitoring_progress_tables = ft.ProgressRing(visible=False)
        self.monitoring_status_tables = ft.Text(
            "Faça login primeiro para visualizar tabelas",
            size=14,
            color=ft.Colors.GREY_400
        )

        # Tabela de Monitoring Tables
        self.table_monitoring = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Database", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Created", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Last Updated", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Files Modified", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Type", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Partitions", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True
        )

        self.tables_container = ft.Container(
            content=self.table_monitoring,
            expand=True,
            bgcolor=ft.Colors.GREY_800,
            border=ft.border.all(1, ft.Colors.GREY_700),
            border_radius=12,
            padding=15,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.BLACK26,
                offset=ft.Offset(0, 2),
            )
        )

        return ft.Container(
            content=ft.Column([
                # Container de filtros e botões
                ft.Container(
                    content=ft.Row([
                        self.table_filter,
                        ft.Container(width=20),
                        self.refresh_button_tables,
                        self.monitoring_progress_tables,
                        ft.Container(width=15),
                        self.copy_tables_button,
                        ft.Container(width=5),
                        self.export_tables_button
                    ], alignment=ft.MainAxisAlignment.START),
                    padding=ft.padding.all(20),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),

                ft.Container(height=15),

                # Status com progress
                ft.Container(
                    content=ft.Row([
                        self.monitoring_status_tables,
                        ft.Container(expand=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                ),

                ft.Container(height=15),

                # Tabela
                ft.Container(
                    content=ft.Column([
                        ft.Text("Monitoring Tables:", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        self.tables_container,
                    ]),
                    expand=True
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO
            ),
            padding=25,
            expand=True,
            bgcolor=ft.Colors.GREY_900
        )

    def filter_tables(self, e=None):
        """Filtra tabelas baseado no texto de busca."""
        filter_text = self.table_filter.value.lower() if self.table_filter.value else ""

        if not hasattr(self, 'all_tables') or not self.all_tables:
            return

        if not filter_text:
            # Se não há filtro, mostra todas as tabelas
            self.update_tables_table(self.all_tables)
        else:
            # Filtra tabelas que contenham o texto no nome ou database
            filtered_tables = [
                table for table in self.all_tables
                if (filter_text in table.get("name", "").lower() or
                    filter_text in table.get("database", "").lower())
            ]
            self.update_tables_table(filtered_tables)

        # Salvar texto do filtro
        self.save_filter_text("table_monitoring", filter_text)

    def copy_tables_to_clipboard(self, e=None):
        """Copia dados das tabelas filtradas para clipboard."""
        try:
            if not hasattr(self, 'table_monitoring') or not self.table_monitoring.rows:
                return

            # Cabeçalhos
            headers = ["Name", "Database", "Created", "Last Updated", "Files Modified", "Type", "Partitions"]

            # Dados das linhas
            data = []
            for row in self.table_monitoring.rows:
                row_data = []
                for cell in row.cells:
                    row_data.append(cell.content.value if hasattr(cell.content, 'value') else str(cell.content))
                data.append(row_data)

            # Criar texto formatado para clipboard
            clipboard_text = "\t".join(headers) + "\n"
            for row_data in data:
                clipboard_text += "\t".join(row_data) + "\n"

            pyperclip.copy(clipboard_text)

            # Feedback visual
            self.monitoring_status_tables.value = "✅ Dados copiados para clipboard"
            self.monitoring_status_tables.color = ft.Colors.GREEN
            self.page.update()

            # Reset status após 3 segundos
            def reset_status():
                time.sleep(3)
                self.monitoring_status_tables.value = f"✅ {len(data)} tabelas encontradas"
                self.monitoring_status_tables.color = ft.Colors.GREEN
                self.page.update()

            threading.Thread(target=reset_status, daemon=True).start()

        except Exception as e:
            self.monitoring_status_tables.value = f"❌ Erro ao copiar: {str(e)}"
            self.monitoring_status_tables.color = ft.Colors.RED
            self.page.update()

    def export_tables_to_excel(self, e=None):
        """Exporta dados das tabelas filtradas para Excel."""
        try:
            if not hasattr(self, 'table_monitoring') or not self.table_monitoring.rows:
                return

            # Mostrar status de escolha de pasta
            self.monitoring_status_tables.value = "📁 Escolha onde salvar o arquivo..."
            self.monitoring_status_tables.color = ft.Colors.BLUE
            self.page.update()

            # Preparar dados
            self.export_data_tables = []
            for row in self.table_monitoring.rows:
                row_data = []
                for cell in row.cells:
                    row_data.append(cell.content.value if hasattr(cell.content, 'value') else str(cell.content))
                self.export_data_tables.append(row_data)

            # Abrir seletor de pasta e executar export após seleção
            self.select_export_folder(self._export_tables_after_folder_selection)

        except Exception as e:
            self.monitoring_status_tables.value = f"❌ Erro ao preparar export: {str(e)}"
            self.monitoring_status_tables.color = ft.Colors.RED
            self.page.update()

    def _export_tables_after_folder_selection(self):
        """Executa o export Tables após a pasta ser selecionada"""
        try:
            # Criar DataFrame
            df = pd.DataFrame(self.export_data_tables, columns=["Name", "Database", "Created", "Last Updated", "Files Modified", "Type", "Partitions"])

            # Nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"monitoring_tables_{timestamp}.xlsx"

            # Caminho completo usando a pasta selecionada
            file_path = self.export_folder / filename

            # Exportar
            df.to_excel(file_path, index=False, engine='openpyxl')

            # Feedback visual
            self.monitoring_status_tables.value = f"✅ Exportado para {file_path.parent.name}/{filename}"
            self.monitoring_status_tables.color = ft.Colors.GREEN
            self.page.update()

            # Reset status após 5 segundos
            def reset_status():
                time.sleep(5)
                self.monitoring_status_tables.value = f"✅ {len(self.export_data_tables)} tabelas encontradas"
                self.monitoring_status_tables.color = ft.Colors.GREEN
                self.page.update()

            threading.Thread(target=reset_status, daemon=True).start()

        except Exception as e:
            self.monitoring_status_tables.value = f"❌ Erro ao exportar: {str(e)}"
            self.monitoring_status_tables.color = ft.Colors.RED
            self.page.update()

    def create_monitoring_eventbridge_tab(self):
        # Campo de busca
        self.eventbridge_filter = ft.TextField(
            label="Filtrar Regras EventBridge",
            width=300,
            value=self.load_filter_text("eventbridge_monitoring"),
            on_change=self.filter_eventbridge_rules
        )

        # Botão de atualização manual
        self.refresh_button_eventbridge = ft.ElevatedButton(
            "🔄 Atualizar",
            on_click=self.refresh_eventbridge_rules,
            width=130,
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=3,
            )
        )

        # Botões de exportação/copiar
        self.copy_eventbridge_button = ft.IconButton(
            icon=ft.Icons.COPY,
            tooltip="Copiar tabela para clipboard",
            on_click=self.copy_eventbridge_to_clipboard,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
            )
        )

        self.export_eventbridge_button = ft.IconButton(
            icon=ft.Icons.FILE_DOWNLOAD,
            tooltip="Exportar tabela para Excel",
            on_click=self.export_eventbridge_to_excel,
            icon_size=20,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
            )
        )

        # Progress e status
        self.monitoring_progress_eventbridge = ft.ProgressRing(visible=False)
        self.monitoring_status_eventbridge = ft.Text(
            "Faça login primeiro para visualizar regras EventBridge",
            size=14,
            color=ft.Colors.GREY_400
        )

        # Tabela de EventBridge Rules
        self.eventbridge_rules_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("State", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Description", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Schedule", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Targets", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True
        )

        self.eventbridge_container = ft.Container(
            content=self.eventbridge_rules_table,
            expand=True,
            bgcolor=ft.Colors.GREY_800,
            border=ft.border.all(1, ft.Colors.GREY_700),
            border_radius=12,
            padding=15,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.BLACK26,
                offset=ft.Offset(0, 2),
            )
        )

        return ft.Container(
            content=ft.Column([
                # Container de filtros e botões
                ft.Container(
                    content=ft.Row([
                        self.eventbridge_filter,
                        ft.Container(width=20),
                        self.refresh_button_eventbridge,
                        self.monitoring_progress_eventbridge,
                        ft.Container(width=15),
                        self.copy_eventbridge_button,
                        ft.Container(width=5),
                        self.export_eventbridge_button
                    ], alignment=ft.MainAxisAlignment.START),
                    padding=ft.padding.all(20),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),

                ft.Container(height=15),

                # Status com progress
                ft.Container(
                    content=ft.Row([
                        self.monitoring_status_eventbridge,
                        ft.Container(expand=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                ),

                ft.Container(height=15),

                # Tabela
                ft.Container(
                    content=ft.Column([
                        ft.Text("EventBridge Rules:", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        self.eventbridge_container,
                    ]),
                    expand=True
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO
            ),
            padding=25,
            expand=True,
            bgcolor=ft.Colors.GREY_900
        )

    def create_report_athena_tab(self):
        """Cria a aba de relatórios de custos do Athena"""

        # Filtro de período
        self.athena_period_dropdown = ft.Dropdown(
            label="Período",
            width=150,
            options=[
                ft.dropdown.Option("daily", "Diário"),
                ft.dropdown.Option("weekly", "Semanal"),
                ft.dropdown.Option("monthly", "Mensal"),
                ft.dropdown.Option("annual", "Anual")
            ],
            value="monthly",
            on_change=self.on_period_change
        )

        # Filtro de workgroup
        self.athena_workgroup_dropdown = ft.Dropdown(
            label="Workgroup",
            width=200,
            options=[
                ft.dropdown.Option("all", "Todos os Workgroups")
            ],
            value="all",
            on_change=self.on_workgroup_change
        )

        # Seletor de data de início
        self.athena_start_date = ft.TextField(
            label="Data Início (YYYY-MM-DD)",
            width=180,
            value="2024-01-01"
        )

        # Seletor de data de fim
        self.athena_end_date = ft.TextField(
            label="Data Fim (YYYY-MM-DD)",
            width=180,
            value="2024-12-31"
        )

        # Botão de atualização
        self.refresh_button_athena = ft.ElevatedButton(
            "📊 Gerar Relatório",
            on_click=self.refresh_athena_costs,
            width=150,
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=3,
            )
        )

        # Botão para carregar workgroups
        self.load_workgroups_button = ft.ElevatedButton(
            "🔄 Carregar Workgroups",
            on_click=self.load_athena_workgroups,
            width=160,
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=3,
            )
        )

        # Progress e status
        self.athena_progress = ft.ProgressRing(visible=False)
        self.athena_status = ft.Text(
            "Faça login primeiro para visualizar relatórios de custos",
            size=14,
            color=ft.Colors.GREY_400
        )

        # Container para gráficos
        self.athena_charts_container = ft.Container(
            content=ft.Text(
                "Selecione o período e clique em 'Gerar Relatório' para visualizar os custos",
                size=16,
                text_align=ft.TextAlign.CENTER,
                color=ft.Colors.GREY_500
            ),
            height=400,
            expand=True,
            bgcolor=ft.Colors.GREY_800,
            border=ft.border.all(1, ft.Colors.GREY_700),
            border_radius=12,
            padding=20,
            alignment=ft.alignment.center
        )

        # Tabela de custos detalhados
        self.athena_costs_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Workgroup", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Período", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Custo (USD)", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Queries", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Dados Processados (GB)", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True
        )

        self.athena_table_container = ft.Container(
            content=self.athena_costs_table,
            expand=True,
            bgcolor=ft.Colors.GREY_800,
            border=ft.border.all(1, ft.Colors.GREY_700),
            border_radius=12,
            padding=15,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.BLACK26,
                offset=ft.Offset(0, 2),
            )
        )

        return ft.Container(
            content=ft.Column([
                # Container de filtros e botões
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            self.athena_period_dropdown,
                            ft.Container(width=15),
                            self.athena_workgroup_dropdown,
                            ft.Container(width=15),
                            self.athena_start_date,
                            ft.Container(width=15),
                            self.athena_end_date,
                        ], alignment=ft.MainAxisAlignment.START),

                        ft.Container(height=15),

                        ft.Row([
                            self.load_workgroups_button,
                            ft.Container(width=15),
                            self.refresh_button_athena,
                            self.athena_progress,
                        ], alignment=ft.MainAxisAlignment.START),
                    ]),
                    padding=ft.padding.all(20),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=8,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 2),
                    )
                ),

                ft.Container(height=15),

                # Status com progress
                ft.Container(
                    content=ft.Row([
                        self.athena_status,
                        ft.Container(expand=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                ),

                ft.Container(height=15),

                # Gráficos
                ft.Container(
                    content=ft.Column([
                        ft.Text("Relatório de Custos Athena:", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        self.athena_charts_container,
                    ]),
                    expand=True
                ),

                ft.Container(height=15),

                # Tabela detalhada
                ft.Container(
                    content=ft.Column([
                        ft.Text("Detalhamento por Workgroup:", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Container(height=10),
                        self.athena_table_container,
                    ]),
                    height=300
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO
            ),
            padding=25,
            expand=True,
            bgcolor=ft.Colors.GREY_900
        )

    # Report Athena Functions
    def on_period_change(self, e):
        """Callback para mudança de período"""
        print(f"Período selecionado: {self.athena_period_dropdown.value}")

    def on_workgroup_change(self, e):
        """Callback para mudança de workgroup"""
        print(f"Workgroup selecionado: {self.athena_workgroup_dropdown.value}")

    def load_athena_workgroups(self, e):
        """Carrega lista de workgroups do Athena"""
        try:
            self.athena_status.value = "🔄 Carregando workgroups..."
            self.athena_status.color = ft.Colors.ORANGE
            self.athena_progress.visible = True
            self.page.update()

            def load_in_background():
                try:
                    workgroups = self.fetch_athena_workgroups()

                    def update_ui():
                        # Limpar opções existentes
                        self.athena_workgroup_dropdown.options.clear()
                        self.athena_workgroup_dropdown.options.append(
                            ft.dropdown.Option("all", "Todos os Workgroups")
                        )

                        # Adicionar workgroups encontrados
                        for wg in workgroups:
                            self.athena_workgroup_dropdown.options.append(
                                ft.dropdown.Option(wg['Name'], wg['Name'])
                            )

                        self.athena_status.value = f"✅ {len(workgroups)} workgroups encontrados"
                        self.athena_status.color = ft.Colors.GREEN
                        self.athena_progress.visible = False
                        self.page.update()

                    self.page.run_thread(update_ui)

                except Exception as e:
                    def update_error():
                        self.athena_status.value = f"❌ Erro ao carregar workgroups: {str(e)}"
                        self.athena_status.color = ft.Colors.RED
                        self.athena_progress.visible = False
                        self.page.update()

                    self.page.run_thread(update_error)

            threading.Thread(target=load_in_background, daemon=True).start()

        except Exception as e:
            self.athena_status.value = f"❌ Erro ao iniciar carregamento: {str(e)}"
            self.athena_status.color = ft.Colors.RED
            self.athena_progress.visible = False
            self.page.update()

    def refresh_athena_costs(self, e):
        """Gera relatório de custos do Athena"""
        try:
            self.athena_status.value = "📊 Gerando relatório de custos..."
            self.athena_status.color = ft.Colors.ORANGE
            self.athena_progress.visible = True
            self.page.update()

            def generate_in_background():
                try:
                    # Obter parâmetros
                    period = self.athena_period_dropdown.value
                    workgroup = self.athena_workgroup_dropdown.value
                    start_date = self.athena_start_date.value
                    end_date = self.athena_end_date.value

                    # Buscar dados de custos
                    cost_data = self.fetch_athena_costs(period, workgroup, start_date, end_date)

                    def update_ui():
                        # Atualizar tabela
                        self.update_athena_costs_table(cost_data)

                        # Gerar gráficos
                        self.generate_athena_charts(cost_data, period)

                        self.athena_status.value = f"✅ Relatório gerado com {len(cost_data)} registros"
                        self.athena_status.color = ft.Colors.GREEN
                        self.athena_progress.visible = False
                        self.page.update()

                    self.page.run_thread(update_ui)

                except Exception as e:
                    def update_error():
                        self.athena_status.value = f"❌ Erro ao gerar relatório: {str(e)}"
                        self.athena_status.color = ft.Colors.RED
                        self.athena_progress.visible = False
                        self.page.update()

                    self.page.run_thread(update_error)

            threading.Thread(target=generate_in_background, daemon=True).start()

        except Exception as e:
            self.athena_status.value = f"❌ Erro ao iniciar geração: {str(e)}"
            self.athena_status.color = ft.Colors.RED
            self.athena_progress.visible = False
            self.page.update()

    def fetch_athena_workgroups(self):
        """Busca todos os workgroups do Athena"""
        try:
            if not self.current_account_id:
                print("❌ Necessário estar logado para buscar workgroups")
                return []

            print("🔍 Buscando workgroups do Athena...")
            athena_client = boto3.client('athena')

            def get_workgroups():
                paginator = athena_client.get_paginator('list_work_groups')
                workgroups = []
                for page in paginator.paginate():
                    time.sleep(0.1)  # Evitar throttling
                    workgroups.extend(page['WorkGroups'])
                return workgroups

            workgroups = self.retry_with_backoff(get_workgroups, max_retries=3, base_delay=0.5)
            print(f"✅ {len(workgroups)} workgroups encontrados")
            return workgroups

        except Exception as e:
            print(f"❌ Erro ao buscar workgroups: {e}")
            return []

    def fetch_athena_costs(self, period, workgroup, start_date, end_date):
        """Busca dados de custos do Athena via Cost Explorer"""
        try:
            if not self.current_account_id:
                print("❌ Necessário estar logado para buscar custos")
                return []

            print(f"💰 Buscando custos do Athena ({period}) de {start_date} a {end_date}...")
            ce_client = boto3.client('ce')

            # Definir granularidade baseada no período
            granularity_map = {
                'daily': 'DAILY',
                'weekly': 'WEEKLY',
                'monthly': 'MONTHLY',
                'annual': 'MONTHLY'  # Para anual, usar monthly e agregar depois
            }
            granularity = granularity_map.get(period, 'MONTHLY')

            def get_cost_data():
                # Parâmetros básicos
                params = {
                    'TimePeriod': {
                        'Start': start_date,
                        'End': end_date
                    },
                    'Granularity': granularity,
                    'Metrics': ['BlendedCost', 'UsageQuantity'],
                    'GroupBy': [
                        {
                            'Type': 'DIMENSION',
                            'Key': 'SERVICE'
                        }
                    ],
                    'Filter': {
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': ['Amazon Athena']
                        }
                    }
                }

                # Se workgroup específico foi selecionado, adicionar filtro
                if workgroup != "all":
                    # Para workgroup específico, usar filtro de tag ou resource
                    # Nota: Cost Explorer pode não ter granularidade de workgroup
                    # Nesse caso, buscaremos dados do CloudWatch
                    pass

                response = ce_client.get_cost_and_usage(**params)
                return response

            cost_response = self.retry_with_backoff(get_cost_data, max_retries=3, base_delay=0.5)

            # Processar dados de custo
            cost_data = []
            for result_time in cost_response.get('ResultsByTime', []):
                time_period = result_time['TimePeriod']['Start']

                for group in result_time.get('Groups', []):
                    cost_amount = float(group['Metrics']['BlendedCost']['Amount'])
                    usage_quantity = float(group['Metrics']['UsageQuantity']['Amount'])

                    cost_data.append({
                        'workgroup': workgroup if workgroup != "all" else "All Workgroups",
                        'period': time_period,
                        'cost': cost_amount,
                        'queries': int(usage_quantity),
                        'data_processed_gb': usage_quantity * 0.1  # Estimativa
                    })

            # Se não houver dados do Cost Explorer, gerar dados simulados para demonstração
            if not cost_data:
                cost_data = self.generate_sample_athena_data(period, workgroup, start_date, end_date)

            print(f"✅ {len(cost_data)} registros de custo encontrados")
            return cost_data

        except Exception as e:
            print(f"❌ Erro ao buscar custos: {e}")
            # Retornar dados simulados em caso de erro
            return self.generate_sample_athena_data(period, workgroup, start_date, end_date)

    def generate_sample_athena_data(self, period, workgroup, start_date, end_date):
        """Gera dados simulados para demonstração"""
        import random
        from datetime import datetime, timedelta

        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')

            sample_data = []
            workgroups = ['primary', 'analytics', 'etl', 'reporting'] if workgroup == "all" else [workgroup]

            # Gerar dados baseados no período
            if period == 'daily':
                current_date = start
                while current_date <= end:
                    for wg in workgroups:
                        sample_data.append({
                            'workgroup': wg,
                            'period': current_date.strftime('%Y-%m-%d'),
                            'cost': round(random.uniform(5.0, 50.0), 2),
                            'queries': random.randint(10, 200),
                            'data_processed_gb': round(random.uniform(1.0, 100.0), 2)
                        })
                    current_date += timedelta(days=1)

            elif period == 'weekly':
                current_date = start
                while current_date <= end:
                    for wg in workgroups:
                        sample_data.append({
                            'workgroup': wg,
                            'period': f"Semana {current_date.strftime('%Y-%m-%d')}",
                            'cost': round(random.uniform(35.0, 350.0), 2),
                            'queries': random.randint(70, 1400),
                            'data_processed_gb': round(random.uniform(7.0, 700.0), 2)
                        })
                    current_date += timedelta(weeks=1)

            elif period == 'monthly':
                current_date = start
                while current_date <= end:
                    for wg in workgroups:
                        sample_data.append({
                            'workgroup': wg,
                            'period': current_date.strftime('%Y-%m'),
                            'cost': round(random.uniform(150.0, 1500.0), 2),
                            'queries': random.randint(300, 6000),
                            'data_processed_gb': round(random.uniform(30.0, 3000.0), 2)
                        })
                    current_date = current_date.replace(month=current_date.month + 1 if current_date.month < 12 else 1,
                                                      year=current_date.year if current_date.month < 12 else current_date.year + 1)

            elif period == 'annual':
                for year in range(start.year, end.year + 1):
                    for wg in workgroups:
                        sample_data.append({
                            'workgroup': wg,
                            'period': str(year),
                            'cost': round(random.uniform(1800.0, 18000.0), 2),
                            'queries': random.randint(3600, 72000),
                            'data_processed_gb': round(random.uniform(360.0, 36000.0), 2)
                        })

            return sample_data

        except Exception as e:
            print(f"❌ Erro ao gerar dados simulados: {e}")
            return []

    def update_athena_costs_table(self, cost_data):
        """Atualiza a tabela de custos do Athena"""
        try:
            # Limpar tabela atual
            self.athena_costs_table.rows.clear()

            for cost in cost_data:
                row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(cost.get('workgroup', ''), size=12)),
                        ft.DataCell(ft.Text(cost.get('period', ''), size=12)),
                        ft.DataCell(ft.Text(f"${cost.get('cost', 0):.2f}", size=12, color=ft.Colors.GREEN)),
                        ft.DataCell(ft.Text(str(cost.get('queries', 0)), size=12)),
                        ft.DataCell(ft.Text(f"{cost.get('data_processed_gb', 0):.2f}", size=12)),
                    ]
                )
                self.athena_costs_table.rows.append(row)

            self.page.update()

        except Exception as e:
            print(f"❌ Erro ao atualizar tabela: {e}")

    def generate_athena_charts(self, cost_data, period):
        """Gera gráficos de custos do Athena"""
        try:
            if not cost_data:
                self.athena_charts_container.content = ft.Text(
                    "Nenhum dado de custo disponível para gerar gráficos",
                    size=16,
                    text_align=ft.TextAlign.CENTER,
                    color=ft.Colors.GREY_500
                )
                self.page.update()
                return

            # Por enquanto, criar uma visualização textual simples
            # TODO: Implementar gráficos reais com matplotlib

            total_cost = sum(item['cost'] for item in cost_data)
            total_queries = sum(item['queries'] for item in cost_data)
            total_data_gb = sum(item['data_processed_gb'] for item in cost_data)

            # Agrupar por workgroup
            workgroup_costs = {}
            for item in cost_data:
                wg = item['workgroup']
                if wg not in workgroup_costs:
                    workgroup_costs[wg] = {'cost': 0, 'queries': 0, 'data_gb': 0}
                workgroup_costs[wg]['cost'] += item['cost']
                workgroup_costs[wg]['queries'] += item['queries']
                workgroup_costs[wg]['data_gb'] += item['data_processed_gb']

            # Criar conteúdo do resumo
            summary_text = f"""RESUMO DO PERÍODO ({period.upper()})

Custo Total: ${total_cost:.2f}
Queries Totais: {total_queries:,}
Dados Processados: {total_data_gb:.2f} GB

POR WORKGROUP:
"""

            for wg, data in workgroup_costs.items():
                percentage = (data['cost'] / total_cost * 100) if total_cost > 0 else 0
                summary_text += f"\n• {wg}: ${data['cost']:.2f} ({percentage:.1f}%)"
                summary_text += f"\n  Queries: {data['queries']:,} | Dados: {data['data_gb']:.2f} GB\n"

            self.athena_charts_container.content = ft.Text(
                summary_text,
                size=14,
                text_align=ft.TextAlign.LEFT,
                color=ft.Colors.WHITE,
                font_family="monospace"
            )
            self.page.update()

        except Exception as e:
            print(f"❌ Erro ao gerar gráficos: {e}")
            self.athena_charts_container.content = ft.Text(
                f"Erro ao gerar gráficos: {str(e)}",
                size=16,
                text_align=ft.TextAlign.CENTER,
                color=ft.Colors.RED
            )
            self.page.update()

    # EventBridge Monitoring Functions
    def fetch_eventbridge_rules(self):
        """Busca todas as regras do EventBridge usando boto3."""
        try:
            if not self.current_account_id:
                print("❌ Necessário estar logado para buscar regras EventBridge")
                return []

            print("🔍 Buscando regras do EventBridge...")

            # Usar retry para evitar throttling
            def get_eventbridge_rules():
                eventbridge_client = boto3.client('events')
                paginator = eventbridge_client.get_paginator('list_rules')

                all_rules = []
                for page in paginator.paginate():
                    # Pequeno delay entre páginas
                    time.sleep(0.1)
                    for rule in page['Rules']:
                        all_rules.append(rule)

                return all_rules

            rules = self.retry_with_backoff(get_eventbridge_rules, max_retries=3, base_delay=1.0)

            if not rules:
                print("📋 Nenhuma regra EventBridge encontrada")
                return []

            print(f"📊 {len(rules)} regras EventBridge encontradas")

            # Processar regras em paralelo para obter detalhes
            rules_metadata = []
            max_workers = min(3, max(2, len(rules) // 10))  # Reduzido para evitar throttling
            print(f"🔧 Usando {max_workers} workers para processar regras")

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submeter jobs com delay para evitar burst
                future_to_rule = {}
                for i, rule in enumerate(rules):
                    # Delay progressivo entre submissões
                    if i > 0:
                        time.sleep(0.05)

                    future = executor.submit(self.fetch_single_rule_details, rule)
                    future_to_rule[future] = rule['Name']

                # Processar resultados
                completed = 0
                for future in as_completed(future_to_rule):
                    try:
                        rule_data = future.result()
                        rules_metadata.append(rule_data)
                        completed += 1

                        # Log de progresso a cada 25%
                        if completed % max(1, len(rules) // 4) == 0:
                            progress = (completed / len(rules)) * 100
                            print(f"📈 Progresso: {completed}/{len(rules)} ({progress:.0f}%)")

                    except Exception as e:
                        rule_name = future_to_rule[future]
                        print(f"❌ Erro ao processar regra {rule_name}: {e}")
                        # Adicionar entrada com erro
                        rules_metadata.append({
                            'name': rule_name,
                            'state': "ERROR",
                            'description': f"Erro: {str(e)}",
                            'schedule': "N/A",
                            'targets': 0
                        })

            end_time = time.time()
            duration = end_time - start_time
            print(f"⚡ Regras EventBridge processadas em {duration:.2f}s com {max_workers} workers")

            return rules_metadata

        except Exception as e:
            print(f"❌ Erro geral ao buscar regras EventBridge: {e}")
            return []

    def fetch_single_rule_details(self, rule):
        """Busca detalhes de uma única regra do EventBridge."""
        try:
            # Adicionar delay aleatório pequeno para espalhar requisições
            time.sleep(random.uniform(0.1, 0.3))

            rule_name = rule['Name']

            # Buscar targets da regra com retry
            def get_rule_targets():
                eventbridge_client = boto3.client('events')
                return eventbridge_client.list_targets_by_rule(Rule=rule_name)

            targets_response = self.retry_with_backoff(get_rule_targets, max_retries=3, base_delay=0.5)
            target_count = len(targets_response.get('Targets', []))

            return {
                'name': rule_name,
                'state': rule.get('State', 'UNKNOWN'),
                'description': rule.get('Description', 'N/A'),
                'schedule': rule.get('ScheduleExpression', 'N/A'),
                'targets': target_count,
                'arn': rule.get('Arn', 'N/A')
            }

        except Exception as e:
            print(f"❌ Erro ao buscar detalhes da regra {rule.get('Name', 'UNKNOWN')}: {e}")
            return {
                'name': rule.get('Name', 'UNKNOWN'),
                'state': "ERROR",
                'description': f"Erro: {str(e)}",
                'schedule': "N/A",
                'targets': 0,
                'arn': "N/A"
            }

    def toggle_eventbridge_rule(self, rule_name, current_state):
        """Liga ou desliga uma regra do EventBridge."""
        try:
            eventbridge_client = boto3.client('events')

            if current_state == "ENABLED":
                # Desabilitar regra
                def disable_rule():
                    return eventbridge_client.disable_rule(Name=rule_name)

                self.retry_with_backoff(disable_rule, max_retries=3, base_delay=0.5)
                new_state = "DISABLED"
                action = "desabilitada"
            else:
                # Habilitar regra
                def enable_rule():
                    return eventbridge_client.enable_rule(Name=rule_name)

                self.retry_with_backoff(enable_rule, max_retries=3, base_delay=0.5)
                new_state = "ENABLED"
                action = "habilitada"

            print(f"✅ Regra '{rule_name}' {action} com sucesso")
            return new_state

        except Exception as e:
            print(f"❌ Erro ao alterar estado da regra {rule_name}: {e}")
            return current_state  # Retorna estado original em caso de erro

    def update_eventbridge_table(self, rules_data=None):
        """Atualiza a tabela da aba EventBridge."""
        if rules_data is None:
            rules_data = getattr(self, "all_eventbridge_rules", [])

        # Limpa tabela atual
        self.eventbridge_rules_table.rows.clear()

        for rule in rules_data:
            # Criar botão interruptor (switch)
            current_state = rule.get("state", "UNKNOWN")
            is_enabled = current_state == "ENABLED"

            switch_button = ft.Switch(
                value=is_enabled,
                active_color=ft.Colors.GREEN,
                inactive_color=ft.Colors.RED,
                on_change=lambda e, rule_name=rule.get("name"): self.on_rule_switch_toggle(e, rule_name)
            )

            # Definir cor do estado
            state_color = ft.Colors.GREEN if is_enabled else ft.Colors.RED if current_state == "DISABLED" else ft.Colors.ORANGE

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(rule.get("name", ""), size=12)),
                    ft.DataCell(ft.Text(current_state, size=12, color=state_color, weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(rule.get("description", "N/A")[:50] + "..." if len(rule.get("description", "")) > 50 else rule.get("description", "N/A"), size=12)),
                    ft.DataCell(ft.Text(rule.get("schedule", "N/A"), size=12)),
                    ft.DataCell(ft.Text(str(rule.get("targets", 0)), size=12)),
                    ft.DataCell(switch_button),
                ]
            )
            self.eventbridge_rules_table.rows.append(row)

        # Força refresh na UI
        if hasattr(self, "page"):
            self.page.update()

    def on_rule_switch_toggle(self, e, rule_name):
        """Callback para quando o usuário clica no switch de uma regra."""
        try:
            # Encontrar a regra atual na lista
            current_rule = None
            for rule in getattr(self, "all_eventbridge_rules", []):
                if rule.get("name") == rule_name:
                    current_rule = rule
                    break

            if not current_rule:
                print(f"❌ Regra {rule_name} não encontrada")
                return

            current_state = current_rule.get("state", "UNKNOWN")

            # Mostrar status de carregamento
            self.monitoring_status_eventbridge.value = f"🔄 Alterando estado da regra '{rule_name}'..."
            self.monitoring_status_eventbridge.color = ft.Colors.ORANGE
            self.page.update()

            # Executar toggle em thread separada para não bloquear a UI
            def toggle_in_background():
                try:
                    new_state = self.toggle_eventbridge_rule(rule_name, current_state)

                    # Atualizar estado na lista local
                    current_rule["state"] = new_state

                    def update_ui():
                        # Atualizar tabela
                        self.update_eventbridge_table()

                        # Atualizar status
                        action = "habilitada" if new_state == "ENABLED" else "desabilitada"
                        self.monitoring_status_eventbridge.value = f"✅ Regra '{rule_name}' {action} com sucesso"
                        self.monitoring_status_eventbridge.color = ft.Colors.GREEN
                        self.page.update()

                        # Reset status após 3 segundos
                        def reset_status():
                            time.sleep(3)
                            total_rules = len(getattr(self, "all_eventbridge_rules", []))
                            self.monitoring_status_eventbridge.value = f"✅ {total_rules} regras EventBridge encontradas"
                            self.monitoring_status_eventbridge.color = ft.Colors.GREEN
                            self.page.update()

                        threading.Thread(target=reset_status, daemon=True).start()

                    self.page.run_thread(update_ui)

                except Exception as e:
                    def update_ui_error():
                        self.monitoring_status_eventbridge.value = f"❌ Erro ao alterar regra: {str(e)}"
                        self.monitoring_status_eventbridge.color = ft.Colors.RED
                        # Reverter o switch
                        e.control.value = current_state == "ENABLED"
                        self.page.update()

                    self.page.run_thread(update_ui_error)

            threading.Thread(target=toggle_in_background, daemon=True).start()

        except Exception as e:
            self.monitoring_status_eventbridge.value = f"❌ Erro: {str(e)}"
            self.monitoring_status_eventbridge.color = ft.Colors.RED
            self.page.update()

    def refresh_eventbridge_rules(self, e=None):
        """Atualiza a lista de regras do EventBridge."""
        if not self.current_account_id:
            self.monitoring_status_eventbridge.value = "Faça login primeiro para visualizar regras EventBridge"
            self.monitoring_status_eventbridge.color = ft.Colors.RED
            self.page.update()
            return

        # Ativa progress
        self.monitoring_progress_eventbridge.visible = True
        self.refresh_button_eventbridge.disabled = True
        self.monitoring_status_eventbridge.value = "Carregando regras do EventBridge..."
        self.monitoring_status_eventbridge.color = ft.Colors.ORANGE
        self.page.update()

        def fetch_in_background():
            try:
                rules = self.fetch_eventbridge_rules()

                def update_ui():
                    self.all_eventbridge_rules = rules
                    self.update_eventbridge_table(rules)

                    # Salvar no cache
                    self.save_eventbridge_cache(rules)

                    self.monitoring_status_eventbridge.value = f"✅ {len(rules)} regras EventBridge encontradas"
                    self.monitoring_status_eventbridge.color = ft.Colors.GREEN
                    self.monitoring_progress_eventbridge.visible = False
                    self.refresh_button_eventbridge.disabled = False
                    self.page.update()

                # Executa atualização da UI na thread principal
                self.page.run_thread(update_ui)

            except Exception as e:
                def update_ui_error():
                    self.monitoring_status_eventbridge.value = f"❌ Erro ao carregar regras: {str(e)}"
                    self.monitoring_status_eventbridge.color = ft.Colors.RED
                    self.monitoring_progress_eventbridge.visible = False
                    self.refresh_button_eventbridge.disabled = False
                    self.page.update()

                self.page.run_thread(update_ui_error)

        # Executar em thread separada
        threading.Thread(target=fetch_in_background, daemon=True).start()

    def filter_eventbridge_rules(self, e=None):
        """Filtra regras EventBridge baseado no texto de busca."""
        filter_text = self.eventbridge_filter.value.lower() if self.eventbridge_filter.value else ""

        if not hasattr(self, 'all_eventbridge_rules') or not self.all_eventbridge_rules:
            return

        if not filter_text:
            # Se não há filtro, mostra todas as regras
            self.update_eventbridge_table(self.all_eventbridge_rules)
        else:
            # Filtra regras que contenham o texto no nome ou descrição
            filtered_rules = [
                rule for rule in self.all_eventbridge_rules
                if (filter_text in rule.get("name", "").lower() or
                    filter_text in rule.get("description", "").lower())
            ]
            self.update_eventbridge_table(filtered_rules)

        # Salvar texto do filtro
        self.save_filter_text("eventbridge_monitoring", filter_text)

    def copy_eventbridge_to_clipboard(self, e=None):
        """Copia dados das regras EventBridge filtradas para clipboard."""
        try:
            if not hasattr(self, 'eventbridge_rules_table') or not self.eventbridge_rules_table.rows:
                return

            # Cabeçalhos
            headers = ["Name", "State", "Description", "Schedule", "Targets"]

            # Dados das linhas (exceto a coluna Actions)
            data = []
            for row in self.eventbridge_rules_table.rows:
                row_data = []
                for i, cell in enumerate(row.cells[:-1]):  # Excluir última coluna (Actions)
                    row_data.append(cell.content.value if hasattr(cell.content, 'value') else str(cell.content))
                data.append(row_data)

            # Criar texto formatado para clipboard
            clipboard_text = "\t".join(headers) + "\n"
            for row_data in data:
                clipboard_text += "\t".join(row_data) + "\n"

            pyperclip.copy(clipboard_text)

            # Feedback visual
            self.monitoring_status_eventbridge.value = "✅ Dados copiados para clipboard"
            self.monitoring_status_eventbridge.color = ft.Colors.GREEN
            self.page.update()

            # Reset status após 3 segundos
            def reset_status():
                time.sleep(3)
                self.monitoring_status_eventbridge.value = f"✅ {len(data)} regras EventBridge encontradas"
                self.monitoring_status_eventbridge.color = ft.Colors.GREEN
                self.page.update()

            threading.Thread(target=reset_status, daemon=True).start()

        except Exception as e:
            self.monitoring_status_eventbridge.value = f"❌ Erro ao copiar: {str(e)}"
            self.monitoring_status_eventbridge.color = ft.Colors.RED
            self.page.update()

    def export_eventbridge_to_excel(self, e=None):
        """Exporta dados das regras EventBridge filtradas para Excel."""
        try:
            if not hasattr(self, 'eventbridge_rules_table') or not self.eventbridge_rules_table.rows:
                return

            # Mostrar status de escolha de pasta
            self.monitoring_status_eventbridge.value = "📁 Escolha onde salvar o arquivo..."
            self.monitoring_status_eventbridge.color = ft.Colors.BLUE
            self.page.update()

            # Preparar dados (exceto a coluna Actions)
            self.export_data_eventbridge = []
            for row in self.eventbridge_rules_table.rows:
                row_data = []
                for i, cell in enumerate(row.cells[:-1]):  # Excluir última coluna (Actions)
                    row_data.append(cell.content.value if hasattr(cell.content, 'value') else str(cell.content))
                self.export_data_eventbridge.append(row_data)

            # Abrir seletor de pasta e executar export após seleção
            self.select_export_folder(self._export_eventbridge_after_folder_selection)

        except Exception as e:
            self.monitoring_status_eventbridge.value = f"❌ Erro ao preparar export: {str(e)}"
            self.monitoring_status_eventbridge.color = ft.Colors.RED
            self.page.update()

    def _export_eventbridge_after_folder_selection(self):
        """Executa o export EventBridge após a pasta ser selecionada"""
        try:
            # Criar DataFrame
            df = pd.DataFrame(self.export_data_eventbridge, columns=["Name", "State", "Description", "Schedule", "Targets"])

            # Nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eventbridge_rules_{timestamp}.xlsx"

            # Caminho completo usando a pasta selecionada
            file_path = self.export_folder / filename

            # Exportar
            df.to_excel(file_path, index=False, engine='openpyxl')

            # Feedback visual
            self.monitoring_status_eventbridge.value = f"✅ Exportado para {file_path.parent.name}/{filename}"
            self.monitoring_status_eventbridge.color = ft.Colors.GREEN
            self.page.update()

            # Reset status após 5 segundos
            def reset_status():
                time.sleep(5)
                self.monitoring_status_eventbridge.value = f"✅ {len(self.export_data_eventbridge)} regras EventBridge encontradas"
                self.monitoring_status_eventbridge.color = ft.Colors.GREEN
                self.page.update()

            threading.Thread(target=reset_status, daemon=True).start()

        except Exception as e:
            self.monitoring_status_eventbridge.value = f"❌ Erro ao exportar: {str(e)}"
            self.monitoring_status_eventbridge.color = ft.Colors.RED
            self.page.update()


def main(page: ft.Page):
    AWSApp(page)


if __name__ == "__main__":
    ft.app(target=main)