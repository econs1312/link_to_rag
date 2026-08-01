# Skill: FastAPI Clean Architecture & Code Standards

- **Linguagem & Runtime:** Python 3.11+ utilizando código totalmente assíncrono (`async/await`).
- **Tipagem Severa:** Toda função deve conter Type Hints explícitos do Python (`pydantic` v2 para Schemas e DTOs).
- **Estrutura de Camadas:**
  - `api/`: Endpoints e rotas da aplicação (não contêm lógica de negócio).
  - `services/`: Casos de uso e orquestração do pipeline.
  - `extractors/`: Adaptadores isolados para extração de cada plataforma (Strategy Pattern).
  - `models/`: Modelos de banco de dados (SQLAlchemy 2.0 Async).
  - `schemas/`: Modelos Pydantic de entrada, saída e contratos internos.
- **Tratamento de Erros:** Não use blocos try/except genéricos. Dispare exceções customizadas herdando de uma classe base `AppException`.