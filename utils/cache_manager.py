import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class CacheManager:
    def __init__(self):
        self.cache_dir = Path.home() / ".empsdados_cache"
        self.ensure_cache_directory()

    def ensure_cache_directory(self):
        """Garante que o diretório de cache existe"""
        try:
            self.cache_dir.mkdir(exist_ok=True)
            print(f"Diretório de cache: {self.cache_dir}")
        except Exception as e:
            print(f"Erro ao criar diretório de cache: {e}")

    def get_cache_filename(self, cache_type, profile):
        """Gera nome do arquivo de cache"""
        safe_profile = "".join(c if c.isalnum() or c in '-_' else '_' for c in profile)
        return self.cache_dir / f"{cache_type}_{safe_profile}.json"

    def is_cache_fresh(self, cache_type, profile, minutes_threshold=15):
        """Verifica se o cache está válido"""
        cache_file = self.get_cache_filename(cache_type, profile)

        if not cache_file.exists():
            return False

        try:
            # Verificar idade do arquivo
            file_mod_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - file_mod_time > timedelta(minutes=minutes_threshold):
                return False

            # Verificar se há dados válidos no arquivo
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return self.is_cache_fresh_by_data(data, minutes_threshold)

        except Exception as e:
            print(f"Erro ao verificar cache: {e}")
            return False

    def is_cache_fresh_by_data(self, cache_data, minutes_threshold=15):
        """Verifica se os dados de cache são válidos baseado no timestamp"""
        try:
            if not isinstance(cache_data, dict) or 'timestamp' not in cache_data:
                return False

            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            return datetime.now() - cache_time <= timedelta(minutes=minutes_threshold)

        except Exception as e:
            print(f"Erro ao verificar timestamp do cache: {e}")
            return False

    def save_cache(self, cache_type, profile, data):
        """Salva dados no cache"""
        try:
            cache_file = self.get_cache_filename(cache_type, profile)

            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'profile': profile,
                'data': data
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)

            print(f"Cache salvo: {cache_file.name}")
            return True

        except Exception as e:
            print(f"Erro ao salvar cache {cache_type}: {e}")
            return False

    def load_cache(self, cache_type, profile):
        """Carrega dados do cache"""
        try:
            cache_file = self.get_cache_filename(cache_type, profile)

            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            if self.is_cache_fresh_by_data(cache_data):
                print(f"Cache carregado: {cache_file.name}")
                return cache_data.get('data', [])
            else:
                print(f"Cache expirado: {cache_file.name}")
                return None

        except Exception as e:
            print(f"Erro ao carregar cache {cache_type}: {e}")
            return None

    def clear_cache(self, cache_type=None, profile=None):
        """Limpa cache específico ou todos"""
        try:
            if cache_type and profile:
                cache_file = self.get_cache_filename(cache_type, profile)
                if cache_file.exists():
                    cache_file.unlink()
                    print(f"Cache removido: {cache_file.name}")
            else:
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                print("Todos os caches foram removidos")

        except Exception as e:
            print(f"Erro ao limpar cache: {e}")

    def get_cache_info(self):
        """Retorna informações sobre os caches"""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)

            return {
                'count': len(cache_files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'files': [f.name for f in cache_files]
            }
        except Exception as e:
            print(f"Erro ao obter informações do cache: {e}")
            return {'count': 0, 'total_size_mb': 0, 'files': []}