from pathlib import Path
import os

workspace = Path(os.environ['GITHUB_WORKSPACE'])
clean_path = workspace / 'patch.v2' / 'hotfix-runtime-v11-clean.py'
exec(compile(clean_path.read_text(), str(clean_path), 'exec'))
