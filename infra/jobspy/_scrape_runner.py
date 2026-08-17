"""Executa uma única busca do python-jobspy em processo isolado.

Invocado como `python -m infra.jobspy._scrape_runner` por
`infra.jobspy.service._run_scrape`. Lê os kwargs de `scrape_jobs` como JSON no
stdin e escreve no stdout `{"records": [...]}` ou `{"error": "..."}`.

Roda fora do Celery e sem carregar o Django: o processo é descartável e pode
ser morto a qualquer momento (é o que garante o timeout real da busca) sem
deixar transação, conexão ou thread pendente no worker.
"""

import contextlib
import json
import sys


def _emit(payload: dict, stream) -> None:
    json.dump(payload, stream)
    stream.flush()


def main() -> int:
    # O stdout é o canal exclusivo da resposta JSON: guardamos a referência real
    # e desviamos `sys.stdout` para o stderr enquanto o scrape roda, para que um
    # print de biblioteca não corrompa o que o processo pai vai parsear.
    response = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        try:
            scrape_kwargs = json.load(sys.stdin)
        except ValueError as exc:
            _emit({"error": f"kwargs invalidos: {exc}"}, response)
            return 1

        try:
            from jobspy import scrape_jobs

            from infra.jobspy.records import records_from_dataframe

            records = records_from_dataframe(scrape_jobs(**scrape_kwargs))
        except Exception as exc:
            _emit({"error": f"{type(exc).__name__}: {exc}"}, response)
            return 1

    _emit({"records": records}, response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
