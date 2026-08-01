# Skill: Async Job Processing & Queues

- **Comportamento do Endpoint:** `/api/v1/ingest` deve Apenas validar a URL de entrada, salvar o registro inicial com status `PENDING`, publicar o `job_id` no Redis/ARQ e retornar HTTP 202 imediatamente em menos de 200ms.
- **Worker Async:** Utilize `ARQ` (Async Redis Queue) ou `Celery` assíncrono para os workers.
- **Políticas de Retry:**
  - Qualquer falha de rede/scraping deve tentar novamente com Exponential Backoff (3 tentativas max: 2s, 8s, 32s).
  - Se falhar após 3 tentativas, marque o status do Job como `FAILED` no banco e salve o traceback no campo `error_message`.