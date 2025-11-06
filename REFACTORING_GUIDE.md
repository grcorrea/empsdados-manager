# Guia de Refatoração - AWS EmpsDados Manager

## Visão Geral

Este projeto foi refatorado para separar o código monolítico em módulos especializados, melhorando a manutenibilidade, testabilidade e organização do código.

## Estrutura Anterior vs Nova

### Antes
```
├── main.py (268KB - tudo em um arquivo)
├── build.py
└── setup.py
```

### Depois
```
├── main.py (original mantido)
├── main_refactored.py (versão refatorada)
├── services/           # Serviços AWS
│   ├── __init__.py
│   ├── aws_auth.py     # Autenticação AWS SSO
│   ├── s3_service.py   # Operações S3
│   ├── glue_service.py # Jobs Glue
│   ├── stepfunctions_service.py # Step Functions
│   ├── eventbridge_service.py   # EventBridge Rules
│   └── athena_service.py        # Athena/Tables
├── ui/                 # Componentes de Interface
│   ├── __init__.py
│   └── components.py   # Componentes UI reutilizáveis
└── utils/              # Utilitários
    ├── __init__.py
    ├── config_manager.py  # Gerenciamento de configurações
    ├── cache_manager.py   # Sistema de cache
    └── helpers.py         # Funções auxiliares
```

## Módulos Criados

### 1. Utils (Utilitários)

#### `utils/config_manager.py`
- Gerenciamento centralizado de configurações
- Arquivo INI para persistência
- Métodos para get/set de configurações
- Suporte a filtros salvos

#### `utils/cache_manager.py`
- Sistema de cache inteligente
- Cache por perfil AWS
- Verificação de validade por timestamp
- Limpeza automática de cache expirado

#### `utils/helpers.py`
- Funções auxiliares do sistema
- Manipulação de janelas (Windows)
- Formatação de dados (data, tamanho, duração)
- Utilitários de arquivo e pasta

### 2. Services (Serviços AWS)

#### `services/aws_auth.py`
- Autenticação AWS SSO
- Gerenciamento de perfis
- Login/logout assíncrono
- Callbacks para mudanças de estado

#### `services/s3_service.py`
- Sincronização S3
- Operações de upload/download
- Validação de caminhos S3
- Listagem de objetos

#### `services/glue_service.py`
- Busca paralela de jobs Glue
- Cache inteligente
- Filtragem por squad/RT
- Controle de execuções

#### `services/stepfunctions_service.py`
- Busca de Step Functions
- Controle de execuções
- Histórico de execuções
- Retry com backoff

#### `services/eventbridge_service.py`
- Gerenciamento de regras
- Ativação/desativação
- Busca de targets
- Filtragem avançada

#### `services/athena_service.py`
- Busca de tabelas do Data Catalog
- Metadados de tabelas
- Workgroups Athena
- Simulação de custos

### 3. UI (Interface)

#### `ui/components.py`
- Componentes UI reutilizáveis
- Formatação padronizada
- Exportação para Excel
- Cópia para clipboard
- Criação de tabelas, botões, KPIs

### 4. Main Refatorado

#### `main_refactored.py`
- Versão simplificada e modular
- Coordenação entre serviços
- Interface baseada em sidebar
- Navegação entre seções
- Inicialização dos serviços

## Principais Melhorias

### 1. **Separação de Responsabilidades**
- Cada módulo tem uma responsabilidade específica
- Serviços AWS isolados
- UI separada da lógica de negócio

### 2. **Reutilização de Código**
- Componentes UI padronizados
- Funções auxiliares centralizadas
- Cache compartilhado entre serviços

### 3. **Manutenibilidade**
- Arquivos menores e focados
- Imports organizados
- Documentação por módulo

### 4. **Testabilidade**
- Cada serviço pode ser testado isoladamente
- Mocks facilitados pela separação
- Dependências injetadas

### 5. **Performance**
- Cache inteligente por perfil
- Busca paralela otimizada
- Lazy loading de componentes

## Como Usar a Versão Refatorada

### 1. Executar a Nova Versão
```bash
python main_refactored.py
```

### 2. Estrutura da Interface
- **Sidebar**: Navegação entre seções
- **Área Principal**: Conteúdo da seção selecionada
- **Seções Disponíveis**:
  - Login AWS
  - Sincronização S3
  - Monitoring (Glue, Step Functions, Tables, EventBridge)
  - Relatórios (Athena, Glue, Simulador)

### 3. Funcionalidades Principais
- Login/logout AWS SSO
- Cache automático por perfil
- Busca paralela otimizada
- Exportação para Excel
- Filtragem avançada

## Migração do Código Original

### Funcionalidades Implementadas
✅ Estrutura modular completa
✅ Autenticação AWS
✅ Serviços AWS (Glue, S3, Step Functions, EventBridge, Athena)
✅ Sistema de cache
✅ Componentes UI base
✅ Interface simplificada

### Funcionalidades a Implementar
🔄 Migração completa das UIs específicas
🔄 Auto-refresh
🔄 Todos os filtros e KPIs
🔄 Simulador de custos completo
🔄 Todas as exportações

## Vantagens da Refatoração

### Para Desenvolvimento
- **Manutenção**: Código organizado em módulos pequenos
- **Debug**: Erros isolados por responsabilidade
- **Features**: Adicionar novas funcionalidades é mais fácil
- **Testes**: Cada módulo pode ser testado independentemente

### Para Performance
- **Cache**: Sistema inteligente reduz chamadas AWS
- **Paralelo**: Busca otimizada com threading
- **Lazy Loading**: Componentes carregados sob demanda

### Para Usuário
- **Interface**: Navegação mais clara com sidebar
- **Responsividade**: Operações assíncronas
- **Configuração**: Persistência de preferências

## Próximos Passos

1. **Testar** a versão refatorada
2. **Migrar** funcionalidades específicas restantes
3. **Implementar** testes unitários
4. **Otimizar** performance
5. **Documentar** APIs dos serviços

## Considerações

- O arquivo `main.py` original foi mantido para comparação
- A versão refatorada pode ser executada lado a lado
- Cache é compatível entre versões
- Configurações são compartilhadas

Este guia serve como documentação para entender e continuar o desenvolvimento da versão refatorada.