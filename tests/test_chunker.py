from app.services.chunker import ChunkingService


def test_chunker_small_text():
    chunker = ChunkingService(chunk_size=800, chunk_overlap=120)
    text = "Este é um texto curto para testes."
    chunks = chunker.create_chunks(text)

    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["chunk_text"] == text


def test_chunker_long_text():
    chunker = ChunkingService(chunk_size=100, chunk_overlap=20)
    long_text = "Palavra " * 100
    chunks = chunker.create_chunks(long_text)

    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c["chunk_index"] == idx
        assert len(c["chunk_text"]) <= 120
