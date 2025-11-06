import os
import time
import ctypes
import subprocess
import sys
from pathlib import Path


class WindowsHelper:
    @staticmethod
    def minimize_all_windows():
        """Minimiza todas as janelas no Windows"""
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(0x5B, 0, 0, 0)  # Windows key down
            user32.keybd_event(0x4D, 0, 0, 0)  # M key down
            user32.keybd_event(0x4D, 0, 2, 0)  # M key up
            user32.keybd_event(0x5B, 0, 2, 0)  # Windows key up
            print("Todas as janelas foram minimizadas")
            return True
        except Exception as e:
            print(f"Erro ao minimizar janelas: {e}")
            return False

    @staticmethod
    def bring_app_to_front():
        """Traz a aplicação para frente"""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            hWnd = user32.GetForegroundWindow()
            if hWnd:
                user32.ShowWindow(hWnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hWnd)
                user32.BringWindowToTop(hWnd)
                print("Aplicação trazida para frente")
                return True
        except Exception as e:
            print(f"Erro ao trazer aplicação para frente: {e}")
            return False


class SystemHelper:
    @staticmethod
    def setup_proxy_environment():
        """Configura variáveis de ambiente do proxy (sempre define as URLs)"""
        # Sempre definir as variáveis de ambiente do proxy
        os.environ['HTTP_PROXY'] = "http://proxynew.itau:8080"
        os.environ['HTTPS_PROXY'] = "http://proxynew.itau:8080"
        print("Variáveis de ambiente do proxy definidas")

    @staticmethod
    def open_folder(folder_path):
        """Abre pasta no explorador de arquivos"""
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", folder_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])
            print(f"Pasta aberta: {folder_path}")
            return True
        except Exception as e:
            print(f"Erro ao abrir pasta: {e}")
            return False

    @staticmethod
    def get_downloads_folder():
        """Retorna o caminho da pasta Downloads do usuário"""
        return Path.home() / "Downloads"

    @staticmethod
    def ensure_folder_exists(folder_path):
        """Garante que uma pasta existe"""
        try:
            Path(folder_path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"Erro ao criar pasta {folder_path}: {e}")
            return False


class DateTimeHelper:
    @staticmethod
    def format_duration(seconds):
        """Formata duração em segundos para string legível"""
        if seconds is None:
            return "N/A"

        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)

            if hours > 0:
                return f"{hours}h {minutes}m {secs}s"
            elif minutes > 0:
                return f"{minutes}m {secs}s"
            else:
                return f"{secs}s"
        except:
            return "N/A"

    @staticmethod
    def format_timestamp(timestamp_str):
        """Formata timestamp para exibição"""
        if not timestamp_str:
            return "N/A"

        try:
            from datetime import datetime
            if isinstance(timestamp_str, str):
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                dt = timestamp_str

            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except:
            return str(timestamp_str)


class DataHelper:
    @staticmethod
    def safe_get(dictionary, key, default="N/A"):
        """Obtém valor do dicionário de forma segura"""
        try:
            return dictionary.get(key, default) if dictionary else default
        except:
            return default

    @staticmethod
    def format_file_size(size_bytes):
        """Formata tamanho de arquivo em bytes para string legível"""
        if size_bytes is None:
            return "N/A"

        try:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} PB"
        except:
            return "N/A"

    @staticmethod
    def clean_filename(filename):
        """Remove caracteres inválidos do nome do arquivo"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename