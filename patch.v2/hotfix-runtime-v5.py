from pathlib import Path
import os

workspace = Path(os.environ['GITHUB_WORKSPACE'])
recovery_path = workspace / 'patch.v2' / 'hotfix-runtime-v12-snapshot-recovery.py'
exec(compile(recovery_path.read_text(), str(recovery_path), 'exec'))
