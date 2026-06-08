from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from academic_audit.originality.local_similarity import (
    comparability_status,
    find_local_matches_with_scope,
)


class LocalSimilarityTest(unittest.TestCase):
    def test_short_template_text_is_not_comparable(self) -> None:
        comparable, reason = comparability_status(
            "Visión Artificial · Actividad 2 · Filtros espaciales y morfológicos Memoria explicativa · Actividad 2"
        )

        self.assertFalse(comparable)
        self.assertIn(reason, {"texto demasiado corto", "cabecera o linea de plantilla", "metadatos o plantilla"})

    def test_internal_similarity_ignores_short_repeated_headers(self) -> None:
        repeated_header = (
            "Visión Artificial · Actividad 2 · Filtros espaciales y morfológicos "
            "Memoria explicativa · Actividad 2"
        )
        long_a = (
            "El método compara métricas de segmentación, área, perímetro y continuidad para justificar "
            "las decisiones tomadas durante el análisis de grietas con operaciones morfológicas."
        )
        long_b = (
            "La evaluación contrasta resultados cuantitativos y visuales para documentar la estabilidad "
            "del procedimiento y sus limitaciones metodológicas principales."
        )

        result = find_local_matches_with_scope(
            target_docx=Path(__file__),
            corpus_dir=None,
            min_similarity=82,
            target_paragraphs=[
                (1, repeated_header),
                (2, long_a),
                (3, repeated_header),
                (4, long_b),
            ],
        )

        self.assertEqual(result["matches"], [])
        self.assertGreaterEqual(result["scope"]["ignored_paragraphs"], 2)
        self.assertEqual(result["scope"]["relevant_matches"], 0)

    def test_corpus_documents_are_reported(self) -> None:
        target_text = (
            "Este informe describe resultados, métricas y decisiones metodológicas con suficiente "
            "detalle para comparar el procedimiento principal."
        )
        corpus_text = (
            "Este documento de corpus contiene otra explicación con métricas y resultados, pero no "
            "copia literalmente el informe objetivo."
        )

        with tempfile.TemporaryDirectory() as tmp:
            corpus_dir = Path(tmp)
            corpus_doc = corpus_dir / "corpus.pdf"
            corpus_doc.write_text("placeholder", encoding="utf-8")
            with patch(
                "academic_audit.originality.local_similarity.read_document_paragraphs",
                return_value=[("Corpus", corpus_text)],
            ):
                result = find_local_matches_with_scope(
                    target_docx=Path(__file__),
                    corpus_dir=corpus_dir,
                    min_similarity=82,
                    target_paragraphs=[(1, target_text)],
                )

        self.assertGreaterEqual(result["scope"]["corpus_documents"], 1)
        self.assertTrue(result["scope"]["corpus_enabled"])
        self.assertTrue(result["scope"]["corpus_document_names"])


if __name__ == "__main__":
    unittest.main()
