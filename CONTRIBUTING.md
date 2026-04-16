# Contributing to CapyVagas UTFPR

Welcome! This guide covers how to contribute to the CapyVagas project.

## Branch Conventions

We use **GitHub Flow** for branch management:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features | `feature/login-oauth` |
| `fix/` | Bug fixes | `fix/erro-timeout-api` |
| `release/` | Release preparation (optional) | `release/v1.1` |
| `hotfix/` | Urgent production fixes (optional) | `hotfix/erro-ssl-certificado` |

### Naming Rules

1. **Lowercase only** — all words in lowercase
2. **Hyphens as separators** — use `-`, not `_` or spaces
3. **No issue numbers** — keep names descriptive and clean
4. **Short descriptions** — ideally under 50 characters
5. **No special characters** — only letters, numbers, hyphens, and `/`

### Examples

```bash
# Good
feature/adicionar-filtro-vagas
fix/corrigir-timeout-api
hotfix/erro-ssl-certificado

# Bad
feature/Feature_Login_OAuth  # Uppercase and underscores
fix/bugfix                   # Too generic
feature/123                  # Only numbers
feature/login oauth           # Spaces
```

## Pull Request Workflow

1. **Create branch** from master:
   ```bash
   git checkout master && git pull
   git checkout -b feature/minha-feature
   ```

2. **Develop and commit** using Conventional Commits:
   ```bash
   git add . && git commit -m "feat: adiciona feature X"
   ```

3. **Push and create PR**:
   ```bash
   git push -u origin feature/minha-feature
   # Open PR on GitHub
   ```

4. **CI runs automatically**:
   - `Lint` — ruff check + ruff format
   - `Test` — pytest with 70% coverage
   - `Security` — pip-audit + trivy

5. **Review**:
   - Require 1 approval from any project member
   - GitHub Copilot Code Review (if available)

6. **Merge**:
   - PR approved + CI passing → merge to master
   - Strategy: **Squash merge** (one commit per feature)

## Branch Protection Rules

The `master` branch is protected with the following rules:

- ✅ **Pull request required** — direct pushes forbidden
- ✅ **1 approval required** — at least one reviewer must approve
- ✅ **Dismiss stale approvals** — new commits revoke previous approvals
- ✅ **Status checks required** — Lint, Test, and Security must pass
- ✅ **Linear history** — no merge commits allowed

## Merge Strategy

We use **squash merging** by default:

- All commits from the feature branch are combined into a single commit on master
- Keeps master history clean and linear
- Each feature/fix = one commit

### Configuring Squash Merge

To enable in GitHub:
1. Go to **Settings** → **General** → **Pull Requests**
2. Enable **Allow squash merging**
3. Optionally set **Default to squash merging**

## Code Style

- Follow existing code patterns in the project
- Run `ruff check` and `ruff format` before committing
- Use Conventional Commits for commit messages: `feat:`, `fix:`, `docs:`, etc.

## Questions?

Open an issue or start a discussion on GitHub.
