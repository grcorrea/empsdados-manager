import boto3
import json
from typing import Dict, Any, List
from botocore.exceptions import ClientError, NoCredentialsError


class GlueService:
    def __init__(self):
        self.session = boto3.Session()

    def _get_client(self):
        try:
            return self.session.client('glue')
        except NoCredentialsError:
            raise Exception("Credenciais AWS não encontradas. Faça login no AWS SSO primeiro.")

    def list_jobs(self) -> Dict[str, Any]:
        try:
            glue = self._get_client()
            response = glue.get_jobs()

            jobs = []
            for job in response['Jobs']:
                jobs.append({
                    'Name': job['Name'],
                    'Description': job.get('Description', 'N/A'),
                    'Role': job['Role'],
                    'CreatedOn': job['CreatedOn'].strftime('%d/%m/%Y %H:%M:%S'),
                    'LastModifiedOn': job['LastModifiedOn'].strftime('%d/%m/%Y %H:%M:%S'),
                    'ExecutionProperty': job.get('ExecutionProperty', {}),
                    'Command': job.get('Command', {}),
                    'DefaultArguments': job.get('DefaultArguments', {}),
                    'MaxRetries': job.get('MaxRetries', 0),
                    'Timeout': job.get('Timeout', 0),
                    'MaxCapacity': job.get('MaxCapacity', 0),
                    'WorkerType': job.get('WorkerType', 'Standard'),
                    'NumberOfWorkers': job.get('NumberOfWorkers', 0),
                    'GlueVersion': job.get('GlueVersion', '1.0')
                })

            return {"success": True, "data": jobs}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def get_job_details(self, job_name: str) -> Dict[str, Any]:
        try:
            glue = self._get_client()
            response = glue.get_job(JobName=job_name)

            job = response['Job']
            job_details = {
                'Name': job['Name'],
                'Description': job.get('Description', 'N/A'),
                'Role': job['Role'],
                'CreatedOn': job['CreatedOn'].strftime('%d/%m/%Y %H:%M:%S'),
                'LastModifiedOn': job['LastModifiedOn'].strftime('%d/%m/%Y %H:%M:%S'),
                'ExecutionProperty': job.get('ExecutionProperty', {}),
                'Command': job.get('Command', {}),
                'DefaultArguments': job.get('DefaultArguments', {}),
                'Connections': job.get('Connections', {}),
                'MaxRetries': job.get('MaxRetries', 0),
                'AllocatedCapacity': job.get('AllocatedCapacity', 0),
                'Timeout': job.get('Timeout', 0),
                'MaxCapacity': job.get('MaxCapacity', 0),
                'WorkerType': job.get('WorkerType', 'Standard'),
                'NumberOfWorkers': job.get('NumberOfWorkers', 0),
                'SecurityConfiguration': job.get('SecurityConfiguration', 'N/A'),
                'NotificationProperty': job.get('NotificationProperty', {}),
                'GlueVersion': job.get('GlueVersion', '1.0')
            }

            return {"success": True, "data": job_details}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def list_job_runs(self, job_name: str, max_results: int = 100) -> Dict[str, Any]:
        try:
            glue = self._get_client()
            response = glue.get_job_runs(JobName=job_name, MaxResults=max_results)

            job_runs = []
            for run in response['JobRuns']:
                job_run = {
                    'Id': run['Id'],
                    'JobName': run['JobName'],
                    'JobRunState': run['JobRunState'],
                    'StartedOn': run.get('StartedOn', '').strftime('%d/%m/%Y %H:%M:%S') if run.get('StartedOn') else 'N/A',
                    'CompletedOn': run.get('CompletedOn', '').strftime('%d/%m/%Y %H:%M:%S') if run.get('CompletedOn') else 'N/A',
                    'ExecutionTime': run.get('ExecutionTime', 0),
                    'LastModifiedOn': run.get('LastModifiedOn', '').strftime('%d/%m/%Y %H:%M:%S') if run.get('LastModifiedOn') else 'N/A',
                    'Arguments': run.get('Arguments', {}),
                    'ErrorMessage': run.get('ErrorMessage', 'N/A'),
                    'LogGroupName': run.get('LogGroupName', 'N/A'),
                    'WorkerType': run.get('WorkerType', 'Standard'),
                    'NumberOfWorkers': run.get('NumberOfWorkers', 0),
                    'MaxCapacity': run.get('MaxCapacity', 0),
                    'Timeout': run.get('Timeout', 0),
                    'GlueVersion': run.get('GlueVersion', '1.0')
                }

                # Calcular duração se possível
                if run.get('StartedOn') and run.get('CompletedOn'):
                    duration = run['CompletedOn'] - run['StartedOn']
                    job_run['Duration'] = str(duration).split('.')[0]  # Remove microsegundos
                else:
                    job_run['Duration'] = 'N/A'

                job_runs.append(job_run)

            return {"success": True, "data": job_runs}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def start_job_run(self, job_name: str, arguments: Dict[str, str] = None) -> Dict[str, Any]:
        try:
            glue = self._get_client()

            kwargs = {'JobName': job_name}
            if arguments:
                kwargs['Arguments'] = arguments

            response = glue.start_job_run(**kwargs)

            return {
                "success": True,
                "message": f"Job '{job_name}' iniciado com sucesso",
                "data": {
                    'JobRunId': response['JobRunId']
                }
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def stop_job_run(self, job_name: str, job_run_id: str) -> Dict[str, Any]:
        try:
            glue = self._get_client()
            response = glue.batch_stop_job_run(
                JobName=job_name,
                JobRunIds=[job_run_id]
            )

            if response['SuccessfulSubmissions']:
                return {
                    "success": True,
                    "message": f"Job run '{job_run_id}' parado com sucesso"
                }
            else:
                error_msg = "Erro desconhecido"
                if response['Errors']:
                    error_msg = response['Errors'][0].get('ErrorDetail', {}).get('ErrorMessage', error_msg)

                return {"success": False, "error": error_msg}

        except ClientError as e:
            return {"success": False, "error": str(e)}

    def get_job_run_details(self, job_name: str, job_run_id: str) -> Dict[str, Any]:
        try:
            glue = self._get_client()
            response = glue.get_job_run(JobName=job_name, RunId=job_run_id)

            job_run = response['JobRun']
            details = {
                'Id': job_run['Id'],
                'JobName': job_run['JobName'],
                'JobRunState': job_run['JobRunState'],
                'StartedOn': job_run.get('StartedOn', '').strftime('%d/%m/%Y %H:%M:%S') if job_run.get('StartedOn') else 'N/A',
                'CompletedOn': job_run.get('CompletedOn', '').strftime('%d/%m/%Y %H:%M:%S') if job_run.get('CompletedOn') else 'N/A',
                'ExecutionTime': job_run.get('ExecutionTime', 0),
                'Arguments': job_run.get('Arguments', {}),
                'ErrorMessage': job_run.get('ErrorMessage', 'N/A'),
                'PredecessorRuns': job_run.get('PredecessorRuns', []),
                'AllocatedCapacity': job_run.get('AllocatedCapacity', 0),
                'MaxCapacity': job_run.get('MaxCapacity', 0),
                'WorkerType': job_run.get('WorkerType', 'Standard'),
                'NumberOfWorkers': job_run.get('NumberOfWorkers', 0),
                'SecurityConfiguration': job_run.get('SecurityConfiguration', 'N/A'),
                'LogGroupName': job_run.get('LogGroupName', 'N/A'),
                'NotificationProperty': job_run.get('NotificationProperty', {}),
                'GlueVersion': job_run.get('GlueVersion', '1.0'),
                'DPUSeconds': job_run.get('DPUSeconds', 0)
            }

            return {"success": True, "data": details}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def list_crawlers(self) -> Dict[str, Any]:
        try:
            glue = self._get_client()
            response = glue.get_crawlers()

            crawlers = []
            for crawler in response['Crawlers']:
                crawlers.append({
                    'Name': crawler['Name'],
                    'Role': crawler['Role'],
                    'DatabaseName': crawler.get('DatabaseName', 'N/A'),
                    'Description': crawler.get('Description', 'N/A'),
                    'State': crawler.get('State', 'READY'),
                    'CreationTime': crawler.get('CreationTime', '').strftime('%d/%m/%Y %H:%M:%S') if crawler.get('CreationTime') else 'N/A',
                    'LastUpdated': crawler.get('LastUpdated', '').strftime('%d/%m/%Y %H:%M:%S') if crawler.get('LastUpdated') else 'N/A',
                    'LastCrawl': crawler.get('LastCrawl', {}),
                    'Version': crawler.get('Version', 1),
                    'Configuration': crawler.get('Configuration', 'N/A'),
                    'CrawlerSecurityConfiguration': crawler.get('CrawlerSecurityConfiguration', 'N/A')
                })

            return {"success": True, "data": crawlers}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def start_crawler(self, crawler_name: str) -> Dict[str, Any]:
        try:
            glue = self._get_client()
            glue.start_crawler(Name=crawler_name)

            return {
                "success": True,
                "message": f"Crawler '{crawler_name}' iniciado com sucesso"
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def stop_crawler(self, crawler_name: str) -> Dict[str, Any]:
        try:
            glue = self._get_client()
            glue.stop_crawler(Name=crawler_name)

            return {
                "success": True,
                "message": f"Crawler '{crawler_name}' parado com sucesso"
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def get_job_statistics(self) -> Dict[str, Any]:
        try:
            jobs_result = self.list_jobs()
            if not jobs_result.get("success"):
                return jobs_result

            jobs = jobs_result.get("data", [])
            stats = {
                'total_jobs': len(jobs),
                'job_runs_stats': {
                    'SUCCEEDED': 0,
                    'FAILED': 0,
                    'STOPPED': 0,
                    'RUNNING': 0,
                    'STARTING': 0,
                    'STOPPING': 0,
                    'TIMEOUT': 0
                },
                'recent_runs': []
            }

            # Coletar estatísticas dos últimos runs de cada job
            for job in jobs[:10]:  # Limitar para performance
                runs_result = self.list_job_runs(job['Name'], max_results=10)
                if runs_result.get("success"):
                    runs = runs_result.get("data", [])
                    for run in runs:
                        state = run['JobRunState']
                        if state in stats['job_runs_stats']:
                            stats['job_runs_stats'][state] += 1

                        # Adicionar aos runs recentes se for dos últimos 5
                        if len(stats['recent_runs']) < 20:
                            stats['recent_runs'].append({
                                'JobName': run['JobName'],
                                'Id': run['Id'],
                                'State': run['JobRunState'],
                                'StartedOn': run['StartedOn'],
                                'Duration': run.get('Duration', 'N/A')
                            })

            # Ordenar runs recentes por data
            stats['recent_runs'].sort(key=lambda x: x['StartedOn'], reverse=True)
            stats['recent_runs'] = stats['recent_runs'][:20]  # Top 20

            return {"success": True, "data": stats}
        except Exception as e:
            return {"success": False, "error": str(e)}