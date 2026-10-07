import unittest

from backend.app.services.fidelity import determine_escalation


class TestSelectiveEscalation(unittest.TestCase):

    def test_accepted_block_requires_no_retry(self):
        block = {"type": "chart"}

        fidelity = {
            "action": "accept",
            "issues": [],
        }

        result = determine_escalation(block, fidelity)

        self.assertEqual(result["decision"], "accept")
        self.assertFalse(result["retry_required"])
        self.assertEqual(result["strategy"], "none")

    def test_visual_issue_routes_to_visual_reextract(self):
        block = {"type": "chart"}

        fidelity = {
            "action": "review",
            "issues": ["missing_chart_title"],
        }

        result = determine_escalation(block, fidelity)

        self.assertTrue(result["retry_required"])
        self.assertEqual(
            result["strategy"],
            "visual_reextract",
        )

    def test_equation_issue_routes_to_equation_reextract(self):
        block = {"type": "equation"}

        fidelity = {
            "action": "review",
            "issues": ["missing_latex"],
        }

        result = determine_escalation(block, fidelity)

        self.assertTrue(result["retry_required"])
        self.assertEqual(
            result["strategy"],
            "equation_reextract",
        )

    def test_provenance_issue_routes_to_reconstruction(self):
        block = {"type": "figure"}

        fidelity = {
            "action": "review",
            "issues": ["invalid_bbox_geometry"],
        }

        result = determine_escalation(block, fidelity)

        self.assertEqual(
            result["strategy"],
            "provenance_reconstruct",
        )

    def test_low_confidence_routes_to_stronger_extractor(self):
        block = {"type": "paragraph"}

        fidelity = {
            "action": "review",
            "issues": ["low_extractor_confidence"],
        }

        result = determine_escalation(block, fidelity)

        self.assertEqual(
            result["strategy"],
            "stronger_extractor",
        )

    def test_unknown_failure_uses_specialist_fallback(self):
        block = {"type": "table"}

        fidelity = {
            "action": "escalate",
            "issues": ["unknown_failure"],
        }

        result = determine_escalation(block, fidelity)

        self.assertTrue(result["retry_required"])
        self.assertEqual(
            result["strategy"],
            "specialist_fallback",
        )


if __name__ == "__main__":
    unittest.main()