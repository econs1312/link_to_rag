Vamos montar o **PRD Inicial (v1.0)** da nossa **API de Ingestão e Processamento de Links para RAG**.

---

# 📄 PRD: Link-to-Text Ingestion Service (RAG Engine)

## 1. Visão Geral do Produto

O **Link-to-Text Ingestion Service** é um microsserviço focado em receber URLs (notícias, artigos, posts de redes sociais e vídeos) enviadas por usuários ou integrações (ex: WhatsApp/SaaS), extrair o conteúdo textual limpo, estruturar metadados e persistir o resultado em uma base de dados pronta para consumo por agentes de IA (RAG).

---

## 2. Objetivos Principais

* **Universalidade:** Ser capaz de extrair texto de sites comuns, redes sociais e vídeos (transcrição).
* **Limpeza e Formatação:** Entregar textos em Markdown padronizado, livres de scripts, propagandas e elementos de UI.
* **Prontidão para IA:** Gerar trechos (*chunks*) otimizados para embeddings e buscas vetoriais.
* **Arquitetura Assíncrona:** Garantir respostas rápidas ao solicitante via enfileiramento do processamento pesado.

---

## 3. Escopo Funcional (Módulos do Sistema)

### Módulo A: API Gateway & Ingestão (Endpoints)

1. **`POST /api/v1/ingest`**
* **Entrada:** `url` (string), `source_type` (opcional: auto-detect), `metadata` (tags, tenant_id, etc.).
* **Comportamento:** Valida a URL, gera um `job_id`, coloca a tarefa na fila e retorna HTTP 202 (Accepted).


2. **`GET /api/v1/jobs/{job_id}`**
* **Comportamento:** Retorna o status do processamento (`pending`, `processing`, `completed`, `failed`) e o resultado/ID do documento gerado.



### Módulo B: Roteador e Extratores de Conteúdo (*Scrapers/Adapters*)

* **Roteador Inteligente:** Identifica o domínio do link e direciona para o extrator correto:
* **Web Extractor (Geral):** Integração com Jina Reader API (`[https://r.jina.ai/](https://r.jina.ai/)`) ou Firecrawl API para conversão direta de HTML para Markdown.
* **YouTube Extractor:** Uso da `youtube-transcript-api` (ou `yt-dlp` + OpenAI Whisper para vídeos sem legenda manual).
* **Social Media Extractor (Instagram/LinkedIn/X/TikTok):** Integração com rotinas via Apify / Playwright headless para raspagem de legendas e metadados da postagem.



### Módulo C: Processamento de Texto & Chunking

1. **Sanitização:** Remoção de múltiplos espaços em branco, quebras de linha desnecessárias, emojis redundantes e links quebrados.
2. **Adição de Metadados Standard:** Inserção de cabeçalho YAML/Markdown contendo:
```markdown
---
title: "Título do Artigo"
source_url: "https://..."
author: "Nome do Autor"
extracted_at: "2026-07-26T17:18:00Z"
---

```


3. **Chunking Otimizado:** Divisão do texto usando estratégia de janela deslizante (ex: 500 a 1000 caracteres com *overlap* de 10% a 15%).

### Módulo D: Persistência / Repositório

* Salvar o documento consolidado e seus *chunks* no banco de dados.
* Suporte nativo para gravação em banco relacional/vetorial (ex: PostgreSQL com `pgvector` ou Supabase).

---

## 4. Arquitetura Técnica & Stack Recomendada

* **Linguagem / Framework:** Python (FastAPI) *— Ideal para manipulação de texto, integrações de IA e scrapers.*
* **Fila / Filas Assíncronas:** Celery + Redis ou Redis + ARQ (Python async).
* **Banco de Dados:** PostgreSQL (com extensão `pgvector` ativada) via SQLAlchemy/ORM.
* **Extratores Externos:** Jina AI / Firecrawl, Apify SDK, YouTube Transcript API.

---

## 5. Requisitos Não-Funcionais

* **Tempo de Resposta do Webhook/Ingestão:** $< 500\text{ ms}$ para a resposta inicial do job.
* **Resiliência:** Sistema de *retry* automático (até 3 tentativas) para falhas de rede ou bloqueio temporário de scraping.
* **Logs e Rastreabilidade:** Registro detalhado de logs por `job_id` para identificação rápida de links que falharam na extração.

---

## 6. Próximos Passos para a Prompting no Antigravity

Para começar a codificar no Antigravity sob a filosofia de *vibe coding*, a melhor estratégia é dividir o projeto em tarefas pequenas (*micro-prompts*):

1. **Sprint 1 (Base da API e Fila):** Criar a estrutura base do projeto FastAPI, Docker Compose (PostgreSQL + Redis) e o endpoint `/ingest` jogando no Redis.
2. **Sprint 2 (Extratores):** Implementar o módulo de roteamento de links e integrações (Jina/Firecrawl para Web e YouTube API para vídeos).
3. **Sprint 3 (Chunking & Banco):** Implementar o serviço de divisão de texto e salvar os registros no PostgreSQL/PGVector.

---