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
            elif cache_type == "athena_workgroups":
                cache_file = self.get_athena_workgroups_cache_filename()
            elif cache_type == "athena_costs":
                cache_file = self.get_athena_costs_cache_filename()
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

    # ============== FUNÇÕES DE CACHE ATHENA ==============

    def get_athena_workgroups_cache_filename(self):
        """Retorna o nome do arquivo de cache dos workgroups Athena para a conta atual"""
        if not self.current_account_id:
            return self.cache_dir / "athena_workgroups_cache.json"  # Fallback para casos sem account_id
        return self.cache_dir / f"athena_workgroups_cache_{self.current_account_id}.json"

    def get_athena_costs_cache_filename(self):
        """Retorna o nome do arquivo de cache dos custos Athena para a conta atual"""
        if not self.current_account_id:
            return self.cache_dir / "athena_costs_cache.json"  # Fallback para casos sem account_id
        return self.cache_dir / f"athena_costs_cache_{self.current_account_id}.json"

    def save_athena_workgroups_cache(self, workgroups_data):
        """Salva dados dos workgroups Athena no cache local"""
        try:
            if not self.ensure_cache_directory():
                return False

            current_time = datetime.now(timezone.utc).isoformat()
            cache_data = {
                "timestamp": current_time,
                "updated_at": current_time,
                "account_id": self.current_account_id,
                "profile": self.current_profile,
                "workgroups_count": len(workgroups_data),
                "workgroups": workgroups_data  # Workgroups data is already JSON serializable
            }

            cache_file = self.get_athena_workgroups_cache_filename()

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Cache workgroups Athena salvo: {len(workgroups_data)} workgroups")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar cache workgroups Athena: {e}")
            return False

    def load_athena_workgroups_cache(self):
        """Carrega dados dos workgroups Athena do cache local"""
        try:
            cache_file = self.get_athena_workgroups_cache_filename()
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Verificar se o cache é para a conta/profile atual
            if (cache_data.get("account_id") != self.current_account_id or
                cache_data.get("profile") != self.current_profile):
                print("🔄 Cache workgroups Athena é de outra conta/profile, ignorando...")
                return None

            workgroups_list = cache_data.get("workgroups", [])
            cache_timestamp = cache_data.get("timestamp", "")
            print(f"📁 Cache workgroups Athena carregado: {len(workgroups_list)} workgroups (salvo em {cache_timestamp})")
            return workgroups_list

        except Exception as e:
            print(f"❌ Erro ao carregar cache workgroups Athena: {e}")
            return None

    def save_athena_costs_cache(self, costs_data, period, workgroup, start_date, end_date):
        """Salva dados de custos Athena no cache local"""
        try:
            if not self.ensure_cache_directory():
                return False

            current_time = datetime.now(timezone.utc).isoformat()
            cache_data = {
                "timestamp": current_time,
                "updated_at": current_time,
                "account_id": self.current_account_id,
                "profile": self.current_profile,
                "costs_count": len(costs_data),
                "query_params": {
                    "period": period,
                    "workgroup": workgroup,
                    "start_date": start_date,
                    "end_date": end_date
                },
                "costs": costs_data  # Costs data is already JSON serializable
            }

            cache_file = self.get_athena_costs_cache_filename()

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Cache custos Athena salvo: {len(costs_data)} registros")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar cache custos Athena: {e}")
            return False

    def load_athena_costs_cache(self, period, workgroup, start_date, end_date):
        """Carrega dados de custos Athena do cache local se os parâmetros coincidirem"""
        try:
            cache_file = self.get_athena_costs_cache_filename()
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Verificar se o cache é para a conta/profile atual
            if (cache_data.get("account_id") != self.current_account_id or
                cache_data.get("profile") != self.current_profile):
                print("🔄 Cache custos Athena é de outra conta/profile, ignorando...")
                return None

            # Verificar se os parâmetros da consulta coincidem
            cached_params = cache_data.get("query_params", {})
            if (cached_params.get("period") != period or
                cached_params.get("workgroup") != workgroup or
                cached_params.get("start_date") != start_date or
                cached_params.get("end_date") != end_date):
                print("🔄 Cache custos Athena tem parâmetros diferentes, ignorando...")
                return None

            costs_list = cache_data.get("costs", [])
            cache_timestamp = cache_data.get("timestamp", "")
            print(f"📁 Cache custos Athena carregado: {len(costs_list)} registros (salvo em {cache_timestamp})")
            return costs_list

        except Exception as e:
            print(f"❌ Erro ao carregar cache custos Athena: {e}")
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
