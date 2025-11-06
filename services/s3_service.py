import boto3
import subprocess
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError


class S3Service:
    def __init__(self, auth_service, config_manager):
        self.auth_service = auth_service
        self.config_manager = config_manager

    def get_s3_client(self):
        """Retorna cliente S3 usando a sessão atual"""
        if not self.auth_service.is_authenticated():
            raise Exception("Usuário não autenticado")

        session = self.auth_service.get_current_session()
        return session.client('s3')

    def sync_to_s3(self, local_path, s3_path, dry_run=False, callback=None):
        """Sincroniza pasta local para S3"""
        try:
            if not Path(local_path).exists():
                raise Exception(f"Pasta local não existe: {local_path}")

            profile = self.auth_service.current_profile
            if not profile:
                raise Exception("Nenhum perfil AWS ativo")

            print(f" Sincronizando {local_path} -> {s3_path}")

            # Construir comando aws s3 sync
            cmd = [
                'aws', 's3', 'sync',
                str(local_path), s3_path,
                '--profile', profile,
                '--delete'
            ]

            if dry_run:
                cmd.append('--dryrun')

            # Executar comando
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                message = "Sincronização concluída com sucesso!"
                print(f" {message}")
                if callback:
                    callback(True, message, result.stdout)
            else:
                error_msg = result.stderr or "Erro desconhecido"
                print(f" Erro na sincronização: {error_msg}")
                if callback:
                    callback(False, error_msg, result.stdout)

        except subprocess.TimeoutExpired:
            error_msg = "Timeout na sincronização (5 minutos)"
            print(f" {error_msg}")
            if callback:
                callback(False, error_msg, "")
        except Exception as e:
            error_msg = f"Erro na sincronização: {e}"
            print(f" {error_msg}")
            if callback:
                callback(False, error_msg, "")

    def sync_from_s3(self, s3_path, local_path, dry_run=False, callback=None):
        """Sincroniza do S3 para pasta local"""
        try:
            # Garantir que pasta local existe
            Path(local_path).mkdir(parents=True, exist_ok=True)

            profile = self.auth_service.current_profile
            if not profile:
                raise Exception("Nenhum perfil AWS ativo")

            print(f" Sincronizando {s3_path} -> {local_path}")

            # Construir comando aws s3 sync
            cmd = [
                'aws', 's3', 'sync',
                s3_path, str(local_path),
                '--profile', profile,
                '--delete'
            ]

            if dry_run:
                cmd.append('--dryrun')

            # Executar comando
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                message = "Sincronização concluída com sucesso!"
                print(f" {message}")
                if callback:
                    callback(True, message, result.stdout)
            else:
                error_msg = result.stderr or "Erro desconhecido"
                print(f" Erro na sincronização: {error_msg}")
                if callback:
                    callback(False, error_msg, result.stdout)

        except subprocess.TimeoutExpired:
            error_msg = "Timeout na sincronização (5 minutos)"
            print(f" {error_msg}")
            if callback:
                callback(False, error_msg, "")
        except Exception as e:
            error_msg = f"Erro na sincronização: {e}"
            print(f" {error_msg}")
            if callback:
                callback(False, error_msg, "")

    def list_bucket_objects(self, bucket_name, prefix="", max_keys=1000):
        """Lista objetos em um bucket S3"""
        try:
            s3 = self.get_s3_client()

            params = {
                'Bucket': bucket_name,
                'MaxKeys': max_keys
            }

            if prefix:
                params['Prefix'] = prefix

            response = s3.list_objects_v2(**params)
            objects = response.get('Contents', [])

            print(f" Encontrados {len(objects)} objetos no bucket {bucket_name}")
            return objects

        except ClientError as e:
            print(f" Erro ao listar objetos do S3: {e}")
            return []
        except Exception as e:
            print(f" Erro inesperado: {e}")
            return []

    def get_object_metadata(self, bucket_name, object_key):
        """Obtém metadados de um objeto S3"""
        try:
            s3 = self.get_s3_client()

            response = s3.head_object(Bucket=bucket_name, Key=object_key)
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'content_type': response.get('ContentType', ''),
                'metadata': response.get('Metadata', {})
            }

        except ClientError as e:
            print(f" Erro ao obter metadados: {e}")
            return None
        except Exception as e:
            print(f" Erro inesperado: {e}")
            return None

    def check_bucket_exists(self, bucket_name):
        """Verifica se um bucket existe e é acessível"""
        try:
            s3 = self.get_s3_client()
            s3.head_bucket(Bucket=bucket_name)
            return True
        except ClientError:
            return False
        except Exception:
            return False

    def parse_s3_path(self, s3_path):
        """Parse de caminho S3 para bucket e key"""
        if not s3_path.startswith('s3://'):
            raise ValueError("Caminho S3 deve começar com 's3://'")

        path_parts = s3_path[5:].split('/', 1)
        bucket = path_parts[0]
        key = path_parts[1] if len(path_parts) > 1 else ""

        return bucket, key

    def validate_s3_path(self, s3_path):
        """Valida se um caminho S3 é válido"""
        try:
            bucket, key = self.parse_s3_path(s3_path)
            return self.check_bucket_exists(bucket)
        except Exception as e:
            print(f" Caminho S3 inválido: {e}")
            return False