from services.chunker import chunk_text


def test_empty_and_whitespace() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n  \n ") == []


def test_single_paragraph_under_size() -> None:
    chunks = chunk_text("Hello world.", chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Hello world."
    assert chunks[0]["metadata"]["chunk_index"] == 0
    assert chunks[0]["metadata"]["total_chunks"] == 1
    assert chunks[0]["metadata"]["doc_id"] == ""


def test_doc_id_propagated() -> None:
    chunks = chunk_text("Hi.", chunk_size=500, doc_id="doc42")
    assert chunks[0]["metadata"]["doc_id"] == "doc42"


def test_long_text_multiple_chunks_and_metadata() -> None:
    para = "Sentence one. Sentence two. " * 40
    text = para + "\n\n" + para
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c["metadata"]["chunk_index"] == i
    assert chunks[-1]["metadata"]["chunk_index"] == len(chunks) - 1
    assert chunks[0]["metadata"]["total_chunks"] == len(chunks)


def test_overlap_present() -> None:
    long_sentence = "x" * 250
    chunks = chunk_text(long_sentence, chunk_size=100, overlap=10)
    assert len(chunks) >= 2
    assert chunks[1]["text"].startswith(chunks[0]["text"][-10:])


def test_unicode_multibyte() -> None:
    text = "café ☕ résumé 日本語"
    chunks = chunk_text(text, chunk_size=500)
    assert chunks[0]["text"] == text
