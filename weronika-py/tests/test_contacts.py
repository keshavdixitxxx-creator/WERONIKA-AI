import unittest

from weronika_agent.contacts import rank_candidates
from weronika_agent.models import VisibleContact


class ContactMatchingTests(unittest.TestCase):
    def test_exact_match_is_ranked_first(self):
        candidates = rank_candidates("boss", ["Boss Office", "Boss"])
        self.assertEqual(candidates[0].display_name, "Boss")
        self.assertTrue(candidates[0].exact)
        self.assertGreaterEqual(len(candidates), 2)

    def test_similar_names_are_retained_for_disambiguation(self):
        candidates = rank_candidates("alex", ["Alex Morgan", "Alex M.", "Alexander"])
        self.assertGreaterEqual(len(candidates), 2)
        self.assertFalse(any(candidate.exact for candidate in candidates))

    def test_same_display_name_is_not_deduplicated(self):
        contacts = [
            VisibleContact("0:0", "Alex"),
            VisibleContact("0:1", "Alex"),
        ]
        candidates = rank_candidates("Alex", contacts)
        self.assertEqual(len(candidates), 2)
        self.assertNotEqual(candidates[0].source_id, candidates[1].source_id)
        self.assertTrue(all(candidate.context for candidate in candidates))

    def test_very_short_query_does_not_fuzzy_match(self):
        self.assertEqual(rank_candidates("Al", ["Alex", "Alice"]), [])


if __name__ == "__main__":
    unittest.main()
