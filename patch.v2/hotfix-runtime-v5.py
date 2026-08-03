from pathlib import Path
import os
import subprocess

workspace = Path(os.environ['GITHUB_WORKSPACE'])
old_commit = 'a24cab4ea594e9e928e536597b252a61019c36aa'

# Actions checks out a shallow synthetic PR merge. Mark it safe and fetch the
# exact commit containing the hardware-tested v5 script before reading it.
subprocess.run(
    ['git', 'config', '--global', '--add', 'safe.directory', str(workspace)],
    check=True,
)
subprocess.run(
    ['git', 'fetch', '--depth=1', 'origin', old_commit],
    cwd=workspace,
    check=True,
)
v5_source = subprocess.check_output(
    ['git', 'show', f'{old_commit}:patch.v2/hotfix-runtime-v5.py'],
    cwd=workspace,
    text=True,
)
exec(compile(v5_source, 'hotfix-runtime-v5-core.py', 'exec'))

v6_path = workspace / 'patch.v2' / 'hotfix-runtime-v6.py'
exec(compile(v6_path.read_text(), str(v6_path), 'exec'))

v7_path = workspace / 'patch.v2' / 'hotfix-runtime-v7.py'
exec(compile(v7_path.read_text(), str(v7_path), 'exec'))

v8_path = workspace / 'patch.v2' / 'hotfix-runtime-v8.py'
exec(compile(v8_path.read_text(), str(v8_path), 'exec'))
