"""Owner-side allowlisted source bundle; authenticated transport never carries task assets."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
FILES=('tools/private_delivery.py','tools/direct_delivery.py',
       'tools/startup_guard.py','tools/research_split.py','tools/research_split_server.py',
       'tools/research_serving.py','tools/research_serving_install.py','docs/linux-wheel-manifest.json')


def bundle(destination,material,*,authored_cpu=False):
    destination=Path(destination);destination.mkdir(mode=0o700)
    names=list(FILES)
    if authored_cpu:names.append('tests/research_serving_fixture.py')
    rows=[]
    for name in names:
        source=ROOT/name;data=source.read_bytes()
        target=destination/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        target.write_bytes(data);target.chmod(0o600)
        rows.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    # The client private key never enters the serving payload.
    from tools.research_split import private_file
    for name in ('server.key','server.crt','client.crt'):
        source=private_file(Path(material)/name);data=source.read_bytes()
        target=destination/'transport'/name;target.parent.mkdir(mode=0o700,exist_ok=True)
        shutil.copyfile(source,target);target.chmod(0o600)
        rows.append({'path':'transport/'+name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    return json.dumps({'schema_version':1,'phase':'bootstrap','files':rows},sort_keys=True,separators=(',',':')).encode()
