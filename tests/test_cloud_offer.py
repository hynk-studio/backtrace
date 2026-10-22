import copy
import unittest
from tools.cloud_offer import inspect_offer
from tools.runpod_control import GPU
from tests.test_runpod_control import T0


class OfferTests(unittest.TestCase):
    def setUp(self):
        self.account = {'myself': {'clientBalance': 9.8508333333, 'currentSpendPerHr': 0,
                                   'isAutoPayEnabled': False}, 'dataCenters': [{'id': 'CA-MTL-3',
            'gpuAvailability': [{'gpuTypeId': GPU, 'available': True, 'stockStatus': 'Low'}]}]}
        self.price = {'gpuTypes': [{'id': GPU, 'memoryInGb': 80, 'secureCloud': True,
            'lowestPrice': {'uninterruptablePrice': 1.79, 'minMemory': 117, 'minVcpu': 31,
                'stockStatus': 'Low', 'supportPublicIp': True, 'availableGpuCounts': [1]}}]}
        self.calls = []

    def read(self, source, variables=None):
        self.calls.append((source, variables))
        return copy.deepcopy(self.account if variables is None else self.price)

    def test_fresh_scoped_quote_uses_reported_hardware_and_prior_spending(self):
        result = inspect_offer(read=self.read, now=lambda: T0)
        self.assertEqual(result['status'], 'QUALIFIED')
        self.assertEqual(result['offer']['vcpus'], 31)
        self.assertEqual(result['offer']['ram_gb'], 117)
        self.assertEqual(result['costs']['maximum_all_in'], '3.608')
        self.assertEqual(result['costs']['spent_before'], '0.1491666667')
        price = self.calls[1][1]['price']
        self.assertEqual((price['secureCloud'], price['gpuCount'], price['dataCenterId']), (True, 1, 'CA-MTL-3'))
        self.assertEqual((price['minMemoryInGb'], price['minVcpuCount'], price['minCudaVersion']), (117, 8, '12.8'))

    def test_auto_pay_or_existing_spend_blocks_without_settings_mutation(self):
        for field, value in (('isAutoPayEnabled', True), ('currentSpendPerHr', 1)):
            with self.subTest(field=field):
                self.setUp(); self.account['myself'][field] = value
                result = inspect_offer(read=self.read, now=lambda: T0)
                self.assertEqual(result['status'], 'ACCOUNT_NOT_QUALIFIED')
                self.assertEqual(len(self.calls), 1)
                self.assertFalse(result['settings_changed'])

    def test_eligible_european_quote_is_checked_before_other_regions(self):
        europe=copy.deepcopy(self.account['dataCenters'][0]);europe['id']='EU-RO-1'
        self.account['dataCenters'].append(europe)
        result=inspect_offer(read=self.read,now=lambda:T0)
        self.assertEqual(result['offer']['region'],'EU-RO-1')
        self.assertEqual(self.calls[1][1]['price']['dataCenterId'],'EU-RO-1')

    def test_european_broad_stock_without_exact_quote_falls_back_to_qualified_region(self):
        europe=copy.deepcopy(self.account['dataCenters'][0]);europe['id']='EU-RO-1'
        self.account['dataCenters'].append(europe)
        def read(source,variables=None):
            value=self.read(source,variables)
            if variables and variables['price']['dataCenterId']=='EU-RO-1':
                value['gpuTypes'][0]['lowestPrice']=None
            return value
        result=inspect_offer(read=read,now=lambda:T0)
        self.assertEqual(result['offer']['region'],'CA-MTL-3')
        self.assertEqual([v['price']['dataCenterId'] for _,v in self.calls if v],
                         ['EU-RO-1','CA-MTL-3'])

    def test_unavailable_region_or_only_multiple_gpu_capacity_is_not_qualified(self):
        self.account['dataCenters'][0]['gpuAvailability'][0]['available'] = False
        self.assertEqual(inspect_offer(read=self.read, now=lambda: T0)['status'], 'NO_QUALIFIED_REGION')
        self.assertEqual(len(self.calls), 2)
        self.setUp(); self.price['gpuTypes'][0]['lowestPrice']['availableGpuCounts'] = [4, 8]
        self.assertEqual(inspect_offer(read=self.read, now=lambda: T0)['status'], 'NO_QUALIFIED_REGION')

    def test_insufficient_reported_ram_cannot_be_replaced_by_requested_floor(self):
        self.price['gpuTypes'][0]['lowestPrice']['minMemory'] = 64
        with self.assertRaisesRegex(ValueError, 'insufficient host'):
            inspect_offer(read=self.read, now=lambda: T0)

    def test_nullable_summaries_use_exact_filtered_stock_not_unfiltered_price(self):
        price = self.price['gpuTypes'][0]['lowestPrice']
        price.update(supportPublicIp=None, availableGpuCounts=None)
        result = inspect_offer(read=self.read, now=lambda: T0)
        self.assertEqual(result['status'], 'QUALIFIED')
        query_input = self.calls[1][1]['price']
        self.assertEqual(query_input['gpuCount'], 1)
        self.assertIs(query_input['supportPublicIp'], True)
        self.assertEqual(query_input['minDisk'], 100)
        price['stockStatus'] = None
        self.assertEqual(inspect_offer(read=self.read, now=lambda: T0)['status'], 'NO_QUALIFIED_REGION')

    def test_explicit_incompatible_summaries_still_block(self):
        for field, value in (('supportPublicIp', False), ('availableGpuCounts', []),
                             ('availableGpuCounts', [4, 8]), ('availableGpuCounts', [True]),
                             ('availableGpuCounts', '1')):
            with self.subTest(field=field, value=value):
                self.setUp()
                self.price['gpuTypes'][0]['lowestPrice'][field] = value
                self.assertEqual(inspect_offer(read=self.read, now=lambda: T0)['status'],
                                 'NO_QUALIFIED_REGION')


if __name__ == '__main__': unittest.main()
