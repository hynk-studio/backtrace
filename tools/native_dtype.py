"""Prepare the approved one-predicate serving change; never import/run the driver."""
import hashlib
import json
from pathlib import Path


BEFORE = 'torch.cuda.is_bf16_supported()'
AFTER = 'torch.cuda.is_bf16_supported(including_emulation=False)'
CELL_ID = 'f0b1ab0d'


def native_dtype_source(source):
    """Leave the bfloat16/auto branches and every other source byte unchanged."""
    if source.count(BEFORE) != 1:
        raise ValueError('expected exactly one original BF16 predicate')
    return source.replace(BEFORE, AFTER, 1)


def serving_sources(notebook_bytes):
    """Use only the retained organizer v2 notebook pinned by the source manifest."""
    manifest = Path(__file__).resolve().parents[1] / 'docs/source-manifest.json'
    pin = json.loads(manifest.read_text())['notebook']['sha256']
    if hashlib.sha256(notebook_bytes).hexdigest() != pin:
        raise ValueError('organizer notebook hash mismatch')
    cells = [cell for cell in json.loads(notebook_bytes)['cells']
             if cell.get('id') == CELL_ID and cell.get('cell_type') == 'code']
    if len(cells) != 1:
        raise ValueError('expected one pinned serving cell')
    source = ''.join(cells[0]['source'])
    return source, native_dtype_source(source)
