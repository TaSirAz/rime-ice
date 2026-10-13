import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml
import setup_native_grammar as native


class NativeGrammarTests(unittest.TestCase):
    def constants(self, payload):
        return patch.multiple(native, SIZE=len(payload), SHA256=hashlib.sha256(payload).hexdigest())

    def test_verified_download_preserves_ai_and_custom_settings(self):
        payload = b"test-model-data"
        with tempfile.TemporaryDirectory() as directory, self.constants(payload):
            root = Path(directory)
            config = root / "rime_ice.custom.yaml"
            config.write_text("patch:\n  ai_rerank/enabled: true\n  translator/user_dict: rime_ice\n", encoding="utf-8")
            with patch.object(native.urllib.request, "urlopen", return_value=io.BytesIO(payload)) as download:
                native.install(root)
            result = yaml.safe_load(config.read_text())["patch"]
            self.assertTrue(result["ai_rerank/enabled"])
            self.assertEqual(result["translator/user_dict"], "rime_ice")
            self.assertEqual(result["grammar/language"], native.MODEL)
            self.assertEqual(result["translator/max_sentences"], 3)
            self.assertTrue(list(root.glob("*.bak")))
            with patch.object(native.urllib.request, "urlopen") as unnecessary:
                native.install(root)
                unnecessary.assert_not_called()

    def test_bad_download_does_not_change_configuration(self):
        payload = b"correct-model"
        with tempfile.TemporaryDirectory() as directory, self.constants(payload):
            root = Path(directory)
            config = root / "rime_ice.custom.yaml"
            original = "patch:\n  ai_rerank/enabled: true\n"
            config.write_text(original, encoding="utf-8")
            with patch.object(native.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")):
                with self.assertRaises(ValueError):
                    native.install(root)
            self.assertEqual(config.read_text(), original)
            self.assertFalse((root / (native.MODEL + ".gram")).exists())

    def test_existing_other_grammar_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "rime_ice.custom.yaml"
            original = "patch:\n  grammar/language: another-model\n"
            config.write_text(original, encoding="utf-8")
            with patch.object(native.urllib.request, "urlopen") as download:
                with self.assertRaises(ValueError):
                    native.install(root)
                download.assert_not_called()
            self.assertEqual(config.read_text(), original)


if __name__ == "__main__":
    unittest.main()
