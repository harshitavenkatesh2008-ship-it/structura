"""Tests for the SAFE router (backend/app/services/router.py)."""

import copy
import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.app.services.router import (  # noqa: E402
    MATH_ENGINE,
    NATIVE_PDF,
    OCR,
    REASON_CHART_OR_FIGURE,
    REASON_CLEAN_NATIVE_TEXT,
    REASON_EQUATION,
    REASON_FALLBACK_NATIVE_TEXT,
    REASON_FALLBACK_OCR,
    REASON_SCANNED_OR_INSUFFICIENT_TEXT,
    REASON_TABLE,
    ROUTES,
    SUPPORTED_BLOCK_TYPES,
    TABLE_ENGINE,
    VISION_ENGINE,
    RegionEvidence,
    route_region,
    evidence_from_block,
)

CLEAN_NATIVE = dict(
    native_text_available=True,
    insufficient_native_text=False,
    scanned_or_image_only=False,
)


def route(**kwargs):
    return route_region(RegionEvidence(**kwargs))


class SingleRouteTests(unittest.TestCase):
    def test_table_detected(self):
        d = route(table_detected=True)
        self.assertEqual(d.route, TABLE_ENGINE)
        self.assertEqual(d.reason_code, REASON_TABLE)
        self.assertFalse(d.is_fallback)

    def test_equation_detected(self):
        d = route(equation_detected=True)
        self.assertEqual(d.route, MATH_ENGINE)
        self.assertEqual(d.reason_code, REASON_EQUATION)

    def test_chart_or_figure_detected(self):
        d = route(chart_or_figure_detected=True)
        self.assertEqual(d.route, VISION_ENGINE)
        self.assertEqual(d.reason_code, REASON_CHART_OR_FIGURE)

    def test_scanned_routes_to_ocr(self):
        d = route(scanned_or_image_only=True)
        self.assertEqual(d.route, OCR)
        self.assertEqual(d.reason_code, REASON_SCANNED_OR_INSUFFICIENT_TEXT)
        self.assertFalse(d.is_fallback)

    def test_insufficient_native_text_routes_to_ocr(self):
        d = route(native_text_available=True, insufficient_native_text=True)
        self.assertEqual(d.route, OCR)

    def test_clean_native_low_complexity(self):
        d = route(low_complexity=True, block_type="paragraph", **CLEAN_NATIVE)
        self.assertEqual(d.route, NATIVE_PDF)
        self.assertEqual(d.reason_code, REASON_CLEAN_NATIVE_TEXT)
        self.assertFalse(d.is_fallback)

    def test_block_types_as_evidence(self):
        expected = {
            "table": TABLE_ENGINE,
            "equation": MATH_ENGINE,
            "chart": VISION_ENGINE,
            "figure": VISION_ENGINE,
            "image": VISION_ENGINE,
        }
        for block_type, expected_route in expected.items():
            with self.subTest(block_type=block_type):
                self.assertEqual(route(block_type=block_type).route, expected_route)

    def test_text_block_types_add_no_specialised_evidence(self):
        for block_type in ("heading", "paragraph", "list"):
            with self.subTest(block_type=block_type):
                d = route(block_type=block_type, low_complexity=True, **CLEAN_NATIVE)
                self.assertEqual(d.route, NATIVE_PDF)
                self.assertEqual(d.metadata["candidate_routes"], [NATIVE_PDF])


class PrecedenceTests(unittest.TestCase):
    def test_scanned_table_routes_to_table_engine(self):
        d = route(table_detected=True, scanned_or_image_only=True)
        self.assertEqual(d.route, TABLE_ENGINE)
        self.assertIn("scanned_or_image_only:true", d.signals)
        self.assertEqual(d.metadata["outranked_routes"], [OCR])

    def test_table_beats_equation(self):
        d = route(table_detected=True, equation_detected=True)
        self.assertEqual(d.route, TABLE_ENGINE)
        self.assertEqual(d.metadata["candidate_routes"], [TABLE_ENGINE, MATH_ENGINE])

    def test_equation_beats_chart(self):
        d = route(equation_detected=True, chart_or_figure_detected=True)
        self.assertEqual(d.route, MATH_ENGINE)

    def test_chart_beats_scanned(self):
        d = route(chart_or_figure_detected=True, scanned_or_image_only=True)
        self.assertEqual(d.route, VISION_ENGINE)

    def test_scanned_beats_clean_native_text(self):
        d = route(
            native_text_available=True,
            scanned_or_image_only=True,
            low_complexity=True,
        )
        self.assertEqual(d.route, OCR)

    def test_all_indicators_select_table(self):
        d = route(
            table_detected=True,
            equation_detected=True,
            chart_or_figure_detected=True,
            scanned_or_image_only=True,
        )
        self.assertEqual(d.route, TABLE_ENGINE)
        self.assertEqual(
            d.metadata["candidate_routes"],
            [TABLE_ENGINE, MATH_ENGINE, VISION_ENGINE, OCR],
        )


class FallbackTests(unittest.TestCase):
    def test_native_text_but_complex_layout_falls_back_to_native(self):
        d = route(low_complexity=False, **CLEAN_NATIVE)
        self.assertEqual(d.route, NATIVE_PDF)
        self.assertTrue(d.is_fallback)
        self.assertEqual(d.reason_code, REASON_FALLBACK_NATIVE_TEXT)
        self.assertIn("Fallback", d.reason)

    def test_native_text_complexity_unknown_falls_back_to_native(self):
        d = route(**CLEAN_NATIVE)
        self.assertEqual(d.route, NATIVE_PDF)
        self.assertTrue(d.is_fallback)
        self.assertIn("low_complexity", d.metadata["missing_evidence"])

    def test_no_native_text_falls_back_to_ocr(self):
        d = route(native_text_available=False)
        self.assertEqual(d.route, OCR)
        self.assertTrue(d.is_fallback)
        self.assertEqual(d.reason_code, REASON_FALLBACK_OCR)

    def test_no_evidence_falls_back_to_ocr(self):
        d = route()
        self.assertEqual(d.route, OCR)
        self.assertTrue(d.is_fallback)
        self.assertEqual(d.metadata["candidate_routes"], [])

    def test_missing_evidence_is_not_treated_as_false(self):
        # native_text_available not provided: native text is not assumed usable.
        d = route(low_complexity=True)
        self.assertEqual(d.route, OCR)
        self.assertTrue(d.is_fallback)
        self.assertIn("native_text_available", d.metadata["missing_evidence"])

    def test_decisions_carry_no_confidence(self):
        for d in (route(), route(table_detected=True), route(**CLEAN_NATIVE)):
            as_dict = d.to_dict()
            self.assertNotIn("confidence", as_dict)
            self.assertNotIn("confidence", as_dict["metadata"])
            self.assertNotIn("confidence", as_dict["complexity"])


class TelemetryOnlyTests(unittest.TestCase):
    def test_raw_signals_do_not_change_route(self):
        base = dict(low_complexity=True, **CLEAN_NATIVE)
        plain = route(**base)
        extreme = route(
            raw_signals={"text_density": 0.0, "column_count": 12, "table_score": 0.99},
            **base,
        )
        self.assertEqual(plain.route, extreme.route)
        self.assertEqual(plain.reason_code, extreme.reason_code)
        self.assertEqual(extreme.complexity["raw_signals"]["column_count"], 12)
        self.assertEqual(extreme.metadata["raw_signals"]["text_density"], 0.0)

    def test_prior_risk_does_not_change_route(self):
        base = dict(low_complexity=True, **CLEAN_NATIVE)
        for level in ("low", "medium", "high"):
            with self.subTest(level=level):
                d = route(prior_risk_level=level, prior_risk_signals=("x",), **base)
                self.assertEqual(d.route, NATIVE_PDF)
                self.assertFalse(d.is_fallback)
                self.assertIn(f"prior_risk_level:{level}", d.signals)
                self.assertEqual(d.metadata["prior_risk"]["level"], level)

    def test_text_heavy_does_not_change_route(self):
        for heavy in (True, False, None):
            with self.subTest(text_heavy=heavy):
                d = route(text_heavy=heavy, chart_or_figure_detected=True)
                self.assertEqual(d.route, VISION_ENGINE)
                self.assertEqual(d.complexity["text_heavy"], heavy)

    def test_conflicting_evidence_is_recorded(self):
        d = route(block_type="table", table_detected=False)
        self.assertEqual(d.route, TABLE_ENGINE)
        self.assertEqual(
            d.metadata["conflicting_evidence"],
            ["block_type:table vs table_detected:false"],
        )


class ValidationTests(unittest.TestCase):
    def test_unknown_block_type_raises(self):
        with self.assertRaises(ValueError):
            RegionEvidence(block_type="sidebar")

    def test_unknown_risk_level_raises(self):
        with self.assertRaises(ValueError):
            RegionEvidence(prior_risk_level="critical")

    def test_non_boolean_evidence_raises(self):
        with self.assertRaises(TypeError):
            RegionEvidence(table_detected=1)
        with self.assertRaises(TypeError):
            RegionEvidence(scanned_or_image_only="yes")

    def test_route_region_requires_evidence(self):
        with self.assertRaises(TypeError):
            route_region({"table_detected": True})


class DeterminismTests(unittest.TestCase):
    def test_same_input_same_output(self):
        kwargs = dict(
            region_id="r1",
            page=2,
            bbox=[0.1, 0.2, 0.9, 0.3],
            table_detected=True,
            scanned_or_image_only=True,
            prior_risk_level="high",
            prior_risk_signals=["b", "a"],
            raw_signals={"column_count": 3},
        )
        first = route(**kwargs)
        for _ in range(20):
            self.assertEqual(route(**kwargs), first)

    def test_signals_are_sorted(self):
        d = route(table_detected=True, equation_detected=True, block_type="table")
        self.assertEqual(list(d.signals), sorted(d.signals))

    def test_inputs_are_not_mutated(self):
        bbox = [0.1, 0.2, 0.9, 0.3]
        raw = {"column_count": 2}
        risk_signals = ["s1"]
        ev = RegionEvidence(
            bbox=bbox, raw_signals=raw, prior_risk_signals=risk_signals,
            table_detected=True,
        )
        d = route_region(ev)
        d.metadata["raw_signals"]["column_count"] = 99
        d.complexity["raw_signals"]["column_count"] = 99
        self.assertEqual(raw, {"column_count": 2})
        self.assertEqual(bbox, [0.1, 0.2, 0.9, 0.3])
        self.assertEqual(risk_signals, ["s1"])
        # Mutating a returned decision must not leak back into the evidence.
        self.assertEqual(route_region(ev).metadata["raw_signals"], {"column_count": 2})
        self.assertEqual(route_region(ev).complexity["raw_signals"], {"column_count": 2})

    def test_every_decision_uses_a_standard_route(self):
        combos = [
            {},
            {"table_detected": True},
            {"equation_detected": True},
            {"chart_or_figure_detected": True},
            {"scanned_or_image_only": True},
            {"native_text_available": False},
            dict(low_complexity=True, **CLEAN_NATIVE),
            dict(low_complexity=False, **CLEAN_NATIVE),
        ]
        combos += [{"block_type": t} for t in SUPPORTED_BLOCK_TYPES]
        for kwargs in combos:
            with self.subTest(kwargs=kwargs):
                self.assertIn(route(**kwargs).route, ROUTES)


class DocumentGraphFixtureTests(unittest.TestCase):
    def setUp(self):
        path = os.path.join(REPO_ROOT, "tests", "mock_output.json")
        with open(path, encoding="utf-8") as fh:
            self.document = json.load(fh)
        self.block = self.document["pages"][0]["blocks"][0]

    def test_mock_table_block_routes_to_table_engine(self):
        d = route_region(evidence_from_block(self.block))
        self.assertEqual(d.route, TABLE_ENGINE)
        self.assertEqual(d.metadata["region_id"], "block_042")
        self.assertEqual(d.metadata["page"], 31)
        self.assertEqual(d.metadata["bbox"], [0.13, 0.31, 0.87, 0.69])
        self.assertEqual(d.metadata["prior_risk"]["level"], "low")
        self.assertIn("prior_risk_signal:numeric_consistency_pass", d.signals)

    def test_extra_evidence_is_accepted(self):
        d = route_region(evidence_from_block(self.block, scanned_or_image_only=True))
        self.assertEqual(d.route, TABLE_ENGINE)
        self.assertEqual(d.metadata["outranked_routes"], [OCR])

    def test_block_is_not_mutated(self):
        before = copy.deepcopy(self.block)
        route_region(evidence_from_block(self.block))
        self.assertEqual(self.block, before)


if __name__ == "__main__":
    unittest.main()
