import boto3
import json
from typing import Dict, Any, List
from botocore.exceptions import ClientError, NoCredentialsError


class EventBridgeService:
    def __init__(self):
        self.session = boto3.Session()

    def _get_client(self):
        try:
            return self.session.client('events')
        except NoCredentialsError:
            raise Exception("Credenciais AWS não encontradas. Faça login no AWS SSO primeiro.")

    def list_event_buses(self) -> Dict[str, Any]:
        try:
            events = self._get_client()
            response = events.list_event_buses()

            buses = []
            for bus in response['EventBuses']:
                buses.append({
                    'Name': bus['Name'],
                    'Arn': bus['Arn'],
                    'Policy': bus.get('Policy', 'N/A'),
                    'CreationTime': bus.get('CreationTime', '').strftime('%d/%m/%Y %H:%M:%S') if bus.get('CreationTime') else 'N/A'
                })

            return {"success": True, "data": buses}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def list_rules(self, event_bus_name: str = "default") -> Dict[str, Any]:
        try:
            events = self._get_client()
            response = events.list_rules(EventBusName=event_bus_name)

            rules = []
            for rule in response['Rules']:
                rules.append({
                    'Name': rule['Name'],
                    'State': rule['State'],
                    'EventPattern': rule.get('EventPattern', 'N/A'),
                    'ScheduleExpression': rule.get('ScheduleExpression', 'N/A'),
                    'Description': rule.get('Description', 'N/A'),
                    'Arn': rule['Arn']
                })

            return {"success": True, "data": rules}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def list_targets(self, rule_name: str, event_bus_name: str = "default") -> Dict[str, Any]:
        try:
            events = self._get_client()
            response = events.list_targets_by_rule(
                Rule=rule_name,
                EventBusName=event_bus_name
            )

            targets = []
            for target in response['Targets']:
                targets.append({
                    'Id': target['Id'],
                    'Arn': target['Arn'],
                    'RoleArn': target.get('RoleArn', 'N/A'),
                    'Input': target.get('Input', 'N/A'),
                    'InputPath': target.get('InputPath', 'N/A')
                })

            return {"success": True, "data": targets}
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def enable_rule(self, rule_name: str, event_bus_name: str = "default") -> Dict[str, Any]:
        try:
            events = self._get_client()
            events.enable_rule(Name=rule_name, EventBusName=event_bus_name)

            return {
                "success": True,
                "message": f"Regra '{rule_name}' habilitada com sucesso"
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def disable_rule(self, rule_name: str, event_bus_name: str = "default") -> Dict[str, Any]:
        try:
            events = self._get_client()
            events.disable_rule(Name=rule_name, EventBusName=event_bus_name)

            return {
                "success": True,
                "message": f"Regra '{rule_name}' desabilitada com sucesso"
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}

    def put_events(self, source: str, detail_type: str, detail: Dict[str, Any], event_bus_name: str = "default") -> Dict[str, Any]:
        try:
            events = self._get_client()

            response = events.put_events(
                Entries=[
                    {
                        'Source': source,
                        'DetailType': detail_type,
                        'Detail': json.dumps(detail),
                        'EventBusName': event_bus_name
                    }
                ]
            )

            if response['FailedEntryCount'] == 0:
                return {
                    "success": True,
                    "message": f"Evento enviado com sucesso para {event_bus_name}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Falha ao enviar evento: {response['Entries'][0].get('ErrorMessage', 'Erro desconhecido')}"
                }

        except ClientError as e:
            return {"success": False, "error": str(e)}

    def describe_rule(self, rule_name: str, event_bus_name: str = "default") -> Dict[str, Any]:
        try:
            events = self._get_client()
            response = events.describe_rule(Name=rule_name, EventBusName=event_bus_name)

            rule_info = {
                'Name': response['Name'],
                'Arn': response['Arn'],
                'EventPattern': response.get('EventPattern', 'N/A'),
                'ScheduleExpression': response.get('ScheduleExpression', 'N/A'),
                'State': response['State'],
                'Description': response.get('Description', 'N/A'),
                'RoleArn': response.get('RoleArn', 'N/A'),
                'ManagedBy': response.get('ManagedBy', 'N/A'),
                'EventBusName': response.get('EventBusName', 'default')
            }

            return {"success": True, "data": rule_info}
        except ClientError as e:
            return {"success": False, "error": str(e)}