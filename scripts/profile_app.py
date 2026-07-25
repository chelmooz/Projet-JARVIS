#!/usr/bin/env python3
"""Profile les endpoints FastAPI avec cProfile.

Usage:
    python scripts/profile_app.py [--output profile.prof] [--endpoint /api/status]

Sans argument, profile les 4 endpoints principaux (status, backend, jarvis, metrics)
et sauvegarde dans ``profile_output.prof`` (visualisable avec ``snakeviz``).
"""

import argparse
import cProfile
import pstats
import sys
import time

from fastapi.testclient import TestClient

from controllers.router import app

ENDPOINTS = [
    ("GET /api/status", "get", "/api/status"),
    ("GET /api/backend", "get", "/api/backend"),
    ("GET /api/jarvis", "get", "/api/jarvis"),
    ("GET /api/metrics", "get", "/api/metrics"),
]


def profile_endpoint(client: TestClient, method: str, path: str, iterations: int = 100):
    """Profile un endpoint sur N itérations et retourne les stats."""
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(iterations):
        resp = getattr(client, method)(path)
        assert resp.status_code == 200, f"{method.upper()} {path} → {resp.status_code}"
    profiler.disable()
    return profiler


def main():
    parser = argparse.ArgumentParser(description="Profile les endpoints FastAPI")
    parser.add_argument("--output", default="profile_output.prof", help="Fichier .prof de sortie")
    parser.add_argument("--endpoint", help="Endpoint unique à profiler (ex: /api/status)")
    parser.add_argument("--iterations", type=int, default=100, help="Nombre d'itérations (défaut: 100)")
    args = parser.parse_args()

    client = TestClient(app)

    if args.endpoint:
        method = "get"
        label = f"GET {args.endpoint}"
        print(f"Profiling {label} ({args.iterations} itérations)...")
        profiler = profile_endpoint(client, method, args.endpoint, args.iterations)
        profiler.dump_stats(args.output)
        p = pstats.Stats(profiler)
        p.sort_stats("cumtime").print_stats(20)
        print(f"Profil sauvegardé : {args.output}")
        return

    # Profilage multiple
    all_stats = {}
    for label, method, path in ENDPOINTS:
        print(f"Profiling {label} ({args.iterations} itérations)...")
        profiler = profile_endpoint(client, method, path, args.iterations)
        profiler.dump_stats(f"profile_{path.replace('/', '_')}.prof")
        all_stats[label] = profiler

    print("\nRapport cumulé (top 10 par cumtime):")
    for label, profiler in all_stats.items():
        p = pstats.Stats(profiler)
        p.sort_stats("cumtime").print_stats(10)

    print(f"\nProfils sauvegardés : profile_*.prof")
    print("Visualiser avec : snakeviz profile_*.prof")


if __name__ == "__main__":
    main()
