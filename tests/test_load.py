"""TDD — Tests de charge légers (M23e).

Valide la sûreté concurrente des services sur disque (lock) sans dépendre
d'Ollama : écritures concurrentes de messages + recherches concurrentes.
Borné (threads × opérations) pour rester rapide et déterministe en CI.
"""
import threading

import services.conversation as conversation
from services.sanitize import clean_text


def test_concurrent_add_message_no_loss(monkeypatch, tmp_path):
    svc = conversation.ConversationService(storage_dir=str(tmp_path))
    cid = "loadconv"
    n_threads = 8
    per_thread = 25
    total = n_threads * per_thread

    def worker(tid):
        for i in range(per_thread):
            svc.add_message(cid, "user", f"t{tid}-{i}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    conv = svc.get_conversation(cid)
    # Tous les messages doivent être présents (lock thread-safe)
    assert len(conv["messages"]) == total


def test_concurrent_clean_text_is_safe():
    n_threads = 12
    per_thread = 100
    counter = {"n": 0}
    lock = threading.Lock()

    def worker():
        for _ in range(per_thread):
            out = clean_text("x" * 50)
            if out == "x" * 50:
                with lock:
                    counter["n"] += 1

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter["n"] == n_threads * per_thread
