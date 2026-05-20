"""
Scan Data/TestInputData and show job-number grouping using the new job_utils.
Run with PYTHONPATH set to repository root (same pattern as other tools).
"""
import os
import pprint
from pathlib import Path

from src.services.job_utils import find_job_in_file

DATA_DIR = Path(__file__).parent.parent / 'Data' / 'TestInputData'

results = {}
for root, dirs, files in os.walk(DATA_DIR):
    for f in files:
        if not f.lower().endswith(('.msg', '.pdf')):
            continue
        p = os.path.join(root, f)
        job = find_job_in_file(p)
        results.setdefault(job, []).append(p)

print('Detected job groups:')
for job, paths in sorted(results.items(), key=lambda kv: (kv[0] is None, kv[0])):
    print(f"{job or 'Unknown'}: {len(paths)} file(s)")
    for pp in paths[:5]:
        print('  -', os.path.relpath(pp, Path.cwd()))
print('\nTotal files scanned:', sum(len(v) for v in results.values()))
