# Skill: Text Cleaning, Chunking & PgVector Ingestion

1. **Higienização:**
   - Remova tags HTML remanescentes.
   - Remova sequências de quebras de linha maiores que `\n\n`.
   - Mantenha a estrutura em Markdown (títulos, listas, negritos) pois retêm semântica para LLMs.
   - Adicione o Frontmatter em YAML no topo do documento final.

2. **Estratégia de Chunking:**
   - Utilize a estratégia de `RecursiveCharacterTextSplitter` da LangChain ou LlamaIndex.
   - `chunk_size`: 800 caracteres.
   - `chunk_overlap`: 120 caracteres.
   - Mantenha a ordem dos chunks armazenando um índice incremental (`chunk_index`).

3. **Persistência no Banco:**
   - Tabela `documents`: ID, URL, título, conteúdo original em Markdown, status, timestamps.
   - Tabela `document_chunks`: ID, document_id, chunk_index, chunk_text, embedding (vector(1536)).