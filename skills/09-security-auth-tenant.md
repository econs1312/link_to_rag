# Regras de Segurança, Autenticação e Multi-Tenancy

Este projeto (L2RAG) lida com ingestão de URLs externas e armazenamento vetorial. A segurança e o isolamento dos dados são críticos.

## 1. Prevenção de SSRF (Server-Side Request Forgery)
- **Regra Estrita:** Todas as URLs enviadas para ingestão via API devem ser validadas para impedir ataques SSRF.
- **Implementação:** No modelo Pydantic (`IngestRequest`), utilize validadores personalizados para rejeitar domínios ou IPs que apontem para redes locais ou privadas (ex: `127.0.0.1`, `localhost`, `10.0.0.0/8`, `192.168.0.0/16`, `169.254.169.254`).
- Nunca permita que os extratores acedam a hosts internos da infraestrutura.

## 2. Autenticação de API (API Keys)
- A API não deve estar aberta ao público em produção.
- Utilize um sistema de injeção de dependências do FastAPI (`Depends`) para validar o cabeçalho `Authorization` ou `X-API-Key`.
- **Aviso em Dev:** Se a variável `API_KEYS` estiver ausente ou vazia no ficheiro `.env`, o sistema deve emitir um `log.warning` no arranque a avisar que a API está a correr sem autenticação (útil para desenvolvimento local), mas nunca deve falhar silenciosamente em produção.

## 3. Isolamento Multi-Tenant
- **Regra Estrita:** Nenhum cliente/utilizador pode aceder aos documentos ou tarefas de outro.
- O campo `tenant_id` deve estar presente em todas as queries à base de dados relacional e vetorial.
- Nunca crie rotas como `GET /documents/{id}` sem validar se o `tenant_id` do utilizador autenticado corresponde ao dono do documento.