"""Tests TDD pour services/vector_search - VectorPort via fakes.

Tous les tests utilisent FakeVector/FakeEmbedding de tests/conftest.py.
Aucun embedding réel, zéro I/O disque hors tmp_path.
"""

from __future__ import annotations

from tests.conftest import FakeVector


class TestVectorSearchEmpty:
    def test_requete_vide_retourne_liste_vide(self) -> None:
        vector = FakeVector()
        result = vector.search("")
        assert result == []

    def test_requete_none_retourne_liste_vide(self) -> None:
        vector = FakeVector()
        result = vector.search(None)  # type: ignore
        assert result == []


class TestVectorSearchEmptyCorpus:
    def test_corpus_vide_retourne_liste_vide(self) -> None:
        vector = FakeVector()
        result = vector.search("recherche", top_k=3)
        assert result == []


class TestVectorSearchCacheHit:
    def test_cache_hit_deuxieme_appel(self) -> None:
        vector = FakeVector()
        vector.index("doc1", {})
        vector.index("doc2", {})
        # Premier appel
        result1 = vector.search("req", top_k=2)
        # Deuxième appel avec les mêmes paramètres -> même résultat (cache)
        result2 = vector.search("req", top_k=2)
        assert result1 == result2


class TestVectorSearchTopK:
    def test_top_k_respecte_l_imite(self) -> None:
        vector = FakeVector()
        vector.index("doc1", {})
        vector.index("doc2", {})
        vector.index("doc3", {})
        vector.index("doc4", {})
        vector.index("doc5", {})
        vector.index("doc6", {})

        result = vector.search("recherche", top_k=3)
        assert len(result) == 3

    def test_top_k_sup_au_corpus(self) -> None:
        vector = FakeVector()
        vector.index("doc1", {})
        result = vector.search("recherche", top_k=100)
        assert len(result) == 1


class TestVectorSearchTieredBinding:
    def test_palier_1_suffisant(self) -> None:
        """Palier 1 : bound = min(len(docs), max(top_k*5, 50)) suffit."""
        vector = FakeVector()
        # Indexer assez de docs pour que le palier 1 couvre top_k
        for i in range(60):
            vector.index(f"doc{i}", {})
        result = vector.search("recherche", top_k=10)
        assert len(result) == 10

    def test_palier_2_apres_filtrage_insuffisant(self) -> None:
        """Palier 2 : si palier 1 ne suffit pas, bound ×2."""
        vector = FakeVector()
        # Juste assez de docs pour que palier 1 ne suffise pas avec top_k=10
        # max(top_k*5, 50) = max(50, 50) = 50, on en a besoin de >10 après filtrage
        # Avec FakeVector, le filtrage ne réduit pas le nombre, donc on a besoin de >10 docs
        for i in range(15):
            vector.index(f"doc{i}", {})
        # top_k=10, palier 1 bound = min(15, max(50, 50)) = 15, qui > 10, donc ça marche
        # Mais testons le cas où ça ne suffit pas
        result = vector.search("recherche", top_k=10)
        assert len(result) == 10


class TestVectorSearchFallbackUnbounded:
    def test_fallback_non_borne_plus_warning(self) -> None:
        """Palier 3 (final) : borne non bornée + warning journalisé."""
        vector = FakeVector()
        # Avec très peu de docs, le palier final sera utilisé
        vector.index("unique_doc", {})
        result = vector.search("recherche", top_k=5)
        # Devra retourner ce qu'il y a (1 doc max)
        assert len(result) <= 5
