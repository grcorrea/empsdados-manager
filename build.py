import subprocess
import sys
import os


def build_executable():
    try:
        print("🔨 Construindo executável Windows...")

        command = [
            sys.executable,
            "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name=AWS-Manager",
            "--hidden-import=flet",
            "--hidden-import=boto3",
            "--hidden-import=botocore",
            "main.py"
        ]

        result = subprocess.run(command, check=True)

        if result.returncode == 0:
            print("✅ Executável criado com sucesso em dist/AWS-Manager.exe")
        else:
            print("❌ Erro ao criar executável")

    except subprocess.CalledProcessError as e:
        print(f"❌ Erro durante a construção: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")


if __name__ == "__main__":
    build_executable()