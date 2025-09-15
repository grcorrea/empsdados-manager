import boto3
import json
from typing import Dict, Any, List
from botocore.exceptions import ClientError, NoCredentialsError


class StepFunctionsService:
    def __init__(self):
        self.session = boto3.Session()

    def _get_client(self):
        try:
            return self.session.client('stepfunctions')
        except NoCredentialsError:
            raise Exception("Credenciais AWS não encontradas. Faça login no AWS SSO primeiro.")

    def list_state_machines(self) -> Dict[str, Any]:
        try:
            sf = self._get_client()
            response = sf.list_state_machines()

            machines = []
            for machine in response['stateMachines']:
                machines.append({
                    'name': machine['name'],
                    'stateMachineArn': machine['stateMachineArn'],
                    'type': machine['type'],
                    'creationDate': machine['creationDate'].strftime('%d/%m/%Y %H:%M:%S')
                })

            return {"success": True, "data": machines}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def describe_state_machine(self, state_machine_arn: str) -> Dict[str, Any]:
        try:
            sf = self._get_client()
            response = sf.describe_state_machine(stateMachineArn=state_machine_arn)

            machine_info = {
                'name': response['name'],
                'stateMachineArn': response['stateMachineArn'],
                'definition': response['definition'],
                'roleArn': response['roleArn'],
                'type': response['type'],
                'creationDate': response['creationDate'].strftime('%d/%m/%Y %H:%M:%S'),
                'status': response.get('status', 'N/A'),
                'description': response.get('description', 'N/A')
            }

            return {"success": True, "data": machine_info}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def list_executions(self, state_machine_arn: str, status_filter: str = None) -> Dict[str, Any]:
        try:
            sf = self._get_client()

            kwargs = {'stateMachineArn': state_machine_arn, 'maxResults': 100}
            if status_filter:
                kwargs['statusFilter'] = status_filter

            response = sf.list_executions(**kwargs)

            executions = []
            for execution in response['executions']:
                exec_info = {
                    'name': execution['name'],
                    'executionArn': execution['executionArn'],
                    'status': execution['status'],
                    'startDate': execution['startDate'].strftime('%d/%m/%Y %H:%M:%S')
                }

                if 'stopDate' in execution:
                    exec_info['stopDate'] = execution['stopDate'].strftime('%d/%m/%Y %H:%M:%S')
                else:
                    exec_info['stopDate'] = 'Em execução'

                executions.append(exec_info)

            return {"success": True, "data": executions}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def start_execution(self, state_machine_arn: str, execution_name: str = None, input_data: str = "{}") -> Dict[str, Any]:
        try:
            sf = self._get_client()

            kwargs = {
                'stateMachineArn': state_machine_arn,
                'input': input_data
            }

            if execution_name:
                kwargs['name'] = execution_name

            response = sf.start_execution(**kwargs)

            return {
                "success": True,
                "message": f"Execução iniciada com sucesso",
                "data": {
                    'executionArn': response['executionArn'],
                    'startDate': response['startDate'].strftime('%d/%m/%Y %H:%M:%S')
                }
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def stop_execution(self, execution_arn: str, error: str = "User requested stop", cause: str = "Stopped by user") -> Dict[str, Any]:
        try:
            sf = self._get_client()

            response = sf.stop_execution(
                executionArn=execution_arn,
                error=error,
                cause=cause
            )

            return {
                "success": True,
                "message": f"Execução parada com sucesso",
                "data": {
                    'stopDate': response['stopDate'].strftime('%d/%m/%Y %H:%M:%S')
                }
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def describe_execution(self, execution_arn: str) -> Dict[str, Any]:
        try:
            sf = self._get_client()
            response = sf.describe_execution(executionArn=execution_arn)

            execution_info = {
                'name': response['name'],
                'executionArn': response['executionArn'],
                'stateMachineArn': response['stateMachineArn'],
                'status': response['status'],
                'startDate': response['startDate'].strftime('%d/%m/%Y %H:%M:%S'),
                'input': response.get('input', '{}'),
                'output': response.get('output', 'N/A')
            }

            if 'stopDate' in response:
                execution_info['stopDate'] = response['stopDate'].strftime('%d/%m/%Y %H:%M:%S')
            else:
                execution_info['stopDate'] = 'Em execução'

            if 'error' in response:
                execution_info['error'] = response['error']
            if 'cause' in response:
                execution_info['cause'] = response['cause']

            return {"success": True, "data": execution_info}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def get_execution_history(self, execution_arn: str) -> Dict[str, Any]:
        try:
            sf = self._get_client()
            response = sf.get_execution_history(
                executionArn=execution_arn,
                maxResults=100,
                reverseOrder=True
            )

            events = []
            for event in response['events']:
                event_info = {
                    'timestamp': event['timestamp'].strftime('%d/%m/%Y %H:%M:%S'),
                    'type': event['type'],
                    'id': event['id']
                }

                # Adicionar detalhes específicos do tipo de evento
                for key in ['stateEnteredEventDetails', 'stateExitedEventDetails', 'taskStateEnteredEventDetails',
                           'taskStateExitedEventDetails', 'executionStartedEventDetails', 'executionSucceededEventDetails',
                           'executionFailedEventDetails']:
                    if key in event:
                        event_info['details'] = event[key]
                        break

                events.append(event_info)

            return {"success": True, "data": events}
        except ClientError as e:
            return {"success": False, "error": str(e)}