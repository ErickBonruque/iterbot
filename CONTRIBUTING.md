# Contribuindo com o IterBot UTFPR

Bem-vindo! Este guia explica como contribuir com o projeto IterBot.

## Convenções de Branch

Usamos **GitHub Flow** para o gerenciamento de branches:

| Prefixo | Propósito | Exemplo |
|---------|-----------|---------|
| `feature/` | Novas funcionalidades | `feature/login-oauth` |
| `fix/` | Correções de bugs | `fix/erro-timeout-api` |
| `release/` | Preparação de release (opcional) | `release/v1.1` |
| `hotfix/` | Correções urgentes em produção (opcional) | `hotfix/erro-ssl-certificado` |

### Regras de Nomenclatura

1. **Apenas minúsculas** — todas as palavras em caixa baixa
2. **Hífens como separadores** — use `-`, não `_` nem espaços
3. **Sem números de issue** — mantenha nomes descritivos e limpos
4. **Descrições curtas** — idealmente com menos de 50 caracteres
5. **Sem caracteres especiais** — apenas letras, números, hífens e `/`

### Exemplos

```bash
# Bom
feature/adicionar-filtro-vagas
fix/corrigir-timeout-api
hotfix/erro-ssl-certificado

# Ruim
feature/Feature_Login_OAuth  # Maiúsculas e underscores
fix/bugfix                   # Genérico demais
feature/123                  # Só números
feature/login oauth          # Espaços
```

## Fluxo de Pull Request

1. **Crie a branch** a partir do master:
   ```bash
   git checkout master && git pull
   git checkout -b feature/minha-feature
   ```

2. **Desenvolva e commite** usando Conventional Commits:
   ```bash
   git add . && git commit -m "feat: adiciona feature X"
   ```

3. **Faça push e abra o PR**:
   ```bash
   git push -u origin feature/minha-feature
   # Abra o PR no GitHub
   ```

4. **O CI roda automaticamente**:
   - `Lint` — ruff check + ruff format
   - `Test` — pytest com 70% de cobertura
   - `Security` — pip-audit + trivy

5. **Revisão**:
   - Exige 1 aprovação de qualquer membro do projeto
   - GitHub Copilot Code Review (se disponível)

6. **Merge**:
   - PR aprovado + CI verde → merge no master
   - Estratégia: **Squash merge** (um commit por feature)

## Regras de Proteção de Branch

A branch `master` é protegida com as seguintes regras:

- ✅ **Pull request obrigatório** — pushes diretos são proibidos
- ✅ **1 aprovação obrigatória** — pelo menos um revisor precisa aprovar
- ✅ **Aprovações antigas são descartadas** — novos commits revogam aprovações anteriores
- ✅ **Status checks obrigatórios** — Lint, Test e Security precisam passar
- ✅ **Histórico linear** — sem commits de merge

## Estratégia de Merge

Usamos **squash merge** por padrão:

- Todos os commits da branch de feature são combinados em um único commit no master
- Mantém o histórico do master limpo e linear
- Cada feature/fix = um commit

### Configurando o Squash Merge

Para habilitar no GitHub:
1. Vá em **Settings** → **General** → **Pull Requests**
2. Habilite **Allow squash merging**
3. Opcionalmente marque **Default to squash merging**

## Estilo de Código

- Siga os padrões de código existentes no projeto
- Rode `ruff check` e `ruff format` antes de commitar
- Use Conventional Commits nas mensagens: `feat:`, `fix:`, `docs:` etc.

## Dúvidas?

Abra uma issue ou inicie uma discussão no GitHub.
