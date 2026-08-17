# ADR-006: Scrape do python-jobspy isolado em subprocesso

## Status

Accepted

## Date

2026-08-17

## Context

A busca diária de vagas (`fetch_daily_jobs`, 35 termos) saturou o worker Celery
em produção: ~750 threads vivas, 95% de CPU e load 228 no host de 1 vCPU. A
sessão do WhatsApp caiu junto, por falta de CPU.

A causa está na paginação do scraper do LinkedIn dentro do python-jobspy
(`jobspy/linkedin/__init__.py`):

```python
start += len(job_list)
```

Quando um termo deixa de retornar vagas novas, `len(job_list)` é 0, `start`
nunca avança e o guard `start < 1000` nunca dispara. O laço repete a mesma
requisição para sempre, gastando CPU em request + parse de HTML. A thread que
executa isso **não é abortável**: o `ThreadPoolExecutor` do jobspy não oferece
cancelamento, e um timeout no lado do chamador apenas abandona a thread, que
continua rodando. A cada execução diária o worker acumulava mais threads presas.

Três caminhos foram considerados:

1. **Corrigir/forkar o python-jobspy** — resolve a causa, mas nos coloca como
   mantenedores de um fork e não protege contra o próximo laço infinito da
   biblioteca (Indeed e Glassdoor têm paginação parecida).
2. **`multiprocessing.Process` por termo** — foi a primeira tentativa (commit
   `0e2154a`) e **falhou em 100% dos termos em produção**: a busca roda dentro
   de um `ForkPoolWorker` do Celery, que é um processo daemônico, e o
   multiprocessing proíbe filhos de daemon (`AssertionError: daemonic processes
   are not allowed to have children`). O fetch passou a salvar zero vagas.
3. **`subprocess` por termo** — não tem a restrição de processo daemônico.

## Decision

**Cada termo roda `scrape_jobs` em um processo separado, iniciado por
`subprocess.run([sys.executable, "-m", "infra.jobspy._scrape_runner"])`, com
timeout.**

- `infra/jobspy/_scrape_runner.py` lê os kwargs em JSON pelo stdin e devolve
  `{"records": [...]}` ou `{"error": "..."}` pelo stdout. Não carrega o Django:
  o processo é descartável e pode morrer a qualquer momento sem deixar
  transação, conexão ou thread pendente no worker.
- O stdout é canal exclusivo da resposta; `sys.stdout` é desviado para o stderr
  enquanto o scrape roda, para que um print de biblioteca não corrompa o JSON.
- `infra/jobspy/records.py` isola a normalização do DataFrame para JSON, de modo
  que o runner não precise importar o serviço inteiro.
- O timeout por termo passou a 40s por incluir o startup do interpretador
  (import do pandas custa ~1s local e alguns segundos no host de 1 vCPU).

## Consequences

**Positivas**

- O timeout mata o processo de verdade (SIGKILL), levando junto as threads
  inabortáveis. Um termo travado não contamina os demais nem o worker.
- Vale para qualquer laço infinito futuro da biblioteca, não só o do LinkedIn.
- Um crash do scraper (inclusive OOM) vira um erro por termo, não uma queda da
  task inteira.

**Negativas**

- Um interpretador novo por termo: ~1s local, alguns segundos no host pequeno.
  Com 35 termos, é custo aceitável para uma task diária.
- Testes que mockavam `scrape_jobs` no processo do pytest não valem mais para o
  caminho de execução — o mock vive na memória do processo de teste, e o scrape
  roda em outro. A suíte passou a exercitar o protocolo com runners falsos em
  `tmp_path`, incluindo a prova de que o timeout mata o processo.

## Validação em produção

Execução manual de `fetch_daily_jobs` após o deploy (2026-08-17): 35 termos
processados, 305 vagas salvas, 0 erros, e o worker Celery com 1 thread por
processo.
