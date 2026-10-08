import unittest

from backend.app.validators.fidelity import calculate_fidelity


class TestFidelityGuard(unittest.TestCase):

    def test_valid_block_is_accepted(self):
        block = {
            "type": "paragraph",
            "page": 1,
            "bbox": [10, 20, 300, 100],
            "content": "Structura test content",
            "confidence": 0.95,
        }

        result = calculate_fidelity(block)

        self.assertEqual(result["fidelity_score"], 1.0)
        self.assertEqual(result["risk"], "low")
        self.assertEqual(result["action"], "accept")
        self.assertFalse(result["flagged"])
        self.assertEqual(result["issues"], [])

    def test_invalid_bbox_requires_review(self):
        block = {
            "type": "figure",
            "page": 2,
            "bbox": [500, 600, 100, 150],
            "content": {"description": "Test figure"},
            "confidence": 0.90,
        }

        result = calculate_fidelity(block)

        self.assertIn("invalid_bbox_geometry", result["issues"])
        self.assertEqual(result["risk"], "medium")
        self.assertEqual(result["action"], "review")

    def test_invalid_page_requires_review(self):
        block = {
            "type": "paragraph",
            "page": 0,
            "bbox": [10, 20, 300, 100],
            "content": "Test content",
            "confidence": 0.90,
        }

        result = calculate_fidelity(block)

        self.assertIn("invalid_page", result["issues"])
        self.assertEqual(result["action"], "review")

    def test_multiple_severe_failures_escalate(self):
        block = {
            "type": "chart",
            "page": 1,
            "bbox": [10, 20, float("nan"), 100],
            "content": {
                "title": "Revenue",
                "description": "Revenue chart",
            },
            "confidence": 1.5,
        }

        result = calculate_fidelity(block)

        self.assertIn("invalid_bbox_coordinates", result["issues"])
        self.assertIn(
            "invalid_extractor_confidence",
            result["issues"],
        )
        self.assertEqual(result["risk"], "high")
        self.assertEqual(result["action"], "escalate")
        self.assertTrue(result["flagged"])


if __name__ == "__main__":
    unittest.main()