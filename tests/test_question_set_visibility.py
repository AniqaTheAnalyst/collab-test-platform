import unittest
from components import supabase_store as store


class QuestionSetVisibilityTests(unittest.TestCase):

    def setUp(self):
        """Save IDs created during tests so we can clean up after."""
        self.created_ids = []

    def tearDown(self):
        """Delete any question sets created during the test."""
        for qid in self.created_ids:
            try:
                store._client.table("question_sets").delete().eq("id", qid).execute()
            except Exception:
                pass

    def test_save_question_set_is_private_by_default(self):
        qs = store.save_question_set(
            {"title": "Test set", "subject": "Math", "time_limit": 10, "questions": []},
            uploader="alice",
        )
        self.created_ids.append(qs["id"])
        self.assertFalse(qs.get("is_public", False))

    def test_publish_question_set_makes_it_public(self):
        qs = store.save_question_set(
            {"title": "Test set", "subject": "Math", "time_limit": 10, "questions": []},
            uploader="alice",
        )
        self.created_ids.append(qs["id"])
        updated = store.publish_question_set(qs["id"])
        self.assertTrue(updated["is_public"])


if __name__ == "__main__":
    unittest.main()