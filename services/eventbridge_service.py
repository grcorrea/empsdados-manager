import boto3
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError


class EventBridgeService:
    def __init__(self, auth_service, cache_manager):
        self.auth_service = auth_service
        self.cache_manager = cache_manager

    def get_eventbridge_client(self):
        """Retorna cliente EventBridge usando a sessão atual"""
        if not self.auth_service.is_authenticated():
            raise Exception("Usuário não autenticado")

        session = self.auth_service.get_current_session()
        return session.client('events')

    def fetch_eventbridge_rules(self, use_cache=True):
        """Busca regras do EventBridge"""
        try:
            profile = self.auth_service.current_profile
            if not profile:
                return []

            # Verificar cache primeiro
            if use_cache:
                cached_data = self.cache_manager.load_cache('eventbridge_rules', profile)
                if cached_data:
                    print(f" Regras EventBridge carregadas do cache ({len(cached_data)} regras)")
                    return cached_data

            events_client = self.get_eventbridge_client()

            def get_eventbridge_rules():
                """Busca todas as regras do EventBridge"""
                all_rules = []

                try:
                    # Listar regras padrão
                    paginator = events_client.get_paginator('list_rules')

                    for page in paginator.paginate():
                        rules = page.get('Rules', [])

                        # Buscar detalhes de cada regra em paralelo
                        with ThreadPoolExecutor(max_workers=10) as executor:
                            future_to_rule = {
                                executor.submit(self._fetch_single_rule_details, rule): rule
                                for rule in rules
                            }

                            for future in as_completed(future_to_rule):
                                try:
                                    rule_data = future.result()
                                    all_rules.append(rule_data)
                                except Exception as e:
                                    rule = future_to_rule[future]
                                    print(f" Erro ao buscar detalhes da regra {rule.get('Name', 'unknown')}: {e}")
                                    # Adicionar regra com dados básicos mesmo com erro
                                    all_rules.append({
                                        'name': rule.get('Name', 'N/A'),
                                        'arn': rule.get('Arn', 'N/A'),
                                        'state': rule.get('State', 'N/A'),
                                        'description': rule.get('Description', ''),
                                        'schedule_expression': rule.get('ScheduleExpression', ''),
                                        'event_pattern': rule.get('EventPattern', ''),
                                        'targets': [],
                                        'targets_count': 0,
                                        'error': str(e)
                                    })

                    print(f" {len(all_rules)} regras EventBridge carregadas")
                    return all_rules

                except Exception as e:
                    print(f" Erro ao buscar regras EventBridge: {e}")
                    return []

            rules = get_eventbridge_rules()

            # Salvar no cache
            if rules:
                self.cache_manager.save_cache('eventbridge_rules', profile, rules)

            return rules

        except Exception as e:
            print(f" Erro ao buscar regras EventBridge: {e}")
            return []

    def _fetch_single_rule_details(self, rule):
        """Busca detalhes de uma única regra EventBridge"""
        try:
            events_client = self.get_eventbridge_client()
            rule_name = rule.get('Name', '')

            def get_rule_targets():
                """Busca targets de uma regra"""
                try:
                    response = events_client.list_targets_by_rule(Rule=rule_name)
                    return response.get('Targets', [])
                except Exception as e:
                    print(f" Erro ao buscar targets da regra {rule_name}: {e}")
                    return []

            # Buscar targets da regra
            targets = get_rule_targets()

            rule_data = {
                'name': rule_name,
                'arn': rule.get('Arn', 'N/A'),
                'description': rule.get('Description', ''),
                'state': rule.get('State', 'N/A'),
                'schedule_expression': rule.get('ScheduleExpression', ''),
                'event_pattern': rule.get('EventPattern', ''),
                'event_bus_name': rule.get('EventBusName', 'default'),
                'managed_by': rule.get('ManagedBy', ''),
                'created_by': rule.get('CreatedBy', ''),
                'targets': targets,
                'targets_count': len(targets)
            }

            # Adicionar informações dos targets principais
            if targets:
                target_types = []
                target_arns = []

                for target in targets:
                    target_arn = target.get('Arn', '')
                    target_arns.append(target_arn)

                    # Identificar tipo do target pelo ARN
                    if 'lambda' in target_arn:
                        target_types.append('Lambda')
                    elif 'states' in target_arn:
                        target_types.append('Step Functions')
                    elif 'sqs' in target_arn:
                        target_types.append('SQS')
                    elif 'sns' in target_arn:
                        target_types.append('SNS')
                    elif 'kinesis' in target_arn:
                        target_types.append('Kinesis')
                    elif 'logs' in target_arn:
                        target_types.append('CloudWatch Logs')
                    elif 'events' in target_arn:
                        target_types.append('EventBridge')
                    elif 'ec2' in target_arn:
                        target_types.append('EC2')
                    else:
                        target_types.append('Outro')

                rule_data['target_types'] = list(set(target_types))
                rule_data['target_arns'] = target_arns

            # Status summary
            state = rule.get('State', 'N/A')
            if state == 'ENABLED':
                rule_data['status_summary'] = ' Ativada'
            elif state == 'DISABLED':
                rule_data['status_summary'] = ' Desativada'
            else:
                rule_data['status_summary'] = f' {state}'

            # Tipo de regra
            if rule.get('ScheduleExpression'):
                rule_data['rule_type'] = ' Agendada'
            elif rule.get('EventPattern'):
                rule_data['rule_type'] = ' Evento'
            else:
                rule_data['rule_type'] = ' Outro'

            return rule_data

        except Exception as e:
            print(f" Erro ao buscar detalhes da regra {rule.get('Name', 'unknown')}: {e}")
            # Retornar dados básicos mesmo com erro
            return {
                'name': rule.get('Name', 'N/A'),
                'arn': rule.get('Arn', 'N/A'),
                'state': rule.get('State', 'N/A'),
                'description': rule.get('Description', ''),
                'schedule_expression': rule.get('ScheduleExpression', ''),
                'event_pattern': rule.get('EventPattern', ''),
                'targets': [],
                'targets_count': 0,
                'status_summary': ' Erro ao carregar',
                'error': str(e)
            }

    def toggle_rule(self, rule_name, current_state):
        """Ativa/desativa uma regra EventBridge"""
        try:
            events_client = self.get_eventbridge_client()

            if current_state == 'ENABLED':
                # Desativar regra
                events_client.disable_rule(Name=rule_name)
                print(f" Regra {rule_name} desativada")
                return 'DISABLED'
            else:
                # Ativar regra
                events_client.enable_rule(Name=rule_name)
                print(f" Regra {rule_name} ativada")
                return 'ENABLED'

        except Exception as e:
            print(f" Erro ao alterar estado da regra {rule_name}: {e}")
            return current_state

    def disable_rule(self, rule_name):
        """Desativa uma regra EventBridge"""
        try:
            events_client = self.get_eventbridge_client()
            events_client.disable_rule(Name=rule_name)
            print(f" Regra {rule_name} desativada")
            return True
        except Exception as e:
            print(f" Erro ao desativar regra {rule_name}: {e}")
            return False

    def enable_rule(self, rule_name):
        """Ativa uma regra EventBridge"""
        try:
            events_client = self.get_eventbridge_client()
            events_client.enable_rule(Name=rule_name)
            print(f" Regra {rule_name} ativada")
            return True
        except Exception as e:
            print(f" Erro ao ativar regra {rule_name}: {e}")
            return False

    def get_rule_details(self, rule_name):
        """Obtém detalhes completos de uma regra específica"""
        try:
            events_client = self.get_eventbridge_client()

            # Obter detalhes da regra
            rule_response = events_client.describe_rule(Name=rule_name)

            # Obter targets da regra
            targets_response = events_client.list_targets_by_rule(Rule=rule_name)
            targets = targets_response.get('Targets', [])

            rule_data = {
                'name': rule_response.get('Name', ''),
                'arn': rule_response.get('Arn', ''),
                'description': rule_response.get('Description', ''),
                'state': rule_response.get('State', ''),
                'schedule_expression': rule_response.get('ScheduleExpression', ''),
                'event_pattern': rule_response.get('EventPattern', ''),
                'event_bus_name': rule_response.get('EventBusName', 'default'),
                'managed_by': rule_response.get('ManagedBy', ''),
                'created_by': rule_response.get('CreatedBy', ''),
                'targets': targets,
                'targets_count': len(targets)
            }

            return rule_data

        except Exception as e:
            print(f" Erro ao obter detalhes da regra {rule_name}: {e}")
            return None

    def filter_rules(self, rules, filter_text="", state_filter="", type_filter=""):
        """Filtra regras EventBridge baseado nos critérios fornecidos"""
        if not rules:
            return []

        filtered_rules = rules

        # Filtro por texto
        if filter_text:
            filter_text = filter_text.lower()
            filtered_rules = [
                rule for rule in filtered_rules
                if filter_text in rule.get('name', '').lower() or
                   filter_text in rule.get('description', '').lower() or
                   filter_text in rule.get('schedule_expression', '').lower()
            ]

        # Filtro por estado
        if state_filter and state_filter != "Todos":
            filtered_rules = [
                rule for rule in filtered_rules
                if rule.get('state', '') == state_filter
            ]

        # Filtro por tipo
        if type_filter and type_filter != "Todos":
            if type_filter == "Agendada":
                filtered_rules = [
                    rule for rule in filtered_rules
                    if rule.get('schedule_expression', '')
                ]
            elif type_filter == "Evento":
                filtered_rules = [
                    rule for rule in filtered_rules
                    if rule.get('event_pattern', '')
                ]

        return filtered_rules