SAMPLE_HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Introdução ao RAG e Vetores</title>
</head>
<body>
    <header><h1>Header do Site</h1></header>
    <main>
        <p>O Retrieval-Augmented Generation (RAG) é uma técnica que combina busca de informação com modelos de linguagem de grande porte (LLMs).</p>
        <p>Ao invés de apenas gerar texto a partir dos pesos pré-treinados, o sistema recupera documentos relevantes de uma base vetorial.</p>
    </main>
    <footer>Copyright 2026</footer>
</body>
</html>
"""

SAMPLE_RAW_TEXT = """
Introdução ao RAG e Vetores.


O Retrieval-Augmented Generation (RAG) é uma técnica poderosa!   
Ela junta bancos de dados vetoriais com LLMs.


<script>alert('test')</script>
Outro parágrafo importante com mais detalhes.
"""

SAMPLE_YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
]

SAMPLE_SOCIAL_URLS = [
    "https://www.instagram.com/p/C123456789/",
    "https://twitter.com/user/status/123456789",
    "https://x.com/user/status/123456789",
    "https://www.linkedin.com/posts/activity-123456789/",
    "https://www.tiktok.com/@user/video/123456789",
]

SAMPLE_WEB_URLS = [
    "https://techcrunch.com/2026/07/26/ai-agents-evolution/",
    "https://news.ycombinator.com/item?id=1000",
]
