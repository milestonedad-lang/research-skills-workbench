"""Real container execution smoke check; run after building the runner image."""
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.core import Store
from server.execution import run_python


async def main():
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory)
        run = {'id':'smoke', 'project_id':'smoke', 'runner_image':'research-workbench-runner:0.1.0'}
        root = store.root / 'projects/smoke/runs/smoke'
        (root/'inputs').mkdir(parents=True)
        (root/'inputs/sample.csv').write_text('value\n1\n2\n3\n4\n5\n', encoding='utf-8')
        code = """import json, pathlib, pandas as pd, matplotlib.pyplot as plt
data = pd.read_csv('/inputs/sample.csv')['value']
pathlib.Path('/outputs/result.json').write_text(json.dumps({'mean':float(data.mean()),'n':int(data.count())}))
plt.hist(data)
plt.savefig('/outputs/figure.png')
try:
    pathlib.Path('/inputs/forbidden.txt').write_text('bad')
    raise AssertionError('inputs must be read-only')
except OSError:
    pass
print('smoke passed')
"""
        result = await run_python(store, run, code)
        assert result['exit_code'] == 0, result
        assert json.loads((root/'outputs/result.json').read_text()) == {'mean':3.0, 'n':5}
        png = (root/'outputs/figure.png').read_bytes()
        assert png.startswith(b'\x89PNG\r\n\x1a\n')
        print(json.dumps({'status':'passed', 'runner_digest':run['runner_digest'], 'png_sha256':hashlib.sha256(png).hexdigest()}))


if __name__ == '__main__':
    asyncio.run(main())
