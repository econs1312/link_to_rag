# Skill: Testing & Fixtures Strategy

- **Testes Unitários:** Escreva testes com `pytest` e `pytest-asyncio`.
- **Mocks de Extratores (VCR / Fixtures):**
  - NENHUM teste automatizado deve fazer requisições HTTP reais para redes sociais, YouTube ou Jina.
  - Crie uma pasta `tests/fixtures/` contendo retornos fictícios de HTML e JSON de postagens para simular a resposta dos extratores.
- **Testes de Integração com Banco:** Testes de banco devem rodar contra uma instância isolada do PostgreSQL via Testcontainers ou SQLite em memória para o PgVector.