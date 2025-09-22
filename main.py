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

        self.setup_page()
        self.setup_status_bar()
        self.setup_tabs()
        self.check_login_status()

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
                    "title": "AWS Manager",
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
        self.page.title = app_config.get("title", "AWS Manager")
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

        # Configurações da janela
        window_config = app_config.get("window", {})
        self.page.window.width = window_config.get("width", 600)
        self.page.window.height = window_config.get("height", 750)
        self.page.window.resizable = window_config.get("resizable", False)
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

    def setup_tabs(self):
        # Login Tab Content
        self.login_tab = self.create_login_tab()

        # S3 Tab Content
        self.s3_tab = self.create_s3_tab()

        # Monitoring Glue Tab Content
        self.monitoring_glue_tab = self.create_monitoring_tab()

        # Monitoring STF Tab Content
        self.monitoring_stpf_tab = self.create_monitoring_stpf_tab()

        # Create Tabs com handler para detectar mudança
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Login", content=self.login_tab),
                ft.Tab(text="S3", content=self.s3_tab),
                ft.Tab(text="Monitoring Glue", content=self.monitoring_glue_tab),
                ft.Tab(text="Monitoring STF", content=self.monitoring_stpf_tab)
            ],
            expand=True,
            on_change=self.on_tab_change,
        )

        # Layout principal com abas e barra de status
        main_layout = ft.Column([
            self.tabs,
            self.status_bar
        ], expand=True, spacing=0)

        self.page.add(main_layout)

    def on_tab_change(self, e):
        """Handler chamado quando uma aba é selecionada"""
        try:
            selected_index = e.control.selected_index
            tab_names = ["Login", "S3", "Monitoring Glue", "Monitoring STF"]

            if selected_index < len(tab_names):
                tab_name = tab_names[selected_index]
                print(f"[TAB] Aba selecionada: {tab_name}")

                # Verificar cache apenas para abas de monitoring
                if tab_name == "Monitoring Glue":
                    # Adicionar um pequeno delay para garantir que a UI foi atualizada
                    def load_cache():
                        time.sleep(0.1)  # Pequeno delay
                        self.check_and_load_cache_on_tab_open("glue")

                    threading.Thread(target=load_cache, daemon=True).start()

                elif tab_name == "Monitoring STF":
                    # Adicionar um pequeno delay para garantir que a UI foi atualizada
                    def load_cache():
                        time.sleep(0.1)  # Pequeno delay
                        self.check_and_load_cache_on_tab_open("stpf")

                    threading.Thread(target=load_cache, daemon=True).start()

        except Exception as ex:
            print(f"[ERROR] Erro no handler de mudanca de aba: {ex}")

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
            )
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
            )
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
            on_change=self.update_s3_path
        )

        # RT Dropdown
        rt_options = s3_config.get("rt_options", ["fluxo", "corebank", "assessoria", "credito"])
        self.rt_dropdown = ft.Dropdown(
            label="RT",
            options=[ft.dropdown.Option(option) for option in rt_options],
            width=120,
            on_change=self.on_rt_change
        )

        # Environment Dropdown
        env_options = s3_config.get("environment_options", ["sirius", "athena"])
        self.env_dropdown = ft.Dropdown(
            label="Ambiente",
            options=[ft.dropdown.Option(option) for option in env_options],
            width=120,
            on_change=self.update_s3_path
        )

        # Squad Dropdown (inicialmente vazio, será preenchido baseado no RT)
        self.squad_dropdown = ft.Dropdown(
            label="Squad",
            options=[],
            width=140,
            on_change=self.update_s3_path,
            disabled=True  # Desabilitado até selecionar RT
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
            )
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
            )
        )

        # Checkbox para --delete no S3 → Local
        self.delete_checkbox = ft.Checkbox(
            label="Usar --delete (S3 → Local)",
            value=False,
            tooltip="Remove arquivos locais que não existem no S3"
        )

        # Progress and Status
        self.s3_progress = ft.ProgressRing(visible=False)
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
        self.glue_cache_file = self.cache_dir / "glue_cache.json"
        self.stpf_cache_file = self.cache_dir / "stpf_cache.json"

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

    def fetch_glue_jobs(self, max_jobs=None):
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

                    # Limitação para contas com muitos jobs
                    if max_jobs and len(all_job_names) >= max_jobs:
                        print(f"⚠️  Limitando a {max_jobs} jobs para melhor performance")
                        break

                if max_jobs and len(all_job_names) >= max_jobs:
                    break

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

        self.monitoring_progress.visible = True
        self.refresh_button.disabled = True
        self.monitoring_status.value = "Carregando jobs do Glue..."
        self.monitoring_status.color = ft.Colors.ORANGE
        self.page.update()

        try:
            # Buscar jobs em thread separada para não bloquear UI
            def fetch_in_background():
                # Opção de limitar jobs para contas com muitos jobs (opcional)
                max_jobs_limit = getattr(self, 'max_glue_jobs', 200)  # Limitar a 200 jobs por padrão
                jobs = self.fetch_glue_jobs(max_jobs=max_jobs_limit)

                # Atualizar UI na thread principal
                def update_ui():
                    self.all_jobs = jobs
                    self.filter_jobs()  # Aplicar filtro atual

                    # Salvar cache após carregar dados
                    if jobs:
                        self.save_glue_cache(jobs)

                    self.last_update_text.value = f"Última atualização: {datetime.now().strftime('%H:%M:%S')}"

                    if len(jobs) >= max_jobs_limit:
                        self.monitoring_status.value = f"✅ {len(jobs)} jobs carregados (limitado a {max_jobs_limit})"
                    else:
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
        self.jobs_failed = str(failed_count)
        self.jobs_running = str(running_count)
        self.jobs_dpu_hours = str(total_dpu_hours)
        self.jobs_time = str(total_minutes)
        self.jobs_flex = str(total_flex)

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

    def fetch_step_functions(self):
        """Busca Step Functions do AWS e seus status"""
        try:
            if not self.current_account_id:
                return []

            sfn_client = boto3.client('stepfunctions')

            # Buscar todas as state machines
            paginator = sfn_client.get_paginator('list_state_machines')
            state_machines = []

            for page in paginator.paginate():
                for sm in page['stateMachines']:
                    sm_name = sm['name']
                    sm_arn = sm['stateMachineArn']

                    # Buscar última execução da state machine
                    try:
                        executions_response = sfn_client.list_executions(
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

                    state_machines.append({
                        'name': sm_name,
                        'status': status,
                        'last_execution': started_on_str,
                        'duration': duration_str,
                        'start_time_obj': start_time  # Para ordenação
                    })

            return state_machines

        except Exception as e:
            print(f"Erro ao buscar Step Functions: {e}")
            return []

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
        self.stpf_time.value = str(int(total_minutes))

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

    def export_stpf_to_excel(self, e):
        """Exporta a tabela filtrada de Step Functions para Excel"""
        try:
            if not self.filtered_stpf:
                self.monitoring_status_sptf.value = "❌ Nenhuma Step Function para exportar"
                self.monitoring_status_sptf.color = ft.Colors.RED
                self.page.update()
                return

            # Preparar dados para DataFrame
            data = []
            for stpf in self.filtered_stpf:
                data.append({
                    'Name': stpf['name'],
                    'Status': stpf['status'],
                    'Última Execução': stpf['last_execution'],
                    'Duração': stpf['duration']
                })

            # Criar DataFrame
            df = pd.DataFrame(data)

            # Gerar nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"step_functions_{timestamp}.xlsx"

            # Exportar para Excel
            df.to_excel(filename, index=False, engine='openpyxl')

            self.monitoring_status_sptf.value = f"✅ {len(self.filtered_stpf)} Step Functions exportadas para {filename}"
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

    def save_glue_cache(self, jobs_data):
        """Salva dados dos jobs Glue no cache local"""
        try:
            if not self.ensure_cache_directory():
                return False

            cache_data = {
                "timestamp": datetime.now().isoformat(),
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

            with open(self.glue_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Cache Glue salvo: {len(jobs_data)} jobs em {self.glue_cache_file}")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar cache Glue: {e}")
            return False

    def load_glue_cache(self):
        """Carrega dados dos jobs Glue do cache local"""
        try:
            if not self.glue_cache_file.exists():
                return None

            with open(self.glue_cache_file, 'r', encoding='utf-8') as f:
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

            cache_data = {
                "timestamp": datetime.now().isoformat(),
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

            with open(self.stpf_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Cache STP salvo: {len(stpf_data)} Step Functions em {self.stpf_cache_file}")
            return True

        except Exception as e:
            print(f"❌ Erro ao salvar cache STP: {e}")
            return False

    def load_stpf_cache(self):
        """Carrega dados das Step Functions do cache local"""
        try:
            if not self.stpf_cache_file.exists():
                return None

            with open(self.stpf_cache_file, 'r', encoding='utf-8') as f:
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

    def check_and_load_cache_on_tab_open(self, tab_type):
        """Verifica cache ao abrir aba e carrega se disponível"""
        if not self.current_account_id:
            return  # Não fazer nada se não estiver logado

        if tab_type == "glue":
            # Tentar carregar cache do Glue
            cached_jobs = self.load_glue_cache()
            if cached_jobs:
                self.all_jobs = cached_jobs
                self.filter_jobs()
                self.monitoring_status.value = f"📁 {len(cached_jobs)} jobs carregados do cache"
                self.monitoring_status.color = ft.Colors.BLUE
                self.last_update_text.value = f"Cache carregado: {datetime.now().strftime('%H:%M:%S')}"
                self.page.update()
            else:
                # Não tem cache, carregar dados automaticamente
                print("🔄 Cache Glue não encontrado, carregando dados...")
                self.refresh_jobs()

        elif tab_type == "stpf":
            # Tentar carregar cache do STP
            cached_stpf = self.load_stpf_cache()
            if cached_stpf:
                self.all_stpf = cached_stpf
                self.filter_stpf_jobs()
                self.monitoring_status_sptf.value = f"📁 {len(cached_stpf)} Step Functions carregadas do cache"
                self.monitoring_status_sptf.color = ft.Colors.BLUE
                self.last_update_text_stpf.value = f"Cache carregado: {datetime.now().strftime('%H:%M:%S')}"
                self.page.update()
            else:
                # Não tem cache, carregar dados automaticamente
                print("🔄 Cache STP não encontrado, carregando dados...")
                self.refresh_stpf_jobs()

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

            # Preparar dados para DataFrame
            data = []
            for job in self.filtered_jobs:
                data.append({
                    'Job Name': job['name'],
                    'Status': job['status'],
                    'Última Execução': job['last_execution'],
                    'Duração': job['duration']
                })

            # Criar DataFrame
            df = pd.DataFrame(data)

            # Gerar nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"glue_jobs_{timestamp}.xlsx"

            # Exportar para Excel
            df.to_excel(filename, index=False, engine='openpyxl')

            self.monitoring_status.value = f"✅ {len(self.filtered_jobs)} jobs exportados para {filename}"
            self.monitoring_status.color = ft.Colors.GREEN
            self.page.update()

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


def main(page: ft.Page):
    AWSApp(page)


if __name__ == "__main__":
    ft.app(target=main)