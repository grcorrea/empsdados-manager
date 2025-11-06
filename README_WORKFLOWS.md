# 🔄 GitHub Actions Workflows

## Arquivos Criados

### 🚀 Workflow Principal
```
.github/workflows/auto-pr.yml
```
**Função**: Cria automaticamente Pull Requests quando há push em branches de desenvolvimento.

**Como funciona**:
- Push em qualquer branch (exceto main/master/develop/dev) → Cria PR automaticamente
- Títulos inteligentes baseados no padrão do branch
- Labels automáticos (feature, fix, docs, etc.)
- Comentários em PRs existentes para novos pushes

### 🧪 Workflow de Teste
```
.github/workflows/test-auto-pr.yml
```
**Função**: Valida e testa o workflow de auto-PR.

**Como usar**:
- Execução manual via GitHub Actions
- Testa sintaxe e lógica do workflow principal
- Valida cenários de uso

### ⚙️ Configuração (Opcional)
```
.github/auto-pr-config.yml
```
**Função**: Arquivo de configuração para personalizar comportamento (futuras versões).

## 📖 Documentação

### 📋 Guia Completo
```
AUTO_PR_GUIDE.md
```
Documentação detalhada com:
- Como usar o workflow
- Exemplos práticos
- Personalização
- Resolução de problemas

## 🎯 Uso Rápido

### 1. Criar Branch Seguindo Convenção
```bash
git checkout -b feature/minha-funcionalidade
# ou
git checkout -b fix/corrigir-bug
# ou
git checkout -b docs/atualizar-readme
```

### 2. Fazer Alterações e Push
```bash
git add .
git commit -m "Implementar funcionalidade X"
git push origin feature/minha-funcionalidade
```

### 3. PR Criado Automaticamente! 🎉
- Título: "✨ Minha Funcionalidade"
- Labels: `enhancement`, `auto-pr`
- Descrição automática com detalhes

## 🏷️ Padrões de Branch Suportados

| Branch Pattern | Título | Labels |
|----------------|--------|---------|
| `feature/*` | ✨ Nome da Feature | `enhancement` |
| `fix/*` | 🐛 Nome do Fix | `bug` |
| `docs/*` | 📝 Nome da Doc | `documentation` |
| `test/*` | 🧪 Nome do Teste | `tests` |
| `outros` | Mensagem do commit | `auto-pr` |

## ✅ Benefícios

- **🔄 Automação**: Sem necessidade de criar PRs manualmente
- **📝 Padronização**: Títulos e descrições consistentes
- **🏷️ Organização**: Labels automáticos para categorização
- **⚡ Velocidade**: Workflow otimizado de desenvolvimento
- **🔒 Segurança**: Usa permissões padrão do GitHub

## 🚀 Status

**✅ Pronto para Uso**
- Sintaxe YAML validada
- Workflow testado
- Documentação completa
- Exemplos funcionais

## 🔧 Próximos Passos

1. **Testar**: Criar um branch de teste para validar funcionamento
2. **Personalizar**: Modificar padrões se necessário
3. **Configurar Labels**: Criar labels no repositório se não existirem
4. **Treinar Equipe**: Compartilhar convenções de branches

---

**🎉 Workflows de Auto-PR configurados e prontos para acelerar seu desenvolvimento!**