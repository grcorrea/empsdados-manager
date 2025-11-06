import boto3
import configparser
import subprocess
import threading
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound


class AWSAuthService:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.current_profile = None
        self.current_account_id = None
        self.current_user_arn = None
        self.auth_callbacks = []

    def add_auth_callback(self, callback):
        """Adiciona callback para ser executado quando status de auth mudar"""
        self.auth_callbacks.append(callback)

    def _notify_auth_change(self):
        """Notifica todos os callbacks sobre mudança no status de auth"""
        for callback in self.auth_callbacks:
            try:
                callback()
            except Exception as e:
                print(f" Erro ao executar callback de auth: {e}")

    def check_login_status(self):
        """Verifica se há um usuário logado e retorna status"""
        try:
            session = boto3.Session()
            sts = session.client('sts')

            # Tentar obter identidade atual
            identity = sts.get_caller_identity()

            # Extrair perfil atual (se possível)
            profile = session.profile_name if session.profile_name != 'default' else None

            self.current_profile = profile
            self.current_account_id = identity.get('Account', 'N/A')
            self.current_user_arn = identity.get('Arn', 'N/A')

            print(f" Usuário logado - Perfil: {self.current_profile}, Conta: {self.current_account_id}")
            self._notify_auth_change()
            return True

        except Exception as e:
            print(f" Erro ao verificar status AWS: {e}")
            self.current_profile = None
            self.current_account_id = None
            self.current_user_arn = None
            self._notify_auth_change()
            return False

    def load_sso_profiles(self):
        """Carrega perfis SSO disponíveis"""
        try:
            aws_config_path = Path.home() / ".aws" / "config"

            if not aws_config_path.exists():
                print(" Arquivo de configuração AWS não encontrado")
                return []

            config = configparser.ConfigParser()
            config.read(aws_config_path)

            profiles = []
            for section_name in config.sections():
                if section_name.startswith('profile '):
                    profile_name = section_name.replace('profile ', '')
                    section = config[section_name]

                    if 'sso_start_url' in section:
                        profiles.append({
                            'name': profile_name,
                            'sso_start_url': section.get('sso_start_url', ''),
                            'sso_region': section.get('sso_region', ''),
                            'sso_account_id': section.get('sso_account_id', ''),
                            'sso_role_name': section.get('sso_role_name', ''),
                            'region': section.get('region', 'us-east-1')
                        })

            print(f" Encontrados {len(profiles)} perfis SSO")
            return profiles

        except Exception as e:
            print(f" Erro ao carregar perfis SSO: {e}")
            return []

    def login_with_profile(self, profile_name, callback=None):
        """Realiza login usando perfil SSO específico"""
        def login_thread():
            try:
                print(f"🔐 Iniciando login SSO para perfil: {profile_name}")

                # Executar comando de login SSO
                result = subprocess.run([
                    'aws', 'sso', 'login', '--profile', profile_name
                ], capture_output=True, text=True, timeout=300)

                if result.returncode == 0:
                    print(f" Login realizado com sucesso para: {profile_name}")

                    # Atualizar status
                    self.current_profile = profile_name
                    self.check_login_status()

                    # Salvar perfil usado
                    self.config_manager.set('AWS', 'last_used_profile', profile_name)
                    self.config_manager.save_config()

                    if callback:
                        callback(True, "Login realizado com sucesso!")
                else:
                    error_msg = result.stderr or "Erro desconhecido"
                    print(f" Erro no login: {error_msg}")
                    if callback:
                        callback(False, f"Erro no login: {error_msg}")

            except subprocess.TimeoutExpired:
                error_msg = "Timeout no processo de login (5 minutos)"
                print(f" {error_msg}")
                if callback:
                    callback(False, error_msg)
            except Exception as e:
                error_msg = f"Erro inesperado: {e}"
                print(f" {error_msg}")
                if callback:
                    callback(False, error_msg)

        # Executar login em thread separada
        threading.Thread(target=login_thread, daemon=True).start()

    def logout(self, callback=None):
        """Realiza logout do AWS SSO"""
        def logout_thread():
            try:
                if not self.current_profile:
                    print(" Nenhum perfil ativo para logout")
                    if callback:
                        callback(True, "Nenhum perfil ativo")
                    return

                print(f"🚪 Realizando logout do perfil: {self.current_profile}")

                # Executar comando de logout SSO
                result = subprocess.run([
                    'aws', 'sso', 'logout', '--profile', self.current_profile
                ], capture_output=True, text=True, timeout=60)

                # Reset das variáveis independentemente do resultado
                self.current_profile = None
                self.current_account_id = None
                self.current_user_arn = None
                self._notify_auth_change()

                if result.returncode == 0:
                    print(" Logout realizado com sucesso")
                    if callback:
                        callback(True, "Logout realizado com sucesso!")
                else:
                    print(f" Logout executado (código: {result.returncode})")
                    if callback:
                        callback(True, "Logout executado")

            except subprocess.TimeoutExpired:
                # Reset das variáveis mesmo com timeout
                self.current_profile = None
                self.current_account_id = None
                self.current_user_arn = None
                self._notify_auth_change()

                error_msg = "Timeout no logout (considerado concluído)"
                print(f" {error_msg}")
                if callback:
                    callback(True, error_msg)
            except Exception as e:
                # Reset das variáveis mesmo com erro
                self.current_profile = None
                self.current_account_id = None
                self.current_user_arn = None
                self._notify_auth_change()

                error_msg = f"Erro no logout (considerado concluído): {e}"
                print(f" {error_msg}")
                if callback:
                    callback(True, error_msg)

        # Executar logout em thread separada
        threading.Thread(target=logout_thread, daemon=True).start()

    def get_current_session(self):
        """Retorna sessão AWS atual"""
        if self.current_profile:
            return boto3.Session(profile_name=self.current_profile)
        else:
            return boto3.Session()

    def is_authenticated(self):
        """Verifica se está autenticado"""
        return self.current_profile is not None

    def get_status_info(self):
        """Retorna informações de status de autenticação"""
        return {
            'profile': self.current_profile,
            'account_id': self.current_account_id,
            'user_arn': self.current_user_arn,
            'authenticated': self.is_authenticated()
        }