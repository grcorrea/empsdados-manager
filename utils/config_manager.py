import configparser
import os
from pathlib import Path


class ConfigManager:
    def __init__(self):
        self.config_file = Path.home() / "empsdados_manager_config.ini"
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        """Carrega configurações do arquivo INI"""
        if self.config_file.exists():
            try:
                self.config.read(self.config_file, encoding='utf-8')
                print(f"Configurações carregadas de: {self.config_file}")
            except Exception as e:
                print(f"Erro ao carregar configurações: {e}")
                self._create_default_config()
        else:
            print(f"Arquivo de configuração não encontrado, criando padrão: {self.config_file}")
            self._create_default_config()

    def _create_default_config(self):
        """Cria configuração padrão"""
        self.config['DEFAULT'] = {
            'refresh_interval': '30',
            'export_folder': str(Path.home() / "Downloads"),
            'auto_refresh_enabled': 'False'
        }

        self.config['AWS'] = {
            'default_profile': '',
            'last_used_profile': ''
        }

        self.config['UI'] = {
            'theme_mode': 'system',
            'window_width': '1200',
            'window_height': '800'
        }

        self.save_config()

    def save_config(self):
        """Salva configurações no arquivo INI"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    def get(self, section, key, fallback=None):
        """Obtém um valor de configuração"""
        try:
            return self.config.get(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    def set(self, section, key, value):
        """Define um valor de configuração"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))

    def save_filter_text(self, filter_type, text):
        """Salva texto de filtro"""
        if not self.config.has_section('Filters'):
            self.config.add_section('Filters')
        self.config.set('Filters', filter_type, text)
        self.save_config()

    def load_filter_text(self, filter_type):
        """Carrega texto de filtro salvo"""
        return self.get('Filters', filter_type, '')