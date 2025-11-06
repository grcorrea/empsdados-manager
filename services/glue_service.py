import boto3
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError


class GlueService:
    def __init__(self, auth_service, cache_manager):
        self.auth_service = auth_service
        self.cache_manager = cache_manager

    def get_glue_client(self):
        """Retorna cliente Glue usando a sessão atual"""
        if not self.auth_service.is_authenticated():
            raise Exception("Usuário não autenticado")

        session = self.auth_service.get_current_session()
        return session.client('glue')

    def fetch_glue_jobs(self, use_cache=True):
        """Busca jobs do AWS Glue e seus status usando processamento paralelo otimizado"""
        try:
            profile = self.auth_service.current_profile
            if not profile:
                return []

            # Verificar cache primeiro
            if use_cache:
                cached_data = self.cache_manager.load_cache('glue_jobs', profile)
                if cached_data:
                    print(f" Jobs Glue carregados do cache ({len(cached_data)} jobs)")
                    return cached_data

            glue_client = self.get_glue_client()

            # 1. Buscar todos os jobs (rápido)
            print(" Listando jobs do Glue...")
            paginator = glue_client.get_paginator('get_jobs')
            all_job_names = []

            for page in paginator.paginate():
                for job in page['Jobs']:
                    all_job_names.append(job['Name'])

            if not all_job_names:
                print(" Nenhum job encontrado na conta")
                return []

            print(f" Encontrados {len(all_job_names)} jobs Glue. Iniciando busca paralela...")

            # 2. Buscar detalhes em paralelo (otimizado)
            jobs = []
            max_workers = min(15, max(5, len(all_job_names) // 4))  # Threads adaptáveis

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Criar client separado para cada thread (recomendação AWS)
                future_to_job = {
                    executor.submit(self._fetch_single_job_details, boto3.client('glue'), job_name): job_name
                    for job_name in all_job_names
                }

                completed = 0
                for future in as_completed(future_to_job):
                    try:
                        job_data = future.result()
                        jobs.append(job_data)
                        completed += 1

                        # Log de progresso a cada 10%
                        if completed % max(1, len(all_job_names) // 10) == 0:
                            progress = (completed / len(all_job_names)) * 100
                            print(f"⏳ Progresso: {completed}/{len(all_job_names)} jobs ({progress:.0f}%)")

                    except Exception as e:
                        job_name = future_to_job[future]
                        print(f" Erro ao buscar job {job_name}: {e}")

            elapsed_time = time.time() - start_time
            print(f" Busca concluída em {elapsed_time:.1f}s - {len(jobs)} jobs carregados")

            # Salvar no cache
            if jobs:
                self.cache_manager.save_cache('glue_jobs', profile, jobs)

            return jobs

        except Exception as e:
            print(f" Erro ao buscar jobs Glue: {e}")
            return []

    def _fetch_single_job_details(self, glue_client, job_name):
        """Busca detalhes de um único job Glue"""
        try:
            # Informações básicas do job
            job_response = glue_client.get_job(JobName=job_name)
            job = job_response['Job']

            # Buscar execuções recentes (apenas as 5 mais recentes para performance)
            runs_response = glue_client.get_job_runs(
                JobName=job_name,
                MaxResults=5
            )
            runs = runs_response.get('JobRuns', [])

            # Dados do job mais recente
            last_run = runs[0] if runs else None

            job_data = {
                'name': job_name,
                'role': job.get('Role', 'N/A'),
                'created_on': job.get('CreatedOn'),
                'last_modified_on': job.get('LastModifiedOn'),
                'glue_version': job.get('GlueVersion', 'N/A'),
                'worker_type': job.get('WorkerType', 'N/A'),
                'number_of_workers': job.get('NumberOfWorkers', 'N/A'),
                'max_capacity': job.get('MaxCapacity', 'N/A'),
                'timeout': job.get('Timeout', 'N/A'),
                'max_retries': job.get('MaxRetries', 'N/A'),
                'allocated_capacity': job.get('AllocatedCapacity', 'N/A'),
                'command': job.get('Command', {}),
                'default_arguments': job.get('DefaultArguments', {}),
                'description': job.get('Description', ''),
                'connections': job.get('Connections', {}).get('Connections', []),
                'security_configuration': job.get('SecurityConfiguration', ''),
                'total_runs': len(runs),
                'job_bookmark': job.get('JobBookmark', 'N/A'),
                'non_overridable_arguments': job.get('NonOverridableArguments', {}),
                'execution_class': job.get('ExecutionClass', 'N/A'),
                'source_control_details': job.get('SourceControlDetails', {})
            }

            # Informações da execução mais recente
            if last_run:
                job_data.update({
                    'last_run_id': last_run.get('Id', 'N/A'),
                    'last_run_state': last_run.get('JobRunState', 'N/A'),
                    'started_on': last_run.get('StartedOn'),
                    'completed_on': last_run.get('CompletedOn'),
                    'execution_time': last_run.get('ExecutionTime', 0),
                    'last_run_dpu_seconds': last_run.get('DPUSeconds', 0),
                    'max_capacity_run': last_run.get('MaxCapacity', 0),
                    'worker_type_run': last_run.get('WorkerType', 'N/A'),
                    'number_of_workers_run': last_run.get('NumberOfWorkers', 0),
                    'allocated_capacity_run': last_run.get('AllocatedCapacity', 0),
                    'attempt': last_run.get('Attempt', 0),
                    'previous_run_id': last_run.get('PreviousRunId', ''),
                    'trigger_name': last_run.get('TriggerName', ''),
                    'job_mode': last_run.get('JobMode', 'N/A'),
                    'error_message': last_run.get('ErrorMessage', ''),
                    'log_group_name': last_run.get('LogGroupName', ''),
                    'notification_property': last_run.get('NotificationProperty', {}),
                    'glue_version_run': last_run.get('GlueVersion', 'N/A')
                })

                # Calcular duração da última execução
                if last_run.get('StartedOn') and last_run.get('CompletedOn'):
                    duration = (last_run['CompletedOn'] - last_run['StartedOn']).total_seconds()
                    job_data['duration_seconds'] = duration
                else:
                    job_data['duration_seconds'] = None

            # Status summary para facilitar filtragem
            if last_run:
                state = last_run.get('JobRunState', 'N/A')
                if state == 'SUCCEEDED':
                    job_data['status_summary'] = ' Sucesso'
                elif state == 'FAILED':
                    job_data['status_summary'] = ' Falha'
                elif state == 'RUNNING':
                    job_data['status_summary'] = ' Executando'
                elif state == 'STOPPED':
                    job_data['status_summary'] = '⏹️ Parado'
                elif state == 'STOPPING':
                    job_data['status_summary'] = '⏸️ Parando'
                elif state == 'TIMEOUT':
                    job_data['status_summary'] = ' Timeout'
                else:
                    job_data['status_summary'] = f' {state}'
            else:
                job_data['status_summary'] = ' Sem execução'

            return job_data

        except Exception as e:
            print(f" Erro ao buscar detalhes do job {job_name}: {e}")
            # Retornar dados básicos mesmo com erro
            return {
                'name': job_name,
                'status_summary': ' Erro ao carregar',
                'error': str(e)
            }

    def get_job_runs(self, job_name, max_results=50):
        """Busca execuções de um job específico"""
        try:
            glue_client = self.get_glue_client()

            response = glue_client.get_job_runs(
                JobName=job_name,
                MaxResults=max_results
            )

            return response.get('JobRuns', [])

        except Exception as e:
            print(f" Erro ao buscar execuções do job {job_name}: {e}")
            return []

    def start_job_run(self, job_name, arguments=None):
        """Inicia execução de um job"""
        try:
            glue_client = self.get_glue_client()

            params = {'JobName': job_name}
            if arguments:
                params['Arguments'] = arguments

            response = glue_client.start_job_run(**params)

            run_id = response.get('JobRunId')
            print(f" Job {job_name} iniciado com ID: {run_id}")

            return run_id

        except Exception as e:
            print(f" Erro ao iniciar job {job_name}: {e}")
            return None

    def stop_job_run(self, job_name, job_run_id):
        """Para execução de um job"""
        try:
            glue_client = self.get_glue_client()

            response = glue_client.batch_stop_job_run(
                JobName=job_name,
                JobRunIds=[job_run_id]
            )

            print(f" Job {job_name} (ID: {job_run_id}) solicitado para parar")
            return True

        except Exception as e:
            print(f" Erro ao parar job {job_name}: {e}")
            return False

    def delete_job(self, job_name):
        """Deleta um job"""
        try:
            glue_client = self.get_glue_client()

            glue_client.delete_job(JobName=job_name)
            print(f" Job {job_name} deletado com sucesso")

            return True

        except Exception as e:
            print(f" Erro ao deletar job {job_name}: {e}")
            return False

    def filter_jobs(self, jobs, filter_text="", squad_filter="", rt_filter=""):
        """Filtra jobs baseado nos critérios fornecidos"""
        if not jobs:
            return []

        filtered_jobs = jobs

        # Filtro por texto
        if filter_text:
            filter_text = filter_text.lower()
            filtered_jobs = [
                job for job in filtered_jobs
                if filter_text in job.get('name', '').lower() or
                   filter_text in job.get('status_summary', '').lower() or
                   filter_text in job.get('role', '').lower()
            ]

        # Filtro por Squad
        if squad_filter and squad_filter != "Todos":
            filtered_jobs = [
                job for job in filtered_jobs
                if squad_filter.lower() in job.get('name', '').lower()
            ]

        # Filtro por RT
        if rt_filter and rt_filter != "Todos":
            filtered_jobs = [
                job for job in filtered_jobs
                if rt_filter.lower() in job.get('name', '').lower()
            ]

        return filtered_jobs