from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from academic_audit.audit_runner import run_document_audit


class AuditRunnerTest(unittest.TestCase):
    def test_heuristic_fallback_writes_teacher_report_and_confidence_zero(self) -> None:
        paragraphs = [
            (
                "Front matter",
                "Asignatura Actividad Alumna Fecha",
            ),
            (
                "Resultados",
                "He seleccionado un método reproducible con métricas de precisión, tiempo y trazabilidad "
                "para comparar resultados. El script conserva salidas raw y permite revisar cada decisión.",
            ),
            (
                "Resultados",
                "La tabla 1 resume las métricas principales y la figura 1 muestra la comparación visual "
                "entre alternativas metodológicas con suficiente detalle para una defensa oral.",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            document = base / "sample.pdf"
            document.write_text("placeholder", encoding="utf-8")
            out_dir = base / "out"

            with patch("academic_audit.audit_runner.read_document_paragraphs", return_value=paragraphs):
                with patch(
                    "academic_audit.audit_runner.run_ollama_review",
                    return_value={
                        "available": False,
                        "model": "qwen2.5",
                        "error": "Ollama no disponible",
                        "confidence_pct": 0,
                        "confidence_label": "no disponible",
                        "confidence_warnings": ["Ollama no disponible"],
                    },
                ):
                    result = run_document_audit(
                        docx=document,
                        out_dir=out_dir,
                        ai_model="qwen2.5",
                    )

            summary = result["summary"]
            written = json.loads((out_dir / "audit_summary.json").read_text(encoding="utf-8"))
            teacher_report = (out_dir / "teacher_report.md").read_text(encoding="utf-8")

            self.assertEqual(summary["audit_mode"], "heuristic_only")
            self.assertEqual(written["ai_model_review"]["confidence_pct"], 0)
            self.assertIn("Informe para profesor", teacher_report)
            self.assertIn("Límites de uso", teacher_report)
            self.assertTrue((out_dir / "dashboard.html").exists())
            self.assertTrue((out_dir / "quality_audit_report.md").exists())


if __name__ == "__main__":
    unittest.main()
