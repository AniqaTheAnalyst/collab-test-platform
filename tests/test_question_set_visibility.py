import os
import tempfile
import unittest

from components import session_store as store


class QuestionSetVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        store.DATA_DIR = self.tmp_dir.name
        store.SESSIONS_FILE = os.path.join(self.tmp_dir.name, "sessions.json")
        store.MATERIALS_FILE = os.path.join(self.tmp_dir.name, "materials.json")
        store.QSETS_FILE = os.path.join(self.tmp_dir.name, "question_sets.json")

    def test_save_question_set_is_private_by_default(self):
        qs = store.save_question_set(
            {"title": "Test set", "subject": "Math", "time_limit": 10, "questions": []},
            uploader="alice",
        )
        self.assertFalse(qs.get("is_public", False))

    def test_publish_question_set_makes_it_public(self):
        qs = store.save_question_set(
            {"title": "Test set", "subject": "Math", "time_limit": 10, "questions": []},
            uploader="alice",
        )
        updated = store.publish_question_set(qs["id"])
        self.assertTrue(updated["is_public"])


if __name__ == "__main__":
    unittest.main()
