# Padrões de Tratamento de Erros e Respostas da API

Uma API resiliente não expõe erros do sistema (Tracebacks) diretamente ao usuário, mas sim respostas estruturadas.

## 1. Formato de Resposta Padrão (JSend)
Todas as respostas da API, sejam de sucesso ou erro, devem seguir o formato padronizado.

- **Sucesso (200/201/202):**
  ```json
  {
    "status": "success",
    "data": { "id": 123, "job_id": "..." }
  }


Erro (4xx / 5xx):

{
  "status": "error",
  "message": "Mensagem amigável para o usuário",
  "code": "ERR_VALIDATION",
  "trace_id": "uuid-da-requisicao"
}

2. Global Exception Handlers (FastAPI)
Utilize os decoradores @app.exception_handler() no FastAPI para interceptar exceções não tratadas.

SQLAlchemy: Se ocorrer um erro de banco de dados (ex: Constraint Violation), o handler deve capturá-lo e retornar um erro HTTP 400 ou 500 genérico. Regra Estrita: Nunca devolva detalhes da estrutura do banco de dados (nomes de colunas ou tabelas) na resposta HTTP.

Pydantic (422): Os erros de validação RequestValidationError devem ser mapeados para um formato limpo e legível em vez do array verboso padrão do FastAPI.

3. Registro (Logging) Obrigatório
Todos os erros (níveis ERROR ou CRITICAL) capturados pelos Exception Handlers devem ser registrados no structlog, incluindo a injeção do trace_id e o traceback interno (no log do servidor, nunca na resposta HTTP enviada ao cliente).