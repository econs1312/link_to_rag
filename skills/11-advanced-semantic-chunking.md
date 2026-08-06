# Chunking Semântico e Enriquecimento de Contexto

Para garantir que o LLM responda com alta precisão, o processo de divisão de texto (chunking) deve ser inteligente e não apenas matemático.

## 1. Quebra Semântica (Semantic Boundaries)
- Evite dividir textos a meio de uma frase apenas porque o limite de caracteres foi atingido (ex: `RecursiveCharacterTextSplitter` ingénuo).
- A IA que programar o sistema deve favorecer estratégias que analisem o fim de sentenças, parágrafos ou até mudanças de tópico (Semantic Chunking) para preservar o significado completo de uma ideia no chunk.

## 2. Injeção de Metadados no Chunk
- Antes de gerar o vetor (embedding) de um bloco de texto, o texto deve ser enriquecido com os metadados do documento original.
- **Padrão:** O chunk deve ter um formato semelhante a:

	[Documento: Título do Artigo]
	[Autor: Nome]

	<conteúdo do chunk>

- Isto garante que a busca vetorial (PgVector) consiga encontrar termos chave que não estão explicitamente repetidos naquele parágrafo específico, mas que pertencem à entidade maior.

## 3. Limpeza Final
- O texto resultante não deve conter múltiplas quebras de linha inúteis (`\n\n\n`) ou espaços duplos. O chunk deve ser condensado para maximizar os tokens úteis passados para a OpenAI/provedor de embeddings.