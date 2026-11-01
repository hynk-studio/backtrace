import unittest
from tools.small_model_sft_inputs import causal_example, full_completion_example


class Tokenizer:
    """A boundary fixture, not evidence about the real Gemma tokenizer."""
    pad_token_id = 0
    full = [2, 3, 4, 5, 6, 106, 7]

    def apply_chat_template(self, messages, *, add_generation_prompt, **kwargs):
        return {'input_ids': [2, 3, 4] if add_generation_prompt else list(self.full)}

    def decode(self, tokens, **kwargs):
        return ''.join({5: '{', 6: '}', 7: '\n', 8: 'extra', 106: '<end>'}[t] for t in tokens)


class FullCompletionTests(unittest.TestCase):
    def encode(self, tokenizer=None, **kwargs):
        return full_completion_example(tokenizer or Tokenizer(),
            [{'role': 'user', 'content': 'Return JSON'}], '{}', eos_token_ids=[1, 106, 50], **kwargs)

    def test_all_answer_tokens_and_terminal_are_labels_without_manual_shift(self):
        row = self.encode(padded_tokens=8)
        self.assertEqual(row['input_ids'], [2, 3, 4, 5, 6, 106, 0, 0])
        self.assertEqual(row['labels'], [-100, -100, -100, 5, 6, 106, -100, -100])
        self.assertEqual(row['attention_mask'], [1, 1, 1, 1, 1, 1, 0, 0])
        self.assertEqual(row['completion_tokens'], 3)
        self.assertEqual(row['terminal_token_id'], 106)

    def test_changed_prompt_boundary_is_rejected(self):
        tokenizer = Tokenizer(); tokenizer.full = [2, 3, 8, 5, 6, 106]
        with self.assertRaisesRegex(ValueError, 'generation prefix'):
            self.encode(tokenizer)

    def test_terminal_is_taken_from_template_not_assumed_to_be_106(self):
        tokenizer = Tokenizer(); tokenizer.full = [2, 3, 4, 5, 6, 50]
        self.assertEqual(self.encode(tokenizer)['labels'][-1], 50)

    def test_missing_or_embedded_terminal_and_extra_text_are_rejected(self):
        for suffix in ([5, 6], [5, 106, 6], [5, 6, 106, 8], [5, 6, 106, 106]):
            tokenizer = Tokenizer(); tokenizer.full = [2, 3, 4, *suffix]
            with self.assertRaises(ValueError): self.encode(tokenizer)

    def test_overflow_fails_without_truncating_the_target(self):
        for kwargs in ({'maximum_tokens': 5}, {'padded_tokens': 5}, {'padded_tokens': 3073}):
            with self.assertRaisesRegex(ValueError, 'truncation is forbidden'):
                self.encode(**kwargs)

    def test_prompt_and_padding_are_masked_even_when_pad_equals_terminal(self):
        row = causal_example([2, 3], [5, 106], pad_token_id=106,
                             maximum_tokens=8, padded_tokens=6)
        self.assertEqual(row['labels'], [-100, -100, 5, 106, -100, -100])

    def test_invalid_or_empty_token_sequences_are_rejected(self):
        for prompt, answer in (([], [5]), ([2], []), ([True], [5]), ([2], [-1])):
            with self.assertRaises(ValueError):
                causal_example(prompt, answer, pad_token_id=0, maximum_tokens=8)


if __name__ == '__main__': unittest.main()
