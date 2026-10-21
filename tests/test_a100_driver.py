"""Injected hardware/config tests. No CUDA, official wheels or provider access."""
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import a100_driver as driver

SMI = 'NVIDIA A100-PCIE-80GB, GPU-authored-fixture, 81920, 570.124.06, Disabled\n'


def cuda():
    return SimpleNamespace(is_available=lambda: True, device_count=lambda: 1,
                           get_device_capability=lambda _: (8, 0),
                           is_bf16_supported=Mock(return_value=True))


class A100DriverTests(unittest.TestCase):
    def test_native_predicate_and_observed_identity(self):
        device = cuda()
        observed = driver.qualify_hardware(SMI, device, toolkit_version='12.8.1')
        device.is_bf16_supported.assert_called_once_with(including_emulation=False)
        self.assertEqual(observed['tp'], 1)
        self.assertEqual(observed['sm'], [8, 0])

    def test_rejects_other_hardware_mig_and_old_driver(self):
        for text in (SMI * 2, SMI.replace('A100-PCIE-80GB', 'A100-SXM4-80GB'),
                     SMI.replace('A100-PCIE-80GB', 'Tesla T4'),
                     SMI.replace('Disabled', 'Enabled'), SMI.replace('Disabled', '[N/A]'),
                     SMI.replace('GPU-', 'MIG-'), SMI.replace('81920', '40960'),
                     SMI.replace('570.124.06', '570.124.05')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                driver.qualify_hardware(text, cuda(), toolkit_version='12.8.1')

    def test_no_emulation_tp_or_toolkit_fallback(self):
        for field, result in (('is_available', False), ('device_count', 2),
                              ('get_device_capability', (9, 0)),
                              ('is_bf16_supported', False)):
            device = cuda()
            setattr(device, field, Mock(return_value=result))
            with self.subTest(field=field), self.assertRaises(ValueError):
                driver.qualify_hardware(SMI, device, toolkit_version='12.8.1')
        for toolkit in ('12.8', '12.8.0', 'unknown'):
            with self.subTest(toolkit=toolkit), self.assertRaises(ValueError):
                driver.qualify_hardware(SMI, cuda(), toolkit_version=toolkit)

    def test_setup_and_startup_share_allocation_clock(self):
        self.assertEqual(driver.startup_deadline(100, now=200), 1400)
        self.assertEqual(driver.startup_deadline(100, now=1299), 2499)
        for allocated, now in ((100, 1300), (100, 99), (float('nan'), 200),
                               (100, float('inf'))):
            with self.assertRaises(ValueError):
                driver.startup_deadline(allocated, now=now)

    def test_runtime_component_keeps_update_one_floor_and_all_hardware_gates(self):
        observed = driver.qualify_hardware(SMI, cuda(), runtime_version='12.8.90')
        self.assertEqual(observed['runtime'], '12.8.90')
        self.assertNotIn('toolkit', observed)
        for value in ('12.8', '12.8.57', 'unknown'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                driver.qualify_hardware(SMI, cuda(), runtime_version=value)
        for text in (SMI.replace('Disabled', 'Enabled'), SMI.replace('570.124.06', '570.124.05')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                driver.qualify_hardware(text, cuda(), runtime_version='12.8.90')
        with self.assertRaises(ValueError):
            driver.qualify_hardware(SMI, cuda())
        with self.assertRaises(ValueError):
            driver.qualify_hardware(SMI, cuda(), toolkit_version='12.8.1', runtime_version='12.8.90')

    def test_rejects_unpinned_source_before_config_execution(self):
        constructor = Mock()
        with self.assertRaisesRegex(ValueError, 'notebook hash mismatch'):
            driver.build_config(b'{"cells": []}', constructor, SimpleNamespace(cuda=cuda()))
        constructor.assert_not_called()

    def test_actual_guard_wraps_once_without_starting_model(self):
        # Only the config construction is substituted; exercise the real guard
        # and verify one-start enforcement at its actual lifecycle boundary.
        class Payload:
            def __init__(self, config, *, adapter_manifest):
                self.config = config
                self.process = None
            def start(self):
                return self

        config = SimpleNamespace(startup_timeout=1200)
        with patch.object(driver, 'build_config', return_value=config):
            server, observed = driver.make_server(
                b'injected-config', SimpleNamespace(cuda=cuda()), SMI,
                toolkit_version='12.8.1', allocation_requested_monotonic=time.monotonic(),
                adapter_manifest=SimpleNamespace(adapters={}),
                server_type=Payload, config_type=object, error_type=RuntimeError)
        self.assertIsNone(server.process)
        self.assertIs(server.start(), server)
        with self.assertRaisesRegex(RuntimeError, 'one server start'):
            server.start()
        self.assertEqual(observed['native_bf16'], True)

    def test_gates_precede_wrapper_construction(self):
        constructor = Mock()
        with self.assertRaises(ValueError):
            driver.make_server(
                b'invalid', SimpleNamespace(cuda=cuda()), SMI,
                toolkit_version='12.8.1', allocation_requested_monotonic=time.monotonic(),
                adapter_manifest=SimpleNamespace(adapters={'unexpected': object()}),
                server_type=constructor, config_type=object, error_type=RuntimeError)
        constructor.assert_not_called()
