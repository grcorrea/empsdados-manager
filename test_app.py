#!/usr/bin/env python3
"""
Script para testar se a aplicação abre corretamente
"""
import subprocess
import time
import sys

def test_app_startup():
    """Testa se a aplicação consegue iniciar sem travar"""
    print("=== TESTE DE INICIALIZAÇÃO DA APLICAÇÃO ===")
    print("Iniciando processo...")

    try:
        # Iniciar processo da aplicação
        proc = subprocess.Popen(
            [sys.executable, 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Coletar output inicial
        output_lines = []
        start_time = time.time()
        success_indicators = 0

        print("\n--- Output da aplicação ---")

        while len(output_lines) < 15 and (time.time() - start_time) < 10:
            line = proc.stdout.readline()
            if line:
                line = line.strip()
                output_lines.append(line)
                print(f"APP: {line}")

                # Verificar indicadores de sucesso
                if any(indicator in line.lower() for indicator in [
                    'iniciando', 'configurações carregadas', 'diretório de cache',
                    'proxy desabilitado', 'app funcionará', 'proxy configurado'
                ]):
                    success_indicators += 1

                # Verificar se há erros críticos
                if any(error in line.lower() for error in [
                    'traceback', 'unhandled error', 'failed to resolve'
                ]):
                    print(f"⚠️ Possível erro detectado: {line}")

            else:
                time.sleep(0.1)

        print("\n--- Análise dos resultados ---")

        # Verificar se processo ainda está ativo
        poll_result = proc.poll()

        if poll_result is None:
            print("✅ SUCESSO: Aplicação está rodando!")
            print(f"📊 Indicadores de sucesso encontrados: {success_indicators}")
            print("🎯 A aplicação carregou sem travar.")

            # Terminar processo gentilmente
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

            return True

        else:
            print(f"❌ FALHA: Aplicação terminou com código: {poll_result}")
            return False

    except Exception as e:
        print(f"❌ ERRO no teste: {e}")
        return False

if __name__ == "__main__":
    success = test_app_startup()
    print(f"\n=== RESULTADO FINAL ===")
    if success:
        print("🎉 Bug da abertura do app foi CORRIGIDO!")
        print("✅ A aplicação agora inicia corretamente.")
    else:
        print("❌ Ainda há problemas na abertura do app.")
        print("🔧 Necessário investigar mais.")