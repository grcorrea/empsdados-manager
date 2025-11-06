import boto3
import time
import random
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError


class AthenaService:
    def __init__(self, auth_service, cache_manager):
        self.auth_service = auth_service
        self.cache_manager = cache_manager

    def get_athena_client(self):
        """Retorna cliente Athena usando a sessão atual"""
        if not self.auth_service.is_authenticated():
            raise Exception("Usuário não autenticado")

        session = self.auth_service.get_current_session()
        return session.client('athena')

    def get_glue_client(self):
        """Retorna cliente Glue para acessar Data Catalog"""
        if not self.auth_service.is_authenticated():
            raise Exception("Usuário não autenticado")

        session = self.auth_service.get_current_session()
        return session.client('glue')

    def get_s3_client(self):
        """Retorna cliente S3 para verificar dados das tabelas"""
        if not self.auth_service.is_authenticated():
            raise Exception("Usuário não autenticado")

        session = self.auth_service.get_current_session()
        return session.client('s3')

    def fetch_athena_workgroups(self):
        """Busca workgroups do Athena"""
        try:
            athena_client = self.get_athena_client()

            def get_workgroups():
                workgroups = []
                next_token = None

                while True:
                    try:
                        if next_token:
                            response = athena_client.list_work_groups(NextToken=next_token)
                        else:
                            response = athena_client.list_work_groups()

                        for wg in response.get('WorkGroups', []):
                            workgroups.append({
                                'name': wg.get('Name', ''),
                                'state': wg.get('State', ''),
                                'description': wg.get('Description', ''),
                                'creation_time': wg.get('CreationTime')
                            })

                        next_token = response.get('NextToken')
                        if not next_token:
                            break

                    except Exception as e:
                        print(f" Erro ao listar workgroups: {e}")
                        break

                return workgroups

            workgroups = get_workgroups()
            print(f" {len(workgroups)} workgroups Athena encontrados")
            return workgroups

        except Exception as e:
            print(f" Erro ao buscar workgroups Athena: {e}")
            return []

    def fetch_athena_costs(self, period, workgroup, start_date, end_date):
        """Busca custos do Athena (simulado - AWS não fornece API direta)"""
        try:
            print(f" Gerando dados de custos Athena para {workgroup} ({period})")

            def get_cost_data():
                # Como AWS não fornece API direta para custos Athena por workgroup,
                # vamos simular dados baseados em padrões reais

                # Buscar queries executadas no período (limitado)
                athena_client = self.get_athena_client()

                try:
                    response = athena_client.list_query_executions(
                        WorkGroup=workgroup,
                        MaxResults=50
                    )

                    query_executions = response.get('QueryExecutionIds', [])
                    total_queries = len(query_executions)

                    # Simular dados baseados no número de queries
                    base_cost_per_query = random.uniform(0.005, 0.050)  # $0.005 a $0.050 por query
                    estimated_total_cost = total_queries * base_cost_per_query

                except Exception as e:
                    print(f" Erro ao buscar execuções, usando dados simulados: {e}")
                    total_queries = random.randint(10, 100)
                    estimated_total_cost = random.uniform(5.0, 50.0)

                # Gerar dados diários no período
                cost_data = []
                current_date = start_date

                while current_date <= end_date:
                    daily_queries = random.randint(1, max(1, total_queries // 30))
                    daily_cost = daily_queries * random.uniform(0.005, 0.020)

                    cost_data.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'queries_count': daily_queries,
                        'data_scanned_tb': round(random.uniform(0.1, 5.0), 2),
                        'cost_usd': round(daily_cost, 4),
                        'workgroup': workgroup
                    })

                    current_date += timedelta(days=1)

                return {
                    'period': period,
                    'workgroup': workgroup,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'total_cost': round(sum(item['cost_usd'] for item in cost_data), 2),
                    'total_queries': sum(item['queries_count'] for item in cost_data),
                    'total_data_scanned_tb': round(sum(item['data_scanned_tb'] for item in cost_data), 2),
                    'daily_data': cost_data
                }

            cost_data = get_cost_data()
            print(f" Dados de custos gerados: ${cost_data['total_cost']} ({cost_data['total_queries']} queries)")

            return cost_data

        except Exception as e:
            print(f" Erro ao buscar custos Athena: {e}")
            return self._generate_sample_athena_data(period, workgroup, start_date, end_date)

    def _generate_sample_athena_data(self, period, workgroup, start_date, end_date):
        """Gera dados de amostra para demonstração"""
        print(" Gerando dados de amostra para Athena...")

        cost_data = []
        current_date = start_date

        while current_date <= end_date:
            daily_queries = random.randint(5, 25)
            daily_cost = daily_queries * random.uniform(0.01, 0.05)

            cost_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'queries_count': daily_queries,
                'data_scanned_tb': round(random.uniform(0.5, 3.0), 2),
                'cost_usd': round(daily_cost, 4),
                'workgroup': workgroup
            })

            current_date += timedelta(days=1)

        return {
            'period': period,
            'workgroup': workgroup,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'total_cost': round(sum(item['cost_usd'] for item in cost_data), 2),
            'total_queries': sum(item['queries_count'] for item in cost_data),
            'total_data_scanned_tb': round(sum(item['data_scanned_tb'] for item in cost_data), 2),
            'daily_data': cost_data
        }

    def fetch_all_tables(self, databases=["itau", "teste"], max_workers=3, use_cache=True):
        """Busca todas as tabelas dos databases especificados"""
        try:
            profile = self.auth_service.current_profile
            if not profile:
                return []

            # Verificar cache primeiro
            if use_cache:
                cached_data = self.cache_manager.load_cache('athena_tables', profile)
                if cached_data:
                    print(f" Tabelas carregadas do cache ({len(cached_data)} tabelas)")
                    return cached_data

            glue_client = self.get_glue_client()
            all_tables = []

            print(f" Buscando tabelas nos databases: {databases}")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_db = {}

                for database in databases:
                    def list_tables_in_db():
                        """Lista tabelas em um database específico"""
                        try:
                            print(f" Listando tabelas no database: {database}")
                            tables = []

                            paginator = glue_client.get_paginator('get_tables')
                            for page in paginator.paginate(DatabaseName=database):
                                for table in page['TableList']:
                                    # Buscar metadados adicionais
                                    table_data = self._fetch_table_metadata(database, table['Name'])
                                    if table_data:
                                        tables.append(table_data)

                            print(f" {len(tables)} tabelas encontradas em {database}")
                            return tables

                        except Exception as e:
                            print(f" Erro ao listar tabelas em {database}: {e}")
                            return []

                    future = executor.submit(list_tables_in_db)
                    future_to_db[future] = database

                # Coletar resultados
                for future in as_completed(future_to_db):
                    database = future_to_db[future]
                    try:
                        tables = future.result()
                        all_tables.extend(tables)
                    except Exception as e:
                        print(f" Erro ao processar database {database}: {e}")

            print(f" Total de {len(all_tables)} tabelas carregadas")

            # Salvar no cache
            if all_tables:
                self.cache_manager.save_cache('athena_tables', profile, all_tables)

            return all_tables

        except Exception as e:
            print(f" Erro ao buscar tabelas: {e}")
            return []

    def _fetch_table_metadata(self, database, table_name):
        """Busca metadados de uma tabela específica"""
        try:
            glue_client = self.get_glue_client()

            def get_table_details():
                try:
                    response = glue_client.get_table(
                        DatabaseName=database,
                        Name=table_name
                    )
                    table = response['Table']

                    # Dados básicos da tabela
                    table_data = {
                        'database': database,
                        'name': table_name,
                        'owner': table.get('Owner', 'N/A'),
                        'create_time': table.get('CreateTime'),
                        'update_time': table.get('UpdateTime'),
                        'last_access_time': table.get('LastAccessTime'),
                        'last_analyzed_time': table.get('LastAnalyzedTime'),
                        'storage_descriptor': table.get('StorageDescriptor', {}),
                        'partition_keys': table.get('PartitionKeys', []),
                        'table_type': table.get('TableType', 'N/A'),
                        'parameters': table.get('Parameters', {}),
                        'description': table.get('Description', ''),
                        'columns': [],
                        'location': '',
                        'input_format': '',
                        'output_format': '',
                        'serde_info': {},
                        'compressed': False,
                        'num_buckets': 0,
                        'bucket_columns': [],
                        'sort_columns': [],
                        'stored_as_sub_directories': False
                    }

                    # Extrair informações do StorageDescriptor
                    sd = table.get('StorageDescriptor', {})
                    if sd:
                        table_data['location'] = sd.get('Location', '')
                        table_data['input_format'] = sd.get('InputFormat', '')
                        table_data['output_format'] = sd.get('OutputFormat', '')
                        table_data['compressed'] = sd.get('Compressed', False)
                        table_data['num_buckets'] = sd.get('NumberOfBuckets', 0)
                        table_data['bucket_columns'] = sd.get('BucketColumns', [])
                        table_data['sort_columns'] = sd.get('SortColumns', [])
                        table_data['stored_as_sub_directories'] = sd.get('StoredAsSubDirectories', False)
                        table_data['serde_info'] = sd.get('SerdeInfo', {})
                        table_data['columns'] = sd.get('Columns', [])

                    # Buscar última modificação no S3 se houver localização
                    if table_data['location']:
                        last_modified = self._get_latest_file_modification_date(table_data['location'])
                        table_data['s3_last_modified'] = last_modified

                    # Estatísticas da tabela (se disponível)
                    if 'numFiles' in table_data['parameters']:
                        table_data['num_files'] = table_data['parameters']['numFiles']
                    if 'totalSize' in table_data['parameters']:
                        table_data['total_size'] = table_data['parameters']['totalSize']

                    return table_data

                except Exception as e:
                    print(f" Erro ao buscar metadados da tabela {database}.{table_name}: {e}")
                    return None

            return get_table_details()

        except Exception as e:
            print(f" Erro ao buscar metadados: {e}")
            return None

    def _get_latest_file_modification_date(self, s3_location):
        """Obtém a data de modificação mais recente dos arquivos no S3"""
        try:
            if not s3_location.startswith('s3://'):
                return None

            s3_client = self.get_s3_client()

            def list_s3_objects():
                try:
                    # Parse do S3 path
                    path_parts = s3_location[5:].split('/', 1)
                    bucket = path_parts[0]
                    prefix = path_parts[1] if len(path_parts) > 1 else ""

                    # Listar objetos mais recentes
                    response = s3_client.list_objects_v2(
                        Bucket=bucket,
                        Prefix=prefix,
                        MaxKeys=1000
                    )

                    objects = response.get('Contents', [])
                    if not objects:
                        return None

                    # Encontrar o arquivo mais recente
                    latest_object = max(objects, key=lambda x: x.get('LastModified', datetime.min.replace(tzinfo=timezone.utc)))
                    return latest_object.get('LastModified')

                except Exception as e:
                    print(f" Erro ao verificar arquivos S3: {e}")
                    return None

            return list_s3_objects()

        except Exception as e:
            print(f" Erro ao obter modificação S3: {e}")
            return None

    def filter_tables(self, tables, filter_text="", database_filter=""):
        """Filtra tabelas baseado nos critérios fornecidos"""
        if not tables:
            return []

        filtered_tables = tables

        # Filtro por texto
        if filter_text:
            filter_text = filter_text.lower()
            filtered_tables = [
                table for table in filtered_tables
                if filter_text in table.get('name', '').lower() or
                   filter_text in table.get('database', '').lower() or
                   filter_text in table.get('description', '').lower() or
                   filter_text in table.get('location', '').lower()
            ]

        # Filtro por database
        if database_filter and database_filter != "Todos":
            filtered_tables = [
                table for table in filtered_tables
                if table.get('database', '') == database_filter
            ]

        return filtered_tables