import boto3
import os
from typing import Dict, Any, List
from botocore.exceptions import ClientError, NoCredentialsError


class S3Service:
    def __init__(self):
        self.session = boto3.Session()

    def _get_client(self):
        try:
            return self.session.client('s3')
        except NoCredentialsError:
            raise Exception("Credenciais AWS não encontradas. Faça login no AWS SSO primeiro.")

    def list_buckets(self) -> Dict[str, Any]:
        try:
            s3 = self._get_client()
            response = s3.list_buckets()

            buckets = []
            for bucket in response['Buckets']:
                buckets.append({
                    'Name': bucket['Name'],
                    'CreationDate': bucket['CreationDate'].strftime('%d/%m/%Y %H:%M:%S')
                })

            return {"success": True, "data": buckets}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def list_objects(self, bucket_name: str, prefix: str = "") -> Dict[str, Any]:
        try:
            s3 = self._get_client()

            kwargs = {'Bucket': bucket_name, 'MaxKeys': 1000}
            if prefix:
                kwargs['Prefix'] = prefix

            response = s3.list_objects_v2(**kwargs)

            objects = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    objects.append({
                        'Key': obj['Key'],
                        'Size': self._format_size(obj['Size']),
                        'LastModified': obj['LastModified'].strftime('%d/%m/%Y %H:%M:%S'),
                        'StorageClass': obj.get('StorageClass', 'STANDARD')
                    })

            # Adicionar "folders" (prefixos comuns)
            folders = []
            if 'CommonPrefixes' in response:
                for prefix_info in response['CommonPrefixes']:
                    folders.append({
                        'Key': prefix_info['Prefix'],
                        'Type': 'FOLDER',
                        'Size': '-',
                        'LastModified': '-',
                        'StorageClass': 'FOLDER'
                    })

            return {"success": True, "data": {"objects": objects, "folders": folders}}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def upload_file(self, file_path: str, bucket_name: str, object_key: str = None) -> Dict[str, Any]:
        try:
            if not os.path.exists(file_path):
                return {"success": False, "error": "Arquivo não encontrado"}

            s3 = self._get_client()

            if not object_key:
                object_key = os.path.basename(file_path)

            s3.upload_file(file_path, bucket_name, object_key)

            return {
                "success": True,
                "message": f"Arquivo {object_key} enviado para {bucket_name} com sucesso"
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"Erro inesperado: {str(e)}"}

    def download_file(self, bucket_name: str, object_key: str, download_path: str) -> Dict[str, Any]:
        try:
            s3 = self._get_client()

            # Criar diretório se não existir
            os.makedirs(os.path.dirname(download_path), exist_ok=True)

            s3.download_file(bucket_name, object_key, download_path)

            return {
                "success": True,
                "message": f"Arquivo {object_key} baixado para {download_path} com sucesso"
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"Erro inesperado: {str(e)}"}

    def delete_object(self, bucket_name: str, object_key: str) -> Dict[str, Any]:
        try:
            s3 = self._get_client()
            s3.delete_object(Bucket=bucket_name, Key=object_key)

            return {
                "success": True,
                "message": f"Arquivo {object_key} deletado do bucket {bucket_name} com sucesso"
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def get_object_info(self, bucket_name: str, object_key: str) -> Dict[str, Any]:
        try:
            s3 = self._get_client()
            response = s3.head_object(Bucket=bucket_name, Key=object_key)

            info = {
                'Key': object_key,
                'Size': self._format_size(response['ContentLength']),
                'LastModified': response['LastModified'].strftime('%d/%m/%Y %H:%M:%S'),
                'ContentType': response.get('ContentType', 'N/A'),
                'ETag': response.get('ETag', 'N/A').strip('"'),
                'StorageClass': response.get('StorageClass', 'STANDARD'),
                'Metadata': response.get('Metadata', {})
            }

            return {"success": True, "data": info}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def create_presigned_url(self, bucket_name: str, object_key: str, expiration: int = 3600) -> Dict[str, Any]:
        try:
            s3 = self._get_client()

            url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )

            return {
                "success": True,
                "data": {
                    "url": url,
                    "expiration_seconds": expiration,
                    "expiration_hours": expiration / 3600
                }
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1

        return f"{size_bytes:.1f} {size_names[i]}"