from pathlib import Path
import hashlib
import os

workspace = Path(os.environ['GITHUB_WORKSPACE'])
source_root = Path('/tmp/Butterscotch')

# Start from the audited v11 tree. This reconstructs the exact v7 source chain
# and applies only the Mac OS 9 projection guard before returning here.
clean_path = workspace / 'patch.v2' / 'hotfix-runtime-v11-clean.py'
exec(compile(clean_path.read_text(), str(clean_path), 'exec'))


def hashes(root: Path):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


before_hashes = hashes(source_root)
runner = source_root / 'src/runner.c'
text = runner.read_text()

include_old = '#include "runner.h"\n'
include_new = '''#include "runner.h"
#ifdef PLATFORM_MACOS9
#include "macos9_trace.h"
#endif
'''
if text.count(include_old) != 1:
    raise SystemExit(f'Expected one runner.h include, found {text.count(include_old)}')
text = text.replace(include_old, include_new, 1)

old = '''    // The snapshot arena is stack-like and every push must be matched with a pop within the same frame. Assert that invariant at the top of each step: a non-zero length here means some site below pushed without popping, and we want a loud failure with the offending length so we can find it instead of silently leaking until the next frame.
    requireMessageFormatted(__FILE__, __LINE__, arrlen(runner->instanceSnapshots) == 0, "instanceSnapshots arena was not fully popped at end of previous frame (length=%td)", arrlen(runner->instanceSnapshots));
'''
new = '''    // The snapshot arena is stack-like and no snapshot is allowed to survive
    // across frame boundaries. On desktop platforms retain the assertion. On
    // Classic Mac OS, abort() becomes an unhelpful Finder "Error Type 1" and
    // can take the application down before the trace is flushed. Recover by
    // restoring the arena's required boundary state instead. This changes only
    // the stretchy-buffer length; it does not free or overwrite game objects.
#ifdef PLATFORM_MACOS9
    MacTrace_stage("Runner_step: snapshot boundary begin");
    {
        ptrdiff_t staleSnapshotCount = arrlen(runner->instanceSnapshots);
        if (staleSnapshotCount != 0) {
            char stage[96];
            snprintf(stage, sizeof(stage), "Runner_step: resetting stale snapshots count=%ld", (long) staleSnapshotCount);
            MacTrace_stage(stage);
            arrsetlen(runner->instanceSnapshots, 0);
        }
    }
    MacTrace_stage("Runner_step: snapshot boundary complete");
#else
    requireMessageFormatted(__FILE__, __LINE__, arrlen(runner->instanceSnapshots) == 0, "instanceSnapshots arena was not fully popped at end of previous frame (length=%td)", arrlen(runner->instanceSnapshots));
#endif
'''
if text.count(old) != 1:
    raise SystemExit(f'Expected one Runner_step snapshot assertion, found {text.count(old)}')
text = text.replace(old, new, 1)
runner.write_text(text)

after_hashes = hashes(source_root)
changed = sorted(set(before_hashes) | set(after_hashes))
changed = [p for p in changed if before_hashes.get(p) != after_hashes.get(p)]
expected = ['src/runner.c']
if changed != expected:
    raise SystemExit(f'v12 audit failed; changed files after v11 were: {changed!r}')

result = runner.read_text()
if result.count('Runner_step: snapshot boundary begin') != 1:
    raise SystemExit('v12 audit failed: boundary trace count is wrong')
if result.count('arrsetlen(runner->instanceSnapshots, 0);') != 1:
    raise SystemExit('v12 audit failed: recovery reset count is wrong')
if result.count('requireMessageFormatted(__FILE__, __LINE__, arrlen(runner->instanceSnapshots) == 0') != 1:
    raise SystemExit('v12 audit failed: non-Mac assertion count is wrong')

print('V12 AUDIT PASSED: v11 plus one Mac-only Runner_step snapshot-boundary recovery')
