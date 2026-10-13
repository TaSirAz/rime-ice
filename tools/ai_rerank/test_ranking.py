import unittest
from ranking import comparable_indices, conservative_order, split_shared_prefix
from worker import validate_request


class RankingTests(unittest.TestCase):
    def test_no_enter_request_is_valid(self):
        self.assertEqual(validate_request({"id": "1", "context": "",
                         "candidates": ["我們達成公事", "我們達成共識"]})[1], "")

    def test_uncommitted_sentence_prefix_conditions_suffix(self):
        self.assertEqual(split_shared_prefix("", ("我們達成公事", "我們達成共識")),
                         ("我們達成", ("公事", "共識")))

    def test_committed_and_composing_prefix_are_combined(self):
        self.assertEqual(split_shared_prefix("今天", ("我們達成公事", "我們達成共識")),
                         ("今天我們達成", ("公事", "共識")))

    def test_no_shared_prefix_still_scores_entire_words(self):
        self.assertEqual(split_shared_prefix("", ("共識", "公式")), ("", ("共識", "公式")))

    def test_identical_words_do_not_produce_empty_suffix(self):
        self.assertEqual(split_shared_prefix("", ("共識", "共識")), ("", ("共識", "共識")))

    def test_small_differences_preserve_every_position(self):
        self.assertEqual(conservative_order([-2.0, -1.9, -1.8], ["公式", "公司", "公事"]),
                         [0, 1, 2])

    def test_clear_winner_promoted_others_stay_in_order(self):
        self.assertEqual(conservative_order([-4, -1, -3], ["公式", "公司", "公事"]), [1, 0, 2])

    def test_ambiguous_best_two_preserve_original(self):
        self.assertEqual(conservative_order([-5, -1, -1.01], ["公式", "公司", "公事"]), [0, 1, 2])

    def test_partial_word_cannot_displace_full_sentence(self):
        self.assertEqual(conservative_order([-5, 0], ["我們達成共識", "我們"]), [0, 1])
        self.assertEqual(comparable_indices(["公式", "公司"], ["0:7", "0:4"]), [0])

    def test_equal_length_different_span_cannot_promote(self):
        self.assertEqual(conservative_order([-5, 0], ["公式", "公司"], ["0:7", "0:4"]), [0, 1])

    def test_late_candidate_cannot_jump_to_first(self):
        self.assertEqual(conservative_order([-4, -4, -4, -4, 0],
                         ["公式", "公司", "公事", "共識", "攻勢"]), [0, 1, 2, 3, 4])

    def test_bad_scores_and_metadata_rejected(self):
        with self.assertRaises(ValueError):
            conservative_order([float("nan"), 1], ["公式", "公司"])
        with self.assertRaises(ValueError):
            comparable_indices(["公式", "公司"], ["0:7"])


if __name__ == "__main__":
    unittest.main()
