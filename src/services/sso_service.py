import boto3
import subprocess
import json
import os
from typing import Dict, Any, List
from botocore.exceptions import ClientError, NoCredentialsError


class SSOService:
    def __init__(self):
        self.session = boto3.Session()

    def get_current_session_info(self) -> Dict[str, Any]:
        try:
            # Verificar se existe sessão ativa via STS
            sts = self.session.client('sts')
            identity = sts.get_caller_identity()

            # Obter informações da sessão atual
            profile = os.environ.get('AWS_PROFILE', 'default')
            region = self.session.region_name or 'us-east-1'

            return {
                "logged_in": True,
                "account_id": identity.get('Account', 'N/A'),
                "user_arn": identity.get('Arn', 'N/A'),
                "user_id": identity.get('UserId', 'N/A'),
                "profile": profile,
                "region": region
            }

        except (ClientError, NoCredentialsError):
            return {
                "logged_in": False,
                "account_id": None,
                "user_arn": None,
                "user_id": None,
                "profile": None,
                "region": None
            }

    def list_sso_profiles(self) -> List[Dict[str, str]]:
        try:
            # Tentar ler configurações AWS
            config_file = os.path.expanduser('~/.aws/config')
            if not os.path.exists(config_file):
                return []

            profiles = []
            with open(config_file, 'r') as f:
                content = f.read()

            # Buscar por profiles SSO
            lines = content.split('\n')
            current_profile = None
            profile_data = {}

            for line in lines:
                line = line.strip()
                if line.startswith('[profile '):
                    if current_profile and 'sso_start_url' in profile_data:
                        profiles.append({
                            'name': current_profile,
                            'sso_start_url': profile_data.get('sso_start_url', ''),
                            'sso_region': profile_data.get('sso_region', ''),
                            'sso_account_id': profile_data.get('sso_account_id', ''),
                            'sso_role_name': profile_data.get('sso_role_name', ''),
                            'region': profile_data.get('region', '')
                        })

                    current_profile = line.replace('[profile ', '').replace(']', '')
                    profile_data = {}

                elif '=' in line and current_profile:
                    key, value = line.split('=', 1)
                    profile_data[key.strip()] = value.strip()

            # Adicionar último profile se necessário
            if current_profile and 'sso_start_url' in profile_data:
                profiles.append({
                    'name': current_profile,
                    'sso_start_url': profile_data.get('sso_start_url', ''),
                    'sso_region': profile_data.get('sso_region', ''),
                    'sso_account_id': profile_data.get('sso_account_id', ''),
                    'sso_role_name': profile_data.get('sso_role_name', ''),
                    'region': profile_data.get('region', '')
                })

            return profiles

        except Exception as e:
            print(f"Erro ao listar profiles SSO: {e}")
            return []

    def login_sso_profile(self, profile_name: str) -> Dict[str, Any]:
        try:
            # Executar login SSO via AWS CLI
            result = subprocess.run(
                ['aws', 'sso', 'login', '--profile', profile_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos timeout
            )

            if result.returncode == 0:
                # Definir profile como padrão
                os.environ['AWS_PROFILE'] = profile_name

                # Verificar se o login foi bem-sucedido
                session_info = self.get_current_session_info()
                if session_info.get("logged_in"):
                    return {
                        "success": True,
                        "message": f"Login SSO realizado com sucesso para o profile {profile_name}",
                        "profile": profile_name,
                        "session_info": session_info
                    }
                else:
                    return {
                        "success": False,
                        "error": "Login realizado mas não foi possível verificar a sessão"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Erro no login SSO: {result.stderr}"
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout no login SSO (5 minutos)"
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "AWS CLI não encontrado. Instale o AWS CLI primeiro."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro inesperado: {str(e)}"
            }

    def logout_sso(self) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                ['aws', 'sso', 'logout'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Remover variáveis de ambiente
                if 'AWS_PROFILE' in os.environ:
                    del os.environ['AWS_PROFILE']

                return {
                    "success": True,
                    "message": "Logout SSO realizado com sucesso"
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro no logout SSO: {result.stderr}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Erro no logout: {str(e)}"
            }

    def check_sso_session_status(self, profile_name: str = None) -> Dict[str, Any]:
        try:
            cmd = ['aws', 'sts', 'get-caller-identity']
            if profile_name:
                cmd.extend(['--profile', profile_name])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {
                    "success": True,
                    "active": True,
                    "account_id": data.get('Account'),
                    "user_arn": data.get('Arn'),
                    "user_id": data.get('UserId')
                }
            else:
                return {
                    "success": True,
                    "active": False,
                    "message": "Sessão SSO não ativa ou expirada"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Erro ao verificar sessão: {str(e)}"
            }