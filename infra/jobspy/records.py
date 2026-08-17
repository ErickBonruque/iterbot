import json
from typing import Any


def records_from_dataframe(jobs_df) -> list[dict[str, Any]]:
    """Converte DataFrame em lista de dicts JSON-serializáveis.

    `jobs_df.to_dict("records")` preserva tipos pandas/numpy (Timestamp, NaN,
    int64, etc.) que não são compatíveis com `json.dumps` — quebra ao gravar
    em `request.session` (Django usa JSONSerializer por padrão desde 4.1) e
    em qualquer outra serialização downstream.

    Roteamos via `to_json(orient="records", date_format="iso")` que cuida da
    conversão (Timestamp → ISO string, NaN → null, numpy → tipos nativos).

    Vive em módulo próprio (e não em `service.py`) para que o runner isolado
    possa importá-lo sem arrastar junto structlog e o resto do serviço.
    """
    if jobs_df is None or jobs_df.empty:
        return []
    return json.loads(jobs_df.to_json(orient="records", date_format="iso"))
