import boto3
import json
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError


class StepFunctionsService:
    def __init__(self, auth_service, cache_manager):
        self.auth_service = auth_service
        self.cache_manager = cache_manager

    def get_stepfunctions_client(self):
        """Retorna cliente Step Functions usando a sessão atual"""
        if not self.auth_service.is_authenticated():
            raise Exception("Usuário não autenticado")

        session = self.auth_service.get_current_session()
        return session.client('stepfunctions')

    def retry_with_backoff(self, func, max_retries=3, base_delay=1.0, *args, **kwargs):
        """Executa função com retry e backoff exponencial"""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')

                if error_code in ['Throttling', 'TooManyRequestsException'] and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⏳ Rate limit atingido, aguardando {delay}s antes de tentar novamente...")
                    time.sleep(delay)
                    continue
                else:
                    raise
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⏳ Erro temporário, aguardando {delay}s antes de tentar novamente...")
                    time.sleep(delay)
                    continue
                else:
                    raise

    def fetch_step_functions(self, use_cache=True):
        """Busca Step Functions e seus status usando processamento paralelo otimizado"""
        try:
            profile = self.auth_service.current_profile
            if not profile:
                return []

            # Verificar cache primeiro
            if use_cache:
                cached_data = self.cache_manager.load_cache('step_functions', profile)
                if cached_data:
                    print(f" Step Functions carregados do cache ({len(cached_data)} máquinas)")
                    return cached_data

            sfn_client = self.get_stepfunctions_client()

            def list_state_machines_with_retry():
                return self.retry_with_backoff(sfn_client.list_state_machines)

            print(" Listando Step Functions...")

            # 1. Buscar todas as máquinas de estado
            all_state_machines = []
            next_token = None

            while True:
                try:
                    if next_token:
                        response = list_state_machines_with_retry(nextToken=next_token)
                    else:
                        response = list_state_machines_with_retry()

                    state_machines = response.get('stateMachines', [])
                    all_state_machines.extend(state_machines)

                    next_token = response.get('nextToken')
                    if not next_token:
                        break

                except Exception as e:
                    print(f" Erro ao listar Step Functions: {e}")
                    break

            if not all_state_machines:
                print(" Nenhuma Step Function encontrada")
                return []

            print(f" Encontradas {len(all_state_machines)} Step Functions. Iniciando busca paralela...")

            # 2. Buscar detalhes em paralelo (otimizado)
            step_functions = []
            max_workers = min(10, max(3, len(all_state_machines) // 3))  # Threads limitadas para evitar throttling

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_sm = {
                    executor.submit(
                        self._fetch_single_stepfunction_details,
                        boto3.client('stepfunctions'),
                        sm['name'],
                        sm['stateMachineArn']
                    ): sm['name']
                    for sm in all_state_machines
                }

                completed = 0
                for future in as_completed(future_to_sm):
                    try:
                        sf_data = future.result()
                        step_functions.append(sf_data)
                        completed += 1

                        # Log de progresso a cada 20%
                        if completed % max(1, len(all_state_machines) // 5) == 0:
                            progress = (completed / len(all_state_machines)) * 100
                            print(f"⏳ Progresso Step Functions: {completed}/{len(all_state_machines)} ({progress:.0f}%)")

                    except Exception as e:
                        sm_name = future_to_sm[future]
                        print(f" Erro ao buscar Step Function {sm_name}: {e}")

            elapsed_time = time.time() - start_time
            print(f" Busca Step Functions concluída em {elapsed_time:.1f}s - {len(step_functions)} carregadas")

            # Salvar no cache
            if step_functions:
                self.cache_manager.save_cache('step_functions', profile, step_functions)

            return step_functions

        except Exception as e:
            print(f" Erro ao buscar Step Functions: {e}")
            return []

    def _fetch_single_stepfunction_details(self, sfn_client, sm_name, sm_arn):
        """Busca detalhes de uma única Step Function"""
        try:
            # Informações básicas da máquina de estado
            sm_response = self.retry_with_backoff(
                sfn_client.describe_state_machine,
                stateMachineArn=sm_arn
            )

            # Buscar execuções recentes (apenas 10 mais recentes para performance)
            try:
                executions_response = self.retry_with_backoff(
                    sfn_client.list_executions,
                    stateMachineArn=sm_arn,
                    maxResults=10
                )
                executions = executions_response.get('executions', [])
            except Exception as e:
                print(f" Erro ao buscar execuções de {sm_name}: {e}")
                executions = []

            # Dados da execução mais recente
            last_execution = executions[0] if executions else None

            sf_data = {
                'name': sm_name,
                'arn': sm_arn,
                'definition': sm_response.get('definition', ''),
                'role_arn': sm_response.get('roleArn', 'N/A'),
                'type': sm_response.get('type', 'N/A'),
                'creation_date': sm_response.get('creationDate'),
                'description': sm_response.get('description', ''),
                'logging_configuration': sm_response.get('loggingConfiguration', {}),
                'tracing_configuration': sm_response.get('tracingConfiguration', {}),
                'tags': sm_response.get('tags', []),
                'label': sm_response.get('label', ''),
                'total_executions': len(executions)
            }

            # Informações da execução mais recente
            if last_execution:
                sf_data.update({
                    'last_execution_arn': last_execution.get('executionArn', 'N/A'),
                    'last_execution_name': last_execution.get('name', 'N/A'),
                    'last_execution_status': last_execution.get('status', 'N/A'),
                    'last_execution_start_date': last_execution.get('startDate'),
                    'last_execution_stop_date': last_execution.get('stopDate'),
                    'last_execution_input': last_execution.get('input', ''),
                    'last_execution_output': last_execution.get('output', ''),
                    'last_execution_error': last_execution.get('error', ''),
                    'last_execution_cause': last_execution.get('cause', '')
                })

                # Calcular duração da última execução
                if last_execution.get('startDate') and last_execution.get('stopDate'):
                    duration = (last_execution['stopDate'] - last_execution['startDate']).total_seconds()
                    sf_data['last_execution_duration_seconds'] = duration
                else:
                    sf_data['last_execution_duration_seconds'] = None

            # Status summary para facilitar filtragem
            if last_execution:
                status = last_execution.get('status', 'N/A')
                if status == 'SUCCEEDED':
                    sf_data['status_summary'] = ' Sucesso'
                elif status == 'FAILED':
                    sf_data['status_summary'] = ' Falha'
                elif status == 'RUNNING':
                    sf_data['status_summary'] = ' Executando'
                elif status == 'ABORTED':
                    sf_data['status_summary'] = ' Abortado'
                elif status == 'TIMED_OUT':
                    sf_data['status_summary'] = ' Timeout'
                else:
                    sf_data['status_summary'] = f' {status}'
            else:
                sf_data['status_summary'] = ' Sem execução'

            return sf_data

        except Exception as e:
            print(f" Erro ao buscar detalhes da Step Function {sm_name}: {e}")
            # Retornar dados básicos mesmo com erro
            return {
                'name': sm_name,
                'arn': sm_arn,
                'status_summary': ' Erro ao carregar',
                'error': str(e)
            }

    def start_execution(self, state_machine_arn, execution_name=None, input_data=None):
        """Inicia execução de uma Step Function"""
        try:
            sfn_client = self.get_stepfunctions_client()

            params = {'stateMachineArn': state_machine_arn}

            if execution_name:
                params['name'] = execution_name

            if input_data:
                if isinstance(input_data, dict):
                    params['input'] = json.dumps(input_data)
                else:
                    params['input'] = input_data

            response = self.retry_with_backoff(
                sfn_client.start_execution,
                **params
            )

            execution_arn = response.get('executionArn')
            print(f" Step Function iniciada com ARN: {execution_arn}")

            return execution_arn

        except Exception as e:
            print(f" Erro ao iniciar Step Function: {e}")
            return None

    def stop_execution(self, execution_arn, error=None, cause=None):
        """Para execução de uma Step Function"""
        try:
            sfn_client = self.get_stepfunctions_client()

            params = {'executionArn': execution_arn}

            if error:
                params['error'] = error
            if cause:
                params['cause'] = cause

            response = self.retry_with_backoff(
                sfn_client.stop_execution,
                **params
            )

            print(f" Execução parada: {execution_arn}")
            return True

        except Exception as e:
            print(f" Erro ao parar execução: {e}")
            return False

    def get_execution_history(self, execution_arn, max_results=100):
        """Obtém histórico de execução de uma Step Function"""
        try:
            sfn_client = self.get_stepfunctions_client()

            response = self.retry_with_backoff(
                sfn_client.get_execution_history,
                executionArn=execution_arn,
                maxResults=max_results
            )

            return response.get('events', [])

        except Exception as e:
            print(f" Erro ao obter histórico de execução: {e}")
            return []

    def filter_step_functions(self, step_functions, filter_text="", status_filter=""):
        """Filtra Step Functions baseado nos critérios fornecidos"""
        if not step_functions:
            return []

        filtered_sfs = step_functions

        # Filtro por texto
        if filter_text:
            filter_text = filter_text.lower()
            filtered_sfs = [
                sf for sf in filtered_sfs
                if filter_text in sf.get('name', '').lower() or
                   filter_text in sf.get('status_summary', '').lower() or
                   filter_text in sf.get('description', '').lower()
            ]

        # Filtro por status
        if status_filter and status_filter != "Todos":
            filtered_sfs = [
                sf for sf in filtered_sfs
                if status_filter in sf.get('status_summary', '')
            ]

        return filtered_sfs