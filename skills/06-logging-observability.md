# Skill: Structured Logging & Observability

- **Logs Estruturados:** Utilize a biblioteca `structlog` ou `loguru`. Todos os logs devem ser emitidos em formato JSON no stdout.
- **Rastreabilidade (Trace ID):**
  - Cada requisição que entra no `/ingest` deve gerar um `correlation_id` único (UUIDv4).
  - O `correlation_id` deve ser repassado do FastAPI para as tarefas do Redis/Worker e impresso em **todos** os logs do pipeline daquela extração.
- **Contexto nos Logs:** Nunca logue apenas "Erro ao extrair". Inclua sempre: `{"correlation_id": "...", "job_id": "...", "target_url": "...", "extractor": "YouTubeExtractor", "error": "..."}`.