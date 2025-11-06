# 🚀 Guia do Auto Pull Request Workflow

## Visão Geral

Este workflow do GitHub Actions cria automaticamente Pull Requests quando você faz push em branches específicos, facilitando o processo de revisão de código e colaboração em equipe.

## ✨ Funcionalidades

- **🔄 Criação Automática**: PRs criados automaticamente em push
- **🏷️ Labels Inteligentes**: Labels baseados no padrão do nome do branch
- **📝 Títulos Automáticos**: Títulos gerados baseados no tipo de branch
- **💬 Comentários**: Atualiza PRs existentes com comentários em novos pushes
- **🚫 Evita Duplicatas**: Verifica se PR já existe antes de criar
- **🔒 Seguro**: Não executa em merge commits (evita loops)

## 📁 Arquivos Criados

### Workflow Principal
```
.github/workflows/auto-pr.yml
```
Workflow principal que executa a lógica de criação de PRs.

### Arquivos de Configuração (Opcionais)
```
.github/auto-pr-config.yml        # Configurações personalizadas
.github/workflows/test-auto-pr.yml # Workflow de teste
```

## ⚙️ Como Funciona

### 1. Trigger
O workflow é acionado quando há **push** em qualquer branch, **EXCETO**:
- `main`
- `master`
- `develop`
- `dev`

### 2. Verificações
- ✅ Não é um merge commit
- ✅ PR não existe ainda para o branch
- ✅ Branch base é válido (main ou master)

### 3. Ações
- **Se PR não existe**: Cria novo PR
- **Se PR já existe**: Adiciona comentário com info do novo push

## 🏷️ Padrões de Branches e Labels

| Padrão do Branch | Título | Labels |
|------------------|--------|---------|
| `feature/nova-funcionalidade` | ✨ Nova Funcionalidade | `enhancement` |
| `fix/corrigir-bug` | 🐛 Corrigir Bug | `bug` |
| `docs/atualizar-readme` | 📝 Atualizar Readme | `documentation` |
| `test/adicionar-testes` | 🧪 Adicionar Testes | `tests` |
| `refactor/limpar-codigo` | ♻️ Limpar Codigo | `refactoring` |
| `outros-branches` | (usa mensagem do commit) | `auto-pr` |

## 🚀 Como Usar

### 1. Configuração Inicial
O workflow já está configurado e pronto para uso. Não requer configuração adicional.

### 2. Fluxo de Trabalho
```bash
# 1. Criar branch seguindo convenção
git checkout -b feature/minha-nova-funcionalidade

# 2. Fazer alterações e commit
git add .
git commit -m "Implementar nova funcionalidade X"

# 3. Fazer push - PR será criado automaticamente!
git push origin feature/minha-nova-funcionalidade
```

### 3. Resultado
- 🎉 PR criado automaticamente
- 🏷️ Labels apropriados adicionados
- 📝 Título gerado baseado no branch
- 📋 Descrição com informações úteis

## 📋 Exemplos Práticos

### Exemplo 1: Feature Branch
```bash
git checkout -b feature/user-authentication
git commit -m "Add login and registration forms"
git push origin feature/user-authentication
```
**Resultado**: PR criado com título "✨ User Authentication"

### Exemplo 2: Bug Fix
```bash
git checkout -b fix/login-validation-error
git commit -m "Fix email validation in login form"
git push origin fix/login-validation-error
```
**Resultado**: PR criado com título "🐛 Login Validation Error"

### Exemplo 3: Documentation
```bash
git checkout -b docs/api-documentation
git commit -m "Update API endpoints documentation"
git push origin docs/api-documentation
```
**Resultado**: PR criado com título "📝 Api Documentation"

## 🔧 Personalização

### Modificar Branches Ignorados
Edite o arquivo `.github/workflows/auto-pr.yml`:
```yaml
on:
  push:
    branches-ignore:
      - main
      - master
      - develop
      - dev
      - production  # Adicionar aqui
```

### Adicionar Novos Padrões de Branch
Edite a seção "Create PR" no workflow:
```bash
elif echo "$BRANCH" | grep -q "chore/"; then
  TITLE="🔧 $(echo $BRANCH | sed 's/chore\///' | sed 's/-/ /g')"
```

### Personalizar Template de PR
Modifique a seção `--body` no workflow:
```bash
--body "## Meu Template Personalizado
Branch: $BRANCH -> $BASE
Descrição customizada aqui."
```

## 🔐 Permissões e Segurança

### Permissões Necessárias
O workflow usa o token padrão do GitHub (`GITHUB_TOKEN`) com estas permissões:
- `contents: read` - Para ler o código
- `pull-requests: write` - Para criar e comentar PRs

### Segurança
- ✅ Usa token padrão (sem secrets adicionais)
- ✅ Não executa em merge commits
- ✅ Limitado a branches específicos
- ✅ Não tem acesso a segredos

## 🧪 Testando o Workflow

### Teste Manual
1. Execute o workflow de teste:
```bash
# Via GitHub UI: Actions > Test Auto PR Workflow > Run workflow
```

2. Ou crie um branch de teste:
```bash
git checkout -b feature/test-auto-pr
echo "test" > test.txt
git add test.txt
git commit -m "Test auto PR workflow"
git push origin feature/test-auto-pr
```

### Verificações
- ✅ PR foi criado automaticamente?
- ✅ Título está correto?
- ✅ Labels foram aplicados?
- ✅ Descrição está completa?

## 🐛 Resolução de Problemas

### PR não foi criado
**Possíveis causas:**
- Branch está na lista de ignorados
- É um merge commit
- Erro de permissões

**Solução:**
1. Verifique os logs do workflow em Actions
2. Confirme que o branch não está ignorado
3. Verifique permissões do repositório

### Labels não aparecem
**Causa:** Labels não existem no repositório

**Solução:**
1. Criar labels manualmente no GitHub:
   - `enhancement`
   - `bug`
   - `documentation`
   - `tests`
   - `refactoring`
   - `auto-pr`

### Título não está correto
**Causa:** Padrão do branch não está sendo reconhecido

**Solução:**
1. Usar convenção: `tipo/descrição`
2. Exemplos válidos:
   - `feature/nova-funcao`
   - `fix/corrigir-bug`
   - `docs/atualizar-docs`

## 📊 Monitoramento

### Verificar Execuções
1. Acesse **Actions** no GitHub
2. Procure workflow **"Auto Pull Request"**
3. Veja logs de execuções

### Métricas Úteis
- Número de PRs criados automaticamente
- Tempo médio de criação
- Taxa de sucesso do workflow

## 🔄 Atualizações

### Versão Atual
- Workflow simplificado e estável
- Suporte a padrões principais de branch
- Prevenção de duplicatas

### Próximas Versões
- [ ] Integração com templates de PR
- [ ] Suporte a múltiplos reviewers
- [ ] Notificações personalizadas
- [ ] Integração com Slack/Teams

## 💡 Dicas e Boas Práticas

### Convenções de Branch
```bash
# ✅ Bom
feature/user-authentication
fix/login-bug
docs/readme-update

# ❌ Evitar
nova-funcionalidade
bug123
update
```

### Mensagens de Commit
```bash
# ✅ Bom - será usado como título se branch não seguir convenção
git commit -m "Implement user authentication system"

# ❌ Evitar
git commit -m "fix"
git commit -m "changes"
```

### Workflow de Equipe
1. **Criar branch** com convenção apropriada
2. **Desenvolver** a funcionalidade
3. **Push** - PR criado automaticamente
4. **Revisar** e aprovar o PR
5. **Merge** quando aprovado

## 🆘 Suporte

### Recursos Úteis
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [Pull Request Best Practices](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests)

### Solicitação de Ajuda
1. Verifique logs do workflow
2. Consulte este guia
3. Abra issue se problema persistir

---

🎉 **Workflow configurado e pronto para uso!**

Agora cada push em branches de desenvolvimento criará automaticamente PRs, facilitando o processo de revisão e colaboração da equipe.