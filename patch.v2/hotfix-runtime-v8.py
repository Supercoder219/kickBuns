from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected source block: {label}")
    return text.replace(old, new, 1)


renderer = Path('/tmp/Butterscotch/src/gl_legacy/gl_legacy_renderer.c')
text = renderer.read_text()

# Define the reduced Mac texture format before glInit creates its first texture.
text = replace_once(
    text,
    '#include "gl_common.h"\n',
    '''#include "gl_common.h"

#ifdef PLATFORM_MACOS9
#define BS_GL_TEXTURE_INTERNAL_FORMAT GL_RGBA4
#else
#define BS_GL_TEXTURE_INTERNAL_FORMAT GL_RGBA
#endif
''',
    'early texture format definition',
)

# The normal legacy renderer draws into an offscreen FBO and vertically flips
# its projection before the final surface blit. Direct-window mode has no final
# blit, so keeping that flip mirrors the complete Undertale frame vertically.
text = replace_once(
    text,
    '    Matrix4f_flipClipY(&projection);\n\n    glMatrixMode(GL_PROJECTION);',
    '''    if (!((GLLegacyRenderer*)renderer)->directFramebuffer)
        Matrix4f_flipClipY(&projection);

    glMatrixMode(GL_PROJECTION);''',
    'direct framebuffer projection orientation',
)

# GameMaker view rectangles use a top-left origin. OpenGL window viewports use
# a bottom-left origin. The old FBO path gets corrected by its final blit, while
# direct-window rendering must convert the viewport/scissor Y coordinate here.
text = replace_once(
    text,
    '''static void glApplyViewport(GLLegacyRenderer* gl, int32_t x, int32_t y, int32_t w, int32_t h) {
    glViewport(x, y, w, h);
    glEnable(GL_SCISSOR_TEST);
    glScissor(x, y, w, h);''',
    '''static void glApplyViewport(GLLegacyRenderer* gl, int32_t x, int32_t y, int32_t w, int32_t h) {
    int32_t nativeY = y;
    if (gl->directFramebuffer)
        nativeY = gl->gameH - y - h;
    glViewport(x, nativeY, w, h);
    glEnable(GL_SCISSOR_TEST);
    glScissor(x, nativeY, w, h);''',
    'direct framebuffer viewport orientation',
)

# Old Rage-class GPUs have tiny VRAM pools. A single 2048x2048 RGBA8 page is
# 16 MB, enough to fail outright on several iMac G3 configurations. Use a 16-bit
# internal texture format and cap oversized atlas uploads at 1024 pixels. UVs
# remain based on the original atlas dimensions, so sprite layout is preserved.
helper_anchor = '// Lazily decodes and uploads a TXTR page on first access.\n'
helper = r'''#ifdef PLATFORM_MACOS9
static uint8_t* macDownscaleTexturePage(const uint8_t* source, int srcW, int srcH,
                                        int* uploadW, int* uploadH) {
    GLint reportedMax = 0;
    int cap = 1024;
    int dstW = srcW;
    int dstH = srcH;
    uint8_t* result;
    int x, y;

    glGetIntegerv(GL_MAX_TEXTURE_SIZE, &reportedMax);
    if (reportedMax > 0 && reportedMax < cap) cap = (int)reportedMax;
    while (dstW > cap || dstH > cap) {
        dstW = dstW > 1 ? dstW / 2 : 1;
        dstH = dstH > 1 ? dstH / 2 : 1;
    }
    *uploadW = dstW;
    *uploadH = dstH;
    if (dstW == srcW && dstH == srcH) return NULL;

    result = (uint8_t*)safeMalloc((size_t)dstW * (size_t)dstH * 4u);
    for (y = 0; y < dstH; ++y) {
        int sy = (int)(((int64_t)y * srcH) / dstH);
        for (x = 0; x < dstW; ++x) {
            int sx = (int)(((int64_t)x * srcW) / dstW);
            const uint8_t* in = source + ((size_t)sy * (size_t)srcW + (size_t)sx) * 4u;
            uint8_t* out = result + ((size_t)y * (size_t)dstW + (size_t)x) * 4u;
            out[0] = in[0]; out[1] = in[1]; out[2] = in[2]; out[3] = in[3];
        }
    }
    return result;
}
#endif

'''
text = replace_once(text, helper_anchor, helper + helper_anchor, 'low-memory texture helper')

upload_old = '''    glBindTexture(GL_TEXTURE_2D, gl->glTextures[pageId]);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);

    free(pixels);'''
upload_new = '''    glBindTexture(GL_TEXTURE_2D, gl->glTextures[pageId]);
#ifdef PLATFORM_MACOS9
    {
        int uploadW = w;
        int uploadH = h;
        uint8_t* scaled = macDownscaleTexturePage(pixels, w, h, &uploadW, &uploadH);
        const uint8_t* uploadPixels = scaled != NULL ? scaled : pixels;
        while (glGetError() != GL_NO_ERROR) { }
        glTexImage2D(GL_TEXTURE_2D, 0, BS_GL_TEXTURE_INTERNAL_FORMAT,
                     uploadW, uploadH, 0, GL_RGBA, GL_UNSIGNED_BYTE, uploadPixels);
        if (glGetError() != GL_NO_ERROR) {
            char stage[96];
            snprintf(stage, sizeof(stage), "texture upload failed: page=%lu original=%ldx%ld upload=%dx%d",
                     (unsigned long)pageId, (long)w, (long)h, uploadW, uploadH);
            MacTrace_stage(stage);
            free(scaled);
            free(pixels);
            gl->textureWidths[pageId] = 0;
            gl->textureHeights[pageId] = 0;
            return false;
        }
        if (scaled != NULL) {
            char stage[96];
            snprintf(stage, sizeof(stage), "texture reduced: page=%lu %ldx%ld to %dx%d",
                     (unsigned long)pageId, (long)w, (long)h, uploadW, uploadH);
            MacTrace_stage(stage);
        }
        free(scaled);
    }
#else
    glTexImage2D(GL_TEXTURE_2D, 0, BS_GL_TEXTURE_INTERNAL_FORMAT,
                 w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
#endif

    free(pixels);'''
text = replace_once(text, upload_old, upload_new, 'texture page upload')

# Use RGBA4 for every other Mac texture allocation too, including white,
# dynamically captured sprites, and any future compatibility surfaces.
text = text.replace('glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,',
                    'glTexImage2D(GL_TEXTURE_2D, 0, BS_GL_TEXTURE_INTERNAL_FORMAT,')
renderer.write_text(text)


# A Retro68 console window is excellent while debugging and extremely expensive
# while a G3 is interpreting GML and drawing OpenGL. Keep stdio link symbols as
# cheap sinks, while MacTrace continues writing its persistent file directly.
root = Path('/tmp/Butterscotch/CMakeLists.txt')
text = root.read_text()
text = replace_once(
    text,
    '    add_application(butterscotch ${SOURCES} ${PLATFORM_SOURCES} ${AUDIO_SOURCES} CONSOLE)',
    '    add_application(butterscotch ${SOURCES} ${PLATFORM_SOURCES} ${AUDIO_SOURCES})',
    'Retro68 console removal',
)
root.write_text(text)

silent_console = Path('/tmp/Butterscotch/src/macos9_silent_console.c')
silent_console.write_text(r'''#include <sys/types.h>
#include <stddef.h>

ssize_t _consolewrite(int fd, const void* buffer, size_t count) {
    (void)fd;
    (void)buffer;
    return (ssize_t)count;
}

ssize_t _consoleread(int fd, void* buffer, size_t count) {
    (void)fd;
    (void)buffer;
    (void)count;
    return 0;
}
''')

mac_cmake = Path('/tmp/Butterscotch/macos9/CMakeLists.txt')
text = mac_cmake.read_text()
text = replace_once(
    text,
    '''target_sources(butterscotch PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/audio/macos9/mac_audio_system.c"
)''',
    '''target_sources(butterscotch PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/audio/macos9/mac_audio_system.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/macos9_silent_console.c"
)''',
    'silent console target source',
)

# Release already selects optimisation, but state the G3-safe hot path flags
# explicitly so container/toolchain defaults cannot quietly regress them.
text = replace_once(
    text,
    'add_compile_options(-mcpu=750 -mtune=750)',
    'add_compile_options(-mcpu=750 -mtune=750 -O3 -fomit-frame-pointer -fno-math-errno)',
    'G3 release optimisation flags',
)
mac_cmake.write_text(text)


# Halve Sound Manager's output/mixing rate while retaining all voices. Undertale
# remains stereo, while the G3 performs half as many mix samples.
audio = Path('/tmp/Butterscotch/src/audio/macos9/mac_audio_system.c')
text = audio.read_text()
text = replace_once(text, '#define MAC_AUDIO_OUTPUT_RATE 44100',
                    '#define MAC_AUDIO_OUTPUT_RATE 22050', 'audio output rate')
text = replace_once(text, '#define MAC_AUDIO_BUFFER_FRAMES 2048',
                    '#define MAC_AUDIO_BUFFER_FRAMES 1024', 'audio buffer size')
audio.write_text(text)
