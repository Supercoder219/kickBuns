from pathlib import Path
import difflib
import hashlib
import os
import subprocess

workspace = Path(os.environ['GITHUB_WORKSPACE'])
source_root = Path('/tmp/Butterscotch')
old_commit = 'a24cab4ea594e9e928e536597b252a61019c36aa'

# Reconstruct the exact hardware-proven v7 source chain. Do not execute the
# current wrapper, because it also contains the failed v8-v10 experiments.
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

for name in ('hotfix-runtime-v6.py', 'hotfix-runtime-v7.py'):
    path = workspace / 'patch.v2' / name
    exec(compile(path.read_text(), str(path), 'exec'))


def hashes(root: Path):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

before_hashes = hashes(source_root)
renderer = source_root / 'src/gl_legacy/gl_legacy_renderer.c'
before = renderer.read_text()
old = '    Matrix4f_flipClipY(&projection);'
new = '''#ifdef PLATFORM_MACOS9
    /* Direct-window mode already renders into the native bottom-up window. */
    if (!((GLLegacyRenderer*)renderer)->directFramebuffer)
#endif
        Matrix4f_flipClipY(&projection);'''
if before.count(old) != 1:
    raise SystemExit(f'Expected exactly one projection flip, found {before.count(old)}')
after = before.replace(old, new, 1)
renderer.write_text(after)

after_hashes = hashes(source_root)
changed = sorted(
    set(before_hashes) | set(after_hashes),
    key=str,
)
changed = [p for p in changed if before_hashes.get(p) != after_hashes.get(p)]
expected = ['src/gl_legacy/gl_legacy_renderer.c']
if changed != expected:
    raise SystemExit(f'Clean-source audit failed; changed files were: {changed!r}')

diff = ''.join(difflib.unified_diff(
    before.splitlines(True),
    after.splitlines(True),
    fromfile='v7/src/gl_legacy/gl_legacy_renderer.c',
    tofile='v11/src/gl_legacy/gl_legacy_renderer.c',
))
if diff.count('Matrix4f_flipClipY') != 2 or 'directFramebuffer' not in diff:
    raise SystemExit('Orientation diff audit failed')
Path('/tmp/source-audit.diff').write_text(diff)
print(diff)
print('SOURCE AUDIT PASSED: exact v7 source plus one renderer edit')
