import os
from pathlib import Path
import tempfile
import unittest
from tools.research_isolation import file_parts, read_workspace, write_workspace


class FileBoundaryTests(unittest.TestCase):
    def test_final_and_parent_symlinks_cannot_read_owner_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); ws=root/'ws';ws.mkdir();secret=root/'private';secret.write_bytes(b'owner')
            (ws/'link').symlink_to(secret);(ws/'dir').symlink_to(root,target_is_directory=True)
            for name in ('link','dir/private'):
                with self.subTest(name=name), self.assertRaises(OSError):read_workspace(ws,name)

    def test_special_and_hardlinked_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'regular').write_bytes(b'owner');os.link(root/'regular',root/'link')
            os.mkfifo(root/'pipe')
            for name in ('link','pipe'):
                with self.subTest(name=name), self.assertRaises(ValueError):read_workspace(root,name)
            with self.assertRaises(ValueError):write_workspace(root,'link',b'bad',65532)
            self.assertEqual((root/'regular').read_bytes(),b'owner')

    def test_simple_read_and_bounded_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'file').write_bytes(b'contents')
            self.assertEqual(read_workspace(root,'/workspace/file'),b'contents')
            with self.assertRaises(ValueError):read_workspace(root,'file',limit=2)
        for value in ('../private','/etc/passwd','x/../y','./file','/workspace/../private'):
            with self.subTest(value=value), self.assertRaises(ValueError):file_parts(value)


if __name__=='__main__':unittest.main()
