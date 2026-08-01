# Skill: Rate Limiting & Cost Management

- **Gestão de Proxies:** Sempre que fizer requisições diretas a redes sociais ou sites com Cloudflare/anti-bot, utilize o pool de IP rotativo configurado via `PROXY_URL`.
- **Tratamento de Rate Limit (HTTP 429):**
  - Ao receber status code `429` de qualquer serviço externo (Jina, OpenAI, Apify), capture o header `Retry-After`.
  - Se o header não existir, aplique um tempo de espera padrão de 60 segundos antes de tentar o próximo `retry` no worker.
- **Circuit Breaker:** Se o mesmo domínio falhar 5 vezes seguidas por bloqueio (HTTP 403 ou 429), pause as requisições para esse domínio por 15 minutos e sinalize a fila.