from pathlib import Path
import os
import subprocess

workspace = Path(os.environ['GITHUB_WORKSPACE'])

# Keep the exact v5 flight-recorder and shutdown changes from the commit that
# produced the hardware-tested build, then apply the v6 event-loop repair.
v5_source = subprocess.check_output(
    [
        'git',
        'show',
        'a24cab4ea594e9e928e536597b252a61019c36aa:patch.v2/hotfix-runtime-v5.py',
    ],
    cwd=workspace,
    text=True,
)
exec(compile(v5_source, 'hotfix-runtime-v5-core.py', 'exec'))

v6_path = workspace / 'patch.v2' / 'hotfix-runtime-v6.py'
exec(compile(v6_path.read_text(), str(v6_path), 'exec'))
