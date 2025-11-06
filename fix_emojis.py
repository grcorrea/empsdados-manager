#!/usr/bin/env python3
"""
Script para remover emojis problemáticos dos arquivos Python
que causam erro de codificação Unicode no Windows.
"""

import os
import re
from pathlib import Path

# Mapeamento de emojis para texto
EMOJI_REPLACEMENTS = {
    '🚀': '',
    '✅': '',
    '❌': '',
    '⚠️': '',
    '📁': '',
    '📋': '',
    '💾': '',
    '📦': '',
    '⏰': '',
    '🔍': '',
    '🔄': '',
    '🗑️': '',
    '📊': '',
    '💡': '',
    '⚡': '',
    '🎯': '',
    '🔧': '',
    '🌟': '',
    '💻': '',
    '🎨': '',
    '❓': '',
    '🪟': '',
    '🔝': '',
    '🌐': '',
    '🛑': '',
    '✨': '',
    '🔥': '',
}

def remove_emojis_from_file(file_path):
    """Remove emojis de um arquivo específico"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Remover emojis
        for emoji, replacement in EMOJI_REPLACEMENTS.items():
            content = content.replace(emoji, replacement)

        # Limpar espaços extras deixados pela remoção
        content = re.sub(r'print\(f?""\s*([^"]*)', r'print(f"\1', content)
        content = re.sub(r'print\(""\s*([^"]*)', r'print("\1', content)

        # Salvar apenas se houve mudanças
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"OK Emojis removidos de: {file_path}")
            return True
        else:
            print(f"- Nenhum emoji encontrado em: {file_path}")
            return False

    except Exception as e:
        print(f"ERRO ao processar {file_path}: {e}")
        return False

def main():
    """Função principal"""
    print("Removendo emojis problemáticos dos arquivos Python...")
    print("-" * 50)

    # Diretórios para processar
    directories = ['services', 'utils', 'ui']

    # Arquivo principal
    files_to_process = ['main.py', 'main_refactored.py']

    total_files = 0
    processed_files = 0

    # Processar arquivos principais
    for file_name in files_to_process:
        if os.path.exists(file_name):
            total_files += 1
            if remove_emojis_from_file(file_name):
                processed_files += 1

    # Processar diretórios
    for directory in directories:
        if os.path.exists(directory):
            for py_file in Path(directory).glob('**/*.py'):
                total_files += 1
                if remove_emojis_from_file(py_file):
                    processed_files += 1

    print("-" * 50)
    print(f"Processamento concluído!")
    print(f"Arquivos verificados: {total_files}")
    print(f"Arquivos modificados: {processed_files}")

    if processed_files > 0:
        print("\nEmojis removidos com sucesso!")
        print("Agora o código deve executar sem erros de Unicode no Windows.")
    else:
        print("\nNenhum emoji problemático encontrado.")

if __name__ == "__main__":
    main()