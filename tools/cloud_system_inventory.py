"""Free exact-image discovery of signed Ubuntu packages needed by the harness.

Run only in the disposable CPU inventory container. Production consumes the
reviewed hash manifest and installs offline; it never runs an apt resolver.
"""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import urllib.parse


def inventory():
    before = {name: shutil.which(name) for name in ('git', 'patch', 'bash', 'setpriv')}
    subprocess.run(['apt-get', 'update'], check=True, timeout=300)
    command = ['apt-get', '--yes', '--no-install-recommends', '--download-only', 'install', 'git', 'patch']
    listing = subprocess.check_output(command[:1] + ['--print-uris'] + command[1:], text=True, timeout=60)
    sources = {}
    for line in listing.splitlines():
        if not line.startswith("'"):
            continue
        url, name, size, checksum = shlex.split(line)
        parsed = urllib.parse.urlsplit(url)
        if (parsed.hostname not in ('archive.ubuntu.com', 'security.ubuntu.com')
                or parsed.scheme not in ('http', 'https') or parsed.query or parsed.fragment
                or Path(name).name != name or not name.endswith('.deb')):
            raise ValueError('unexpected Ubuntu package URI')
        sources[name] = {'url': urllib.parse.urlunsplit(parsed._replace(scheme='https')), 'bytes': int(size)}
    subprocess.run(command, check=True, timeout=300)
    rows = []
    for name, source in sorted(sources.items()):
        path = Path('/var/cache/apt/archives') / name
        data = path.read_bytes()
        if len(data) != source['bytes']:
            raise ValueError('APT package size differs')
        package, version, architecture = subprocess.check_output(
            ['dpkg-deb', '-f', str(path), 'Package', 'Version', 'Architecture'], text=True).splitlines()
        rows.append(dict(path=name, sha256=hashlib.sha256(data).hexdigest(), **source,
                         package=package.removeprefix('Package: '),
                         version=version.removeprefix('Version: '),
                         architecture=architecture.removeprefix('Architecture: ')))
    if not rows or len(rows) > 24 or sum(row['bytes'] for row in rows) > 64 * 1024**2:
        raise ValueError('unexpected system package scope')
    subprocess.run(['dpkg', '--install', *[str(Path('/var/cache/apt/archives') / row['path']) for row in rows]],
                   check=True, timeout=180)
    report = {'schema_version': 1, 'distribution': 'Ubuntu 24.04',
              'requested': ['git', 'patch'], 'authentication': 'APT verified signed Ubuntu indexes and package hashes',
              'before': before, 'files': rows,
              'after': {name: shutil.which(name) for name in before},
              'git_version': subprocess.check_output(['git', '--version'], text=True).strip(),
              'paid_operations': 0}
    Path('/result/system-inventory.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__': inventory()
