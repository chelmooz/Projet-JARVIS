#!/usr/bin/env python3
"""Test concurrent log writing to verify no data loss (race condition fix)."""

import json
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

from log import LogService

from config.constants import PROJECT_DIR


def test_log_concurrent_no_data_loss():
    """RED: 50 threads appellent log.log() - api.json doit contenir exactement 50 entrées."""
    # Nettoyer le fichier de log existant
    log_path = os.path.join(PROJECT_DIR, "logs", "api.json")
    if os.path.exists(log_path):
        os.remove(log_path)

    service = LogService()
    num_threads = 50
    messages = [f"concurrent_message_{i}" for i in range(num_threads)]

    def write_message(msg):
        service.log("INFO", msg)

    threads = []
    for msg in messages:
        t = threading.Thread(target=write_message, args=(msg,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Vérifier que tous les logs ont été écrits
    assert os.path.exists(log_path), "Fichier de log introuvable après écriture"

    with open(log_path, encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list), f"Expected list, got {type(data)}"
    assert len(data) == num_threads, f"Expected {num_threads} log entries, got {len(data)}"

    # Vérifier que toutes les entrées sont uniques
    unique_messages = {entry["message"] for entry in data}
    assert len(unique_messages) == num_threads, f"Expected {num_threads} unique messages, got {len(unique_messages)}"


if __name__ == "__main__":
    import os

    test_log_concurrent_no_data_loss()
    print("Test passed: concurrent log writes have no data loss")
