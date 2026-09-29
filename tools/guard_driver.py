"""Reproduce the startup-only transform of the retained private driver; never run it."""
import argparse
import ast
import difflib
import hashlib
from pathlib import Path
import shutil


DRIVER_SHA256 = 'c7eda43a043535eed064b8f347bf271b22eb235c539e44dfe1633c43f47f5189'
ANCHOR = " ns=shared_namespace();before,after=NATIVE_SERVING.split('server_instance.start()\\n',1)\n exec(before,ns)\n"
REPLACEMENT = """ ns=shared_namespace();before,after=NATIVE_SERVING.split('server_instance.start()\\n',1)
 from importlib.util import spec_from_file_location, module_from_spec
 spec=spec_from_file_location('startup_guard',Path(__file__).with_name('startup_guard.py'))
 guard=module_from_spec(spec);spec.loader.exec_module(guard)
 ns['guarded_server']=guard.guarded_server
 ns['startup_total_deadline']=time.monotonic()+max(0,float(os.environ['BACKTRACE_USEFUL_DEADLINE'])-time.time())
 anchor='server_instance = VllmServer('
 assert before.count(anchor)==1,'unexpected pinned constructor'
 before=before.replace(anchor,'server_instance = guarded_server(VllmServer,total_deadline=startup_total_deadline)(',1)
 exec(before,ns)
"""


def transform(source):
    changes = [
        (ANCHOR, REPLACEMENT),
        (" shutil.copyfile(__file__,CODE/'one_task.py')\n",
         " shutil.copyfile(__file__,CODE/'one_task.py')\n"
         " shutil.copyfile(Path(__file__).with_name('startup_guard.py'),CODE/'startup_guard.py')\n"),
        ("  event('server_stop_returned',seconds=time.time()-start)\n",
         "  event('server_stop_returned',seconds=time.time()-start)\n"
         "  event('startup_observation',**server.startup_observation)\n")]
    for before, after in changes:
        if source.count(before) != 1:
            raise ValueError('unexpected private driver shape; no output created')
        source = source.replace(before, after, 1)
    ast.parse(source)
    return source


def prepare(source, output):
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != DRIVER_SHA256:
        raise ValueError('retained no-custom-ar driver hash mismatch')
    result = transform(data.decode())
    # A new directory prevents overwriting an old attempt or its consumed marker.
    output.mkdir(mode=0o700)
    try:
        (output / 'one_task.py').write_text(result)
        shutil.copyfile(Path(__file__).with_name('startup_guard.py'), output / 'startup_guard.py')
        (output / 'driver.diff').write_text(''.join(difflib.unified_diff(
            data.decode().splitlines(True), result.splitlines(True),
            fromfile='retained-no-custom-ar/one_task.py', tofile='startup-guard/one_task.py')))
    except BaseException:
        shutil.rmtree(output)
        raise
    return hashlib.sha256(result.encode()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(prepare(args.source, args.output))
