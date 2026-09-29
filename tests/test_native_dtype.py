"""Synthetic driver text and injected hardware predicates; no CUDA execution."""
import ast
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from tools.native_dtype import (AFTER, BEFORE, EXTRA_ARGS_LINE, NO_CUSTOM_AR,
                                native_dtype_source, no_custom_ar_source, serving_sources)


SOURCE = """config = dict(
    dtype='bfloat16' if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else 'auto',
    tensor_parallel_size=2, max_model_len=32768, gpu_memory_utilization=0.90,
    tool_call_parser='gemma4', reasoning_parser='gemma4', enable_lora=True,
    max_loras=8, max_lora_rank=128, startup_timeout=60 * 20,
)
"""


class NativeDtypeTests(unittest.TestCase):
    def test_no_custom_ar_adds_only_supported_extra_args(self):
        fixture = SOURCE.replace('max_lora_rank=128, startup_timeout=60 * 20,',
                                 'max_lora_rank=128,\n    startup_timeout=60 * 20,')
        native = native_dtype_source(fixture)
        changed = no_custom_ar_source(native)
        self.assertEqual(changed.replace(EXTRA_ARGS_LINE, '', 1), native)
        self.assertEqual(changed.count(NO_CUSTOM_AR), 1)
        for enabled, expected in ((True, 'bfloat16'), (False, 'auto')):
            scope = {'torch': SimpleNamespace(cuda=SimpleNamespace(
                is_available=lambda: True, is_bf16_supported=lambda **_: enabled))}
            exec(changed, scope)
            self.assertEqual(scope['config']['extra_args'], [NO_CUSTOM_AR])
            self.assertEqual(scope['config']['dtype'], expected)

    def test_no_custom_ar_rejects_drift_and_repeated_application(self):
        native = AFTER + '\n    startup_timeout=60 * 20,\n'
        for source in (native.replace(AFTER, BEFORE), native + native,
                       native.replace('60 * 20', '60 * 30'),
                       'extra_args=[]\n' + native, no_custom_ar_source(native)):
            with self.assertRaisesRegex(ValueError, 'unchanged native-dtype'):
                no_custom_ar_source(source)

    def test_native_non_native_and_no_cuda_branches(self):
        for available, native, expected in ((True, True, 'bfloat16'),
                                             (True, False, 'auto'),
                                             (False, False, 'auto')):
            with self.subTest(available=available, native=native):
                check = Mock(return_value=native)
                torch = SimpleNamespace(cuda=SimpleNamespace(
                    is_available=lambda: available, is_bf16_supported=check))
                scope = {'torch': torch}
                exec(native_dtype_source(SOURCE), scope)
                self.assertEqual(scope['config']['dtype'], expected)
                if available:
                    check.assert_called_once_with(including_emulation=False)
                else:
                    check.assert_not_called()

    def test_exact_source_delta_preserves_all_other_settings(self):
        changed = native_dtype_source(SOURCE)
        self.assertEqual(changed.replace(AFTER, BEFORE, 1), SOURCE)
        original = ast.parse(SOURCE).body[0].value
        modified = ast.parse(changed).body[0].value
        self.assertEqual([ast.dump(k) for k in original.keywords if k.arg != 'dtype'],
                         [ast.dump(k) for k in modified.keywords if k.arg != 'dtype'])
        for source in ('', SOURCE + SOURCE, changed):
            with self.assertRaises(ValueError):
                native_dtype_source(source)

    def test_unpinned_notebook_is_rejected_before_source_use(self):
        with self.assertRaisesRegex(ValueError, 'notebook hash mismatch'):
            serving_sources(b'{"cells": []}')


if __name__ == '__main__':
    unittest.main()
