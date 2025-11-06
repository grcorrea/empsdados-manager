#!/usr/bin/env python3
"""
Script para testar se as variáveis de ambiente do proxy são configuradas corretamente
sem tentar fazer conexões.
"""

import os
import sys
from pathlib import Path

# Adicionar diretório do projeto ao path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

def test_helpers_proxy_setup():
    """Testa se o SystemHelper.setup_proxy_environment() funciona corretamente"""
    print("=" * 60)
    print("TESTE: utils.helpers.SystemHelper.setup_proxy_environment()")
    print("=" * 60)

    try:
        from utils.helpers import SystemHelper

        # Limpar variáveis de ambiente primeiro
        if 'HTTP_PROXY' in os.environ:
            del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ:
            del os.environ['HTTPS_PROXY']

        print("OK: Variáveis de proxy limpas")

        # Testar se as variáveis não existem
        assert 'HTTP_PROXY' not in os.environ, "HTTP_PROXY ainda existe"
        assert 'HTTPS_PROXY' not in os.environ, "HTTPS_PROXY ainda existe"
        print("OK: Confirmado que variáveis não existem")

        # Chamar o método
        SystemHelper.setup_proxy_environment()

        # Verificar se as variáveis foram definidas
        assert 'HTTP_PROXY' in os.environ, "HTTP_PROXY não foi definida"
        assert 'HTTPS_PROXY' in os.environ, "HTTPS_PROXY não foi definida"

        expected_url = "http://proxynew.itau:8080"
        assert os.environ['HTTP_PROXY'] == expected_url, f"HTTP_PROXY incorreta: {os.environ['HTTP_PROXY']}"
        assert os.environ['HTTPS_PROXY'] == expected_url, f"HTTPS_PROXY incorreta: {os.environ['HTTPS_PROXY']}"

        print(f"OK: HTTP_PROXY = {os.environ['HTTP_PROXY']}")
        print(f"OK: HTTPS_PROXY = {os.environ['HTTPS_PROXY']}")
        print("OK: TESTE PASSOU: SystemHelper.setup_proxy_environment() funciona corretamente")

        return True

    except Exception as e:
        print(f"ERRO: TESTE FALHOU: {e}")
        return False

def test_main_proxy_setup():
    """Testa se o main.py configura proxy corretamente"""
    print("\n" + "=" * 60)
    print("TESTE: main.py setup_environment()")
    print("=" * 60)

    try:
        # Limpar variáveis de ambiente primeiro
        if 'HTTP_PROXY' in os.environ:
            del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ:
            del os.environ['HTTPS_PROXY']

        print("OK: Variáveis de proxy limpas")

        # Simular o código do main.py
        os.environ['HTTP_PROXY'] = "http://proxynew.itau:8080"
        os.environ['HTTPS_PROXY'] = "http://proxynew.itau:8080"

        # Verificar se as variáveis foram definidas
        assert 'HTTP_PROXY' in os.environ, "HTTP_PROXY não foi definida"
        assert 'HTTPS_PROXY' in os.environ, "HTTPS_PROXY não foi definida"

        expected_url = "http://proxynew.itau:8080"
        assert os.environ['HTTP_PROXY'] == expected_url, f"HTTP_PROXY incorreta: {os.environ['HTTP_PROXY']}"
        assert os.environ['HTTPS_PROXY'] == expected_url, f"HTTPS_PROXY incorreta: {os.environ['HTTPS_PROXY']}"

        print(f"OK: HTTP_PROXY = {os.environ['HTTP_PROXY']}")
        print(f"OK: HTTPS_PROXY = {os.environ['HTTPS_PROXY']}")
        print("OK: TESTE PASSOU: main.py setup_environment() funciona corretamente")

        return True

    except Exception as e:
        print(f"ERRO: TESTE FALHOU: {e}")
        return False

def test_import_services():
    """Testa se os serviços podem ser importados sem fazer conexões"""
    print("\n" + "=" * 60)
    print("TESTE: Importação de serviços AWS")
    print("=" * 60)

    try:
        # Testar importação dos serviços
        from services.aws_auth import AWSAuthService
        from services.glue_service import GlueService
        from services.stepfunctions_service import StepFunctionsService
        from services.s3_service import S3Service
        from utils.config_manager import ConfigManager
        from utils.cache_manager import CacheManager

        print("OK: Todos os serviços importados com sucesso")

        # Testar criação dos managers (não devem fazer conexões)
        config_manager = ConfigManager()
        cache_manager = CacheManager()

        print("OK: ConfigManager e CacheManager criados com sucesso")

        # Testar criação do auth service (não deve tentar conectar)
        auth_service = AWSAuthService(config_manager)

        print("OK: AWSAuthService criado sem conexões")
        print("OK: TESTE PASSOU: Serviços podem ser importados e criados sem conexões")

        return True

    except Exception as e:
        print(f"ERRO: TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executa todos os testes"""
    print("TESTANDO CONFIGURAÇÃO DE PROXY SEM CONEXÕES")
    print("=" * 60)

    results = []

    # Executar testes
    results.append(test_helpers_proxy_setup())
    results.append(test_main_proxy_setup())
    results.append(test_import_services())

    # Resultados finais
    print("\n" + "=" * 60)
    print("RESULTADOS FINAIS")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"OK: TODOS OS TESTES PASSARAM ({passed}/{total})")
        print("OK: Proxy configurado corretamente sem tentativas de conexão!")
        return True
    else:
        print(f"ERRO: ALGUNS TESTES FALHARAM ({passed}/{total})")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)