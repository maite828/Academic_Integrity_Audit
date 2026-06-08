from __future__ import annotations

import unittest

from academic_audit.ai.ollama_review import normalize_review


class OllamaReviewTest(unittest.TestCase):
    def test_placeholder_verdict_is_removed_and_confidence_drops(self) -> None:
        review = normalize_review(
            {
                "ai_usage_risk_pct": 57,
                "plagiarism_risk_pct": 0,
                "quality_score_pct": 62,
                "overall_verdict": "texto breve",
                "ai_risk_reasons": ["estilo compatible con uso intensivo de IA"],
                "plagiarism_risk_reasons": [],
                "quality_recommendations": ["mejorar detalle", "refinar resultados"],
                "teacher_questions": [
                    "¿Cómo se justifica la elección del método frente a Otsu en términos de robustez?"
                ],
            },
            model="qwen2.5",
            raw_response="{}",
        )

        self.assertTrue(review["available"])
        self.assertEqual(review["overall_verdict"], "")
        self.assertLess(review["confidence_pct"], 60)
        self.assertIn("el modelo no produjo un veredicto textual util", review["confidence_warnings"])

    def test_invalid_metrics_make_review_unavailable(self) -> None:
        review = normalize_review(
            {"response_0": {"content": "bad shape"}},
            model="mistral",
            raw_response='{"response_0": {"content": "bad shape"}}',
        )

        self.assertFalse(review["available"])
        self.assertIn("metricas obligatorias", review["error"])


if __name__ == "__main__":
    unittest.main()
