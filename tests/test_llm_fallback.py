import os
import unittest
from unittest.mock import patch

from components.llm_chain import generate_questions, get_llm


class LLMFallbackTests(unittest.TestCase):
    def test_generate_questions_without_api_keys_uses_fallback(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "GOOGLE_API_KEY": "",
            "NVIDIA_API_KEY": "",
        }, clear=False):
            qs = generate_questions(
                material="Photosynthesis is how plants turn light into energy.",
                num_questions=2,
                question_type="mcq",
                time_limit=15,
                provider="NVIDIA",
                model="meta/llama-3.1-8b-instruct",
            )

            self.assertIsInstance(qs, dict)
            self.assertIn("questions", qs)
            self.assertGreaterEqual(len(qs["questions"]), 1)
            self.assertEqual(qs["time_limit"], 15)

    def test_get_llm_uses_nvidia_key(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nv-test-key"}, clear=False):
            llm = get_llm("NVIDIA", "meta/llama-3.1-8b-instruct")
            self.assertIsNotNone(llm)


if __name__ == "__main__":
    unittest.main()
