import tempfile
import unittest
from pathlib import Path
import yaml
from worker import stable_order, validate_request
from setup import configure


class PrototypeTests(unittest.TestCase):
    def test_ties_preserve_rime_order(self):
        self.assertEqual(stable_order([1.0, 2.0, 2.0]), [1, 2, 0])

    def test_invalid_model_scores_rejected(self):
        with self.assertRaises(ValueError):
            stable_order([float("nan"), 1.0])

    def test_malformed_request_rejected(self):
        with self.assertRaises(ValueError):
            validate_request({"id": "1", "context": "前文", "candidates": [""]})

    def test_valid_request(self):
        self.assertEqual(validate_request({"id": "1", "context": "代入", "candidates": ["公式", "公司"]}),
                         ("1", "代入", ("公式", "公司")))

    def test_opt_in_idempotent_and_sync_preserves_device_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user = root / "Rime"
            user.mkdir()
            (user / "rime_ice.custom.yaml").write_text('patch:\n  "translator/user_dict": rime_ice\n', encoding="utf-8")
            (user / "installation.yaml").write_text("installation_id: computer-a\n", encoding="utf-8")
            configure(user, enable=True, sync_dir=root / "cloud")
            configure(user, enable=True)
            config = yaml.safe_load((user / "rime_ice.custom.yaml").read_text())
            self.assertEqual(config["patch"]["translator/user_dict"], "rime_ice")
            self.assertEqual(len(config["patch"]["engine/filters/+"]), 1)
            self.assertEqual(yaml.safe_load((user / "installation.yaml").read_text())["installation_id"], "computer-a")
            configure(user, disable=True)
            self.assertFalse(yaml.safe_load((user / "rime_ice.custom.yaml").read_text())["patch"]["ai_rerank/enabled"])
            self.assertTrue(list(user.glob("*.bak")))

    def test_reject_sync_inside_live_database(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                configure(Path(directory), sync_dir=Path(directory) / "sync")


if __name__ == "__main__":
    unittest.main()
