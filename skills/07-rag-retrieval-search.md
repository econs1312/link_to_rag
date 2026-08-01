# Skill: Vector Search & Retrieval API

- **Endpoint de Busca:** `POST /api/v1/search`
  - **Entrada:** `query` (str), `limit` (int = 5), `filter_metadata` (dict opcional, ex: por canal ou autor).
- **Gerador de Embeddings:** Converte a `query` de texto usando o mesmo modelo utilizado na ingestão (`text-embedding-3-small` da OpenAI ou equivalente).
- **Busca Híbrida (Hybrid Search):**
  - Combine a busca por Similaridade de Cosseno no PgVector (`<=>`) com a busca por palavras-chave em texto completo do PostgreSQL (`tsvector`/`tsquery`).
  - Aplique Reciprocal Rank Fusion (RRF) ou re-ranking simples para ordenar os `chunks` mais relevantes antes de responder ao agente de IA.