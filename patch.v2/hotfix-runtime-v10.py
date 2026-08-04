from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected source block: {label}")
    return text.replace(old, new, 1)


# v9's address error was introduced by converting the viewport/scissor Y
# coordinate using gl->gameH. glApplyViewport can be reached before gameH has
# been initialized for the first frame, which can pass a garbage coordinate to
# Apple's Rage-era OpenGL driver. Restore the hardware-tested v7 viewport code.
# Keep only v8's much narrower projection correction: direct-window rendering
# must not apply the FBO-oriented clip-space Y flip.
renderer = Path('/tmp/Butterscotch/src/gl_legacy/gl_legacy_renderer.c')
text = renderer.read_text()
text = replace_once(
    text,
    '''static void glApplyViewport(GLLegacyRenderer* gl, int32_t x, int32_t y, int32_t w, int32_t h) {
    int32_t nativeY = y;
    if (gl->directFramebuffer)
        nativeY = gl->gameH - y - h;
    glViewport(x, nativeY, w, h);
    glEnable(GL_SCISSOR_TEST);
    glScissor(x, nativeY, w, h);''',
    '''static void glApplyViewport(GLLegacyRenderer* gl, int32_t x, int32_t y, int32_t w, int32_t h) {
    glViewport(x, y, w, h);
    glEnable(GL_SCISSOR_TEST);
    glScissor(x, y, w, h);''',
    'restore stable viewport coordinates',
)

projection_fix = '''    if (!((GLLegacyRenderer*)renderer)->directFramebuffer)
        Matrix4f_flipClipY(&projection);'''
if projection_fix not in text:
    raise SystemExit('Missing narrow direct-window projection correction')

renderer.write_text(text)
