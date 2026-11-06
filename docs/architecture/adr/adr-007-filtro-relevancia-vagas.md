# ADR-007: Filtro de relevância das vagas online e catálogo único de termos

## Status

Accepted

## Date

2026-11-06

## Context

Antes do teste com alunos, a busca online (python-jobspy) trazia ~240 vagas/dia,
mas na semana de 31/10 a 06/11/2026 **só 17% eram do Brasil** (287 de 1712). O
resto era dos EUA, mais "Jovem Aprendiz", vendedor, sênior e estágio de outras
áreas. Investigando com buscas reais (python-jobspy 1.4.1):

- **LinkedIn não entende `location="Brasil"`** e devolve vagas dos EUA; com
  `"Brazil"`, 10–11 de 15 são do Brasil. Também **ignora a cidade** ("Cascavel"
  devolve Natal e Recife) e, desde o jobspy 1.4, **ignora `is_remote` e
  `job_type`** (só avisa em `DataFrame.attrs["warnings"]`).
- **Indeed respeita cidade, raio e remoto.** "estágio" num raio de 75 milhas de
  "Santa Helena, PR" cobre Cascavel, Toledo, Foz, Medianeira e MCR.
- **Termos específicos no Indeed regional voltam vazios** ("estágio agronomia"
  → 0); o termo amplo "estágio" traz 35–70 vagas, quase todas genéricas
  (agência bancária, RH, jurídico).
- **Glassdoor** voltou a funcionar no jobspy 1.2+, mas devolve as mesmas vagas
  do Indeed, sem descrição, e não aceita "Santa Helena, Paraná, Brazil".
- **Google Jobs** está indisponível no jobspy (FAQ oficial); a API pública da
  **Gupy** mudou de rota e não responde.
- Os dados de cursos/termos existiam em três cópias divergentes (comando
  `seed_courses`, fixture JSON e banco), e em produção os 3 cursos estavam sem
  área (carregados depois da migração que associa curso → área).

Regra de produto definida com o requisitante: o aluno só vê **estágio da área
do curso** — presencial na região de Santa Helena ou remoto — e **vagas remotas
de nível inicial** que dê para conciliar com a graduação.

## Decision

1. **Buscar amplo e classificar depois.** Cada `SearchTerm` ganha `scope`
   (`regional`/`remoto`); `apps/jobs/relevance.py` decide vaga a vaga:
   - exclui aprendiz, sênior/pleno, gerência, vendedor, docência;
   - exclui local fora do Brasil;
   - regional: cidade do Oeste do Paraná (lista em `OESTE_PARANA`) e título de estágio;
   - remoto: sinal de remoto (filtro do Indeed, ou texto "remoto/home office"),
     sem "híbrido/presencial", e título de estágio ou nível inicial (júnior, trainee);
   - área: palavra-chave do curso no título **ou** nome do curso na descrição.
   Palavras-chave e nomes ficam no `Course` (`job_title_keywords`,
   `job_course_names`), editáveis no admin.
2. **Dedupe entre sites e cidades** (título+empresa e título+cidade, preferindo
   a versão com descrição) e **no máximo 2 vagas por empresa** por termo.
3. **Catálogo único** em `apps/courses/catalog.py`, usado pelo `seed_courses` e
   pela migração `0006_apply_course_catalog` (que corrige a área dos cursos e
   troca os 35 termos antigos por 12). A fixture JSON foi removida.
4. **Buscas idênticas rodam uma vez por dia** (a regional e a remota amplas se
   repetem nos 3 cursos): ~8 scrapes/dia em vez de 35, menos chance de 429 do LinkedIn.
5. **O aluno só vê opção com vaga**: o menu lista os termos com vaga na última
   coleta, com a contagem; "Ver Review" lê o `DailyJob` em vez de rodar o jobspy
   ao vivo durante a conversa.
6. **Diagnóstico por site**: o runner repassa `attrs["errors"]` (ex.: 429) e
   `attrs["warnings"]`; o serviço loga `jobspy_board_errors`, e a task loga
   `fetch_daily_jobs_term` com `found`, `kept` e o motivo de cada recusa.

## Consequences

- Muito menos vagas, mas úteis. Agronomia e Biologia vão ter dias sem nenhuma
  vaga — é o mercado da região, não falha. O alarme de scraper quebrado
  (`fetch_daily_jobs_no_results`) olha o que os sites devolveram, não o que o
  filtro manteve.
- Computação depende quase só de remoto (júnior/estágio), como esperado.
- Termo sem `scope` mantém o comportamento antigo (sem filtro) — útil para
  termos experimentais criados no admin. Curso sem palavras-chave não filtra área.
- O "Testar busca" do admin mostra o resultado já filtrado e o motivo das
  recusas, para calibrar palavras-chave sem deploy.
- Adzuna (API oficial, chave gratuita) fica como próxima fonte se o volume
  ficar baixo demais; Gupy e Google estão fora por não terem acesso estável.

## Alternatives Considered

- **Termos específicos por curso no Indeed regional** (o desenho anterior, 35
  termos): voltam vazios; o LinkedIn "preenchia" com vagas de outro país.
- **Ranking por pontuação em vez de filtro**: com tão poucas vagas boas, ordenar
  ruído não ajuda — o aluno ainda veria "Jovem Aprendiz" no fim da lista.
- **Mostrar estágio genérico da região a todos os cursos**: recusado pelo
  requisitante ("apenas as que pedem o curso e são da área").
