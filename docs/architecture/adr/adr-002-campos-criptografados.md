# ADR-002: Campos Criptografados (EncryptedCharField)

## Status

Accepted

## Date

2026-04-16

## Context

Dados sensiveis como chaves de API, tokens e senhas devem ser armazenados de forma segura no banco de dados. O PostgreSQL por si so nao oferece criptografia em nivel de coluna, e backups do banco podem ser comprometidos se acessados por terceiros.

O projeto usa Docker Secrets para configuracao, mas ha campos no banco que armazenam valores que precisam de protecao adicional.

## Decision

Utilizar Django EncryptedCharField com criptografia Fernet para campos sensiveis no banco de dados.

### Implementacao

- Campo `EncryptedCharField` do pacote `django-fernet-fields`
- Chave de criptografia gerenciada via variavel de ambiente `FERNET_KEY`
- Campos afetados: chaves de API externas, tokens de sessao

## Consequences

### Positive
- Dados criptografados em repouso no banco de dados
- Protecao contra leitura de backups por terceiros
- Compliance com melhores praticas de seguranca

### Negative
- Overhead de performance em leitura/escrita (~5-10ms por operacao)
- Requer gerenciamento adicional da chave Fernet
- Backup da chave tambem essencial

### Neutral
- Interface da aplicacao permanece inalterada
- Transicoes de dados ja criptografados requerem migracao especial
