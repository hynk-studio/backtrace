import copy
import json
import unittest

from tools import research_assets as assets, research_comparison as comparison
from test_research_comparison import metadata_fixture, pinned_metadata


class AssetProjectionTests(unittest.TestCase):
    def setUp(self):
        data, protocol = metadata_fixture(comparison.load_protocol(), repository_count=3, tasks_per_repo=4)
        rows = [json.loads(line) for line in data.splitlines()]
        for row in rows:
            row.pop('hints_text')
            row['repo'] = row['repo'].replace('example/', 'Example/')
        self.data, self.protocol = pinned_metadata(protocol, rows)
        self.selection = comparison.select_tasks(self.data, self.protocol)

    def test_reference_fields_and_unselected_tasks_are_not_projected(self):
        result = assets.projections(self.data, self.selection, self.protocol)
        self.assertEqual(len(result), 6)
        self.assertEqual(set(result), {r['instance_id'] for r in self.selection['primary']})
        for task in result.values():
            self.assertEqual(set(task), set(assets.FIELDS))
            self.assertEqual(task['hints_text'], '')
        self.assertNotIn('EVALUATOR_', json.dumps(result))
        self.assertNotIn('PRIVATE_TEST_NAME_SENTINEL', json.dumps(result))

    def test_changed_selection_or_original_metadata_is_rejected(self):
        changed = copy.deepcopy(self.selection); changed['primary'][0]['base_commit'] = 'a' * 40
        with self.assertRaises(ValueError): assets.projections(self.data, changed, self.protocol)
        with self.assertRaises(ValueError): assets.projections(self.data + b'\n', self.selection, self.protocol)

    def test_asset_identity_uses_selected_commit_and_task(self):
        row = self.selection['primary'][0]
        paths = assets.asset_paths(row)
        self.assertEqual(paths[0], 'snapshots/' + row['instance_id'] + '.tgz')
        self.assertIn(row['base_commit'], paths[1])
        self.assertIn(row['base_commit'], paths[2])

    def test_paths_cannot_escape_selected_identity(self):
        for key in ('instance_id', 'repo', 'base_commit'):
            row = dict(self.selection['primary'][0]); row[key] = '../../outside'
            with self.subTest(key=key), self.assertRaises(ValueError): assets.asset_paths(row)


if __name__ == '__main__': unittest.main()
