import flet as ft
import boto3
import os
import configparser
import subprocess
import sys
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound


class AWSApp:
    def __init__(self, page: ft.Page):
        self.page = page

        # Variáveis globais para status AWS
        self.current_profile = None
        self.current_account_id = None
        self.current_user_arn = None

        self.setup_page()
        self.setup_status_bar()
        self.setup_tabs()
        self.check_login_status()

    def setup_page(self):
        self.page.title = "AWS Manager"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window.width = 600
        self.page.window.height = 750
        self.page.window.resizable = False
        self.page.window.center()

    def setup_status_bar(self):
        # Elementos da barra de status
        self.status_profile_text = ft.Text(
            "Profile: Não logado",
            size=12,
            color=ft.Colors.GREY_400
        )

        self.status_account_text = ft.Text(
            "Account ID: N/A",
            size=12,
            color=ft.Colors.GREY_400
        )

        self.status_refresh_button = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Atualizar Status",
            on_click=self.refresh_aws_status,
            icon_size=16
        )

        # Container da barra de status
        self.status_bar = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=16, color=ft.Colors.BLUE),
                self.status_profile_text,
                ft.VerticalDivider(),
                ft.Icon(ft.Icons.CLOUD, size=16, color=ft.Colors.BLUE),
                self.status_account_text,
                self.status_refresh_button
            ], spacing=10, alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            bgcolor=ft.Colors.GREY_900,
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.GREY_700))
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

        # Create Tabs
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Login", content=self.login_tab),
                ft.Tab(text="S3", content=self.s3_tab),
            ],
            expand=True,
        )

        # Layout principal com abas e barra de status
        main_layout = ft.Column([
            tabs,
            self.status_bar
        ], expand=True, spacing=0)

        self.page.add(main_layout)

    def create_login_tab(self):
        self.status_text = ft.Text(
            "Verificando status de login...",
            size=16,
            color=ft.Colors.ORANGE
        )

        self.profile_list = ft.Column(spacing=10)
        self.login_button = ft.ElevatedButton(
            "Login",
            on_click=self.on_login_click,
            disabled=True,
            width=200
        )

        self.progress_ring = ft.ProgressRing(visible=False)

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    ft.Text(
                        "AWS SSO Login",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    alignment=ft.alignment.center,
                    padding=20
                ),
                ft.Divider(),
                self.status_text,
                ft.Container(height=20),
                ft.Text("Profiles SSO Disponíveis:", size=16, weight=ft.FontWeight.BOLD),
                self.profile_list,
                ft.Container(height=20),
                ft.Row([
                    self.login_button,
                    self.progress_ring
                ], alignment=ft.MainAxisAlignment.CENTER),
            ],
            spacing=15,
            horizontal_alignment=ft.CrossAxisAlignment.START
            ),
            padding=30,
            expand=True
        )

    def create_s3_tab(self):
        # RT Dropdown
        self.rt_dropdown = ft.Dropdown(
            label="RT",
            options=[
                ft.dropdown.Option("fluxo"),
                ft.dropdown.Option("corebank"),
                ft.dropdown.Option("assessoria"),
                ft.dropdown.Option("credito"),
            ],
            width=200,
            on_change=self.update_s3_path
        )

        # Environment Dropdown
        self.env_dropdown = ft.Dropdown(
            label="Ambiente",
            options=[
                ft.dropdown.Option("sirius"),
                ft.dropdown.Option("athena"),
            ],
            width=200,
            on_change=self.update_s3_path
        )

        # S3 URI Field
        self.s3_uri_field = ft.TextField(
            label="URI do S3 (ex: s3://meu-bucket/)",
            width=400,
            on_change=self.update_s3_path
        )

        # Local Path Display
        self.local_path_text = ft.Text(
            "Pasta local: Selecione RT e Ambiente",
            size=12,
            color=ft.Colors.GREY_400,
            selectable=True
        )

        # Open Folder Button
        self.open_folder_button = ft.ElevatedButton(
            "📁 Abrir Pasta",
            on_click=self.open_local_folder,
            disabled=True,
            width=120,
            height=35
        )

        # Final S3 Path Display
        self.s3_path_text = ft.Text(
            "Caminho S3: Insira URI e selecione opções",
            size=12,
            color=ft.Colors.GREY_400,
            selectable=True
        )

        # Sync Buttons
        self.sync_to_s3_button = ft.ElevatedButton(
            "🔄 Local → S3",
            on_click=self.sync_to_s3,
            disabled=True,
            width=150
        )

        self.sync_from_s3_button = ft.ElevatedButton(
            "🔄 S3 → Local",
            on_click=self.sync_from_s3,
            disabled=True,
            width=150
        )

        # Progress and Status
        self.s3_progress = ft.ProgressRing(visible=False)
        self.s3_status = ft.Text(
            "",
            size=14,
            color=ft.Colors.BLUE
        )

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    ft.Text(
                        "Sincronização S3",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    alignment=ft.alignment.center,
                    padding=20
                ),
                ft.Divider(),

                ft.Text("Configurações:", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([self.rt_dropdown, self.env_dropdown], spacing=20),

                ft.Container(height=10),
                self.s3_uri_field,

                ft.Container(height=10),
                ft.Text("Preview dos Caminhos:", size=14, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Column([
                        self.local_path_text,
                    ], expand=True),
                    self.open_folder_button
                ], spacing=10, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.s3_path_text,

                ft.Container(height=20),
                ft.Text("Sincronização:", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.sync_to_s3_button,
                    self.sync_from_s3_button,
                    self.s3_progress
                ], spacing=20),

                ft.Container(height=10),
                self.s3_status,
            ],
            spacing=15,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            scroll=ft.ScrollMode.AUTO
            ),
            padding=30,
            expand=True
        )

    def update_s3_path(self, e=None):
        rt = self.rt_dropdown.value
        env = self.env_dropdown.value
        s3_uri = self.s3_uri_field.value

        # Update local path
        if rt and env:
            user_home = Path.home()
            local_path = user_home / "s3" / rt / env
            self.local_path_text.value = f"Pasta local: {local_path}"
            self.local_path_text.color = ft.Colors.GREEN

            # Enable open folder button
            self.open_folder_button.disabled = False
        else:
            self.local_path_text.value = "Pasta local: Selecione RT e Ambiente"
            self.local_path_text.color = ft.Colors.GREY_400

            # Disable open folder button
            self.open_folder_button.disabled = True

        # Update S3 path
        if s3_uri and rt and env:
            s3_uri_clean = s3_uri.rstrip('/')
            final_s3_path = f"{s3_uri_clean}/{rt}/{env}/"
            self.s3_path_text.value = f"Caminho S3: {final_s3_path}"
            self.s3_path_text.color = ft.Colors.GREEN

            # Enable sync buttons
            self.sync_to_s3_button.disabled = False
            self.sync_from_s3_button.disabled = False
        else:
            self.s3_path_text.value = "Caminho S3: Insira URI e selecione opções"
            self.s3_path_text.color = ft.Colors.GREY_400

            # Disable sync buttons
            self.sync_to_s3_button.disabled = True
            self.sync_from_s3_button.disabled = True

        self.page.update()

    def get_local_path(self):
        rt = self.rt_dropdown.value
        env = self.env_dropdown.value
        if rt and env:
            return Path.home() / "s3" / rt / env
        return None

    def get_s3_path(self):
        s3_uri = self.s3_uri_field.value
        rt = self.rt_dropdown.value
        env = self.env_dropdown.value
        if s3_uri and rt and env:
            s3_uri_clean = s3_uri.rstrip('/')
            return f"{s3_uri_clean}/{rt}/{env}/"
        return None

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
                self.s3_status.value = "❌ Selecione RT e Ambiente primeiro"
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
                s3_path,
                '--delete'
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

            result = subprocess.run([
                'aws', 's3', 'sync',
                s3_path,
                str(local_path),
                '--delete'
            ], capture_output=True, text=True, check=True)

            self.s3_status.value = f"✅ Sincronização concluída: S3 → Local"
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
            self.login_button.text = "Já está logado"
            self.login_button.disabled = True
        else:
            self.status_text.value = "❌ Não logado - Selecione um profile SSO"
            self.status_text.color = ft.Colors.RED
            self.load_sso_profiles()

        self.page.update()

    def load_sso_profiles(self):
        try:
            aws_dir = Path.home() / '.aws'
            aws_config_path = None

            # Tentar encontrar arquivo config (com ou sem extensão)
            possible_config_files = ['config', 'config.txt']
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
                self.login_button.text = "Login Realizado"
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
                    self.login_button.text = "Profile Ativo"
                    success = True
                else:
                    self.status_text.value = f"❌ Erro no profile: {result.stderr or result.stdout}"
                    self.status_text.color = ft.Colors.RED
                    self.login_button.disabled = False

            if success:
                os.environ['AWS_PROFILE'] = profile

        except FileNotFoundError:
            self.status_text.value = "❌ AWS CLI não encontrado. Instale o AWS CLI primeiro."
            self.status_text.color = ft.Colors.RED
            self.login_button.disabled = False

        # Atualizar barra de status após tentativa de login
        self.update_status_bar()

        self.progress_ring.visible = False
        self.page.update()


def main(page: ft.Page):
    AWSApp(page)


if __name__ == "__main__":
    ft.app(target=main)