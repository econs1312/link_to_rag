# Regras de Processamento de Ficheiros, OCR e Validação

O sistema permite o upload direto de ficheiros. O processamento destes deve ser seguro, eficiente e resiliente a ficheiros corrompidos ou maliciosos.

## 1. Validação de Mime-Type Real
- **Regra Estrita:** Nunca confie na extensão do ficheiro enviada pelo utilizador.
- Utilize a biblioteca `python-magic` para verificar a assinatura (Magic Bytes) real do ficheiro carregado antes de o processar. Rejeite ficheiros executáveis disfarçados de PDFs/Textos.

## 2. Leitura de PDFs (PyMuPDF)
- Utilize **apenas** `pymupdf` (módulo `fitz`) para abrir e extrair texto de PDFs. Não utilize bibliotecas obsoletas como `PyPDF2`.
- O `pymupdf` é mais rápido e preserva melhor a estrutura de parágrafos.

## 3. OCR como Fallback (PyTesseract)
- Se um PDF for lido com sucesso, mas o texto extraído for muito curto (ex: < 100 caracteres por página), assuma que é um PDF baseado em imagens (escaneado).
- Nesse cenário, aplique uma estratégia de fallback: converta as páginas do PDF em imagens (utilizando as ferramentas do `pymupdf` ou `Pillow`) e extraia o texto com `pytesseract`.

## 4. Gestão de Memória e Ficheiros Temporários
- Ficheiros carregados devem ser guardados em memória ou em diretórios temporários (`tempfile`).
- **Regra Estrita:** Certifique-se SEMPRE de fechar os handles dos ficheiros e limpar/apagar os ficheiros temporários do disco após a extração, utilizando blocos `try...finally` para evitar fugas de memória e preenchimento indevido do disco.