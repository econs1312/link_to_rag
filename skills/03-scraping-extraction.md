# Skill: Content Extraction Strategy

Sempre utilize o padrão Strategy para identificar e processar as URLs de entrada:

1. **Roteador (`LinkRouter`):**
   - Identifica o padrão da URL recebida via Regex ou urllib.parse.

2. **Estratégias de Extração:**
   - **YouTube (`YouTubeExtractor`):** Extrai o ID do vídeo -> usa `youtube-transcript-api` para obter a legenda. Se não houver legenda pública, faz download do áudio via `yt-dlp` e chama a API do OpenAI Whisper.
   - **Web / Artigos (`WebExtractor`):** Tenta primeiro via Jina Reader API (`https://r.jina.ai/{URL}`). Se retornar status != 200, usa `Firecrawl` ou fallback local com `httpx` + `Readability`.
   - **Redes Sociais (`SocialMediaExtractor`):** Se a URL for do Instagram, TikTok ou X, utiliza o SDK do Apify configurado via variável de ambiente `APIFY_API_TOKEN`.

3. **Contrato de Saída dos Extratores:**
   Todos os extratores devem retornar um objeto `ExtractedContent`:
   `{ raw_text: str, title: str, author: str, metadata: dict, source_url: str }`