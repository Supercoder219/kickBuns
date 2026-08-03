from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected source block: {label}")
    return text.replace(old, new, 1)


# v8 proved that the Rage-era Apple OpenGL driver does not tolerate all of the
# memory-saving experiments reliably. Keep only the direct-window orientation
# correction and return texture allocation/upload behavior to the v7 path.
renderer = Path('/tmp/Butterscotch/src/gl_legacy/gl_legacy_renderer.c')
text = renderer.read_text()
text = replace_once(
    text,
    '''#ifdef PLATFORM_MACOS9
#define BS_GL_TEXTURE_INTERNAL_FORMAT GL_RGBA4
#else
#define BS_GL_TEXTURE_INTERNAL_FORMAT GL_RGBA
#endif''',
    '#define BS_GL_TEXTURE_INTERNAL_FORMAT GL_RGBA',
    'restore ordinary RGBA texture format',
)

helper_start = text.find('#ifdef PLATFORM_MACOS9\nstatic uint8_t* macDownscaleTexturePage')
helper_end_marker = '#endif\n\n// Lazily decodes and uploads a TXTR page on first access.\n'
helper_end = text.find(helper_end_marker, helper_start)
if helper_start < 0 or helper_end < 0:
    raise SystemExit('Missing v8 texture downscaler helper')
text = text[:helper_start] + '// Lazily decodes and uploads a TXTR page on first access.\n' + text[helper_end + len(helper_end_marker):]

upload_start_marker = '''    glBindTexture(GL_TEXTURE_2D, gl->glTextures[pageId]);
#ifdef PLATFORM_MACOS9
    {
        int uploadW = w;'''
upload_end_marker = '''#endif

    free(pixels);'''
upload_start = text.find(upload_start_marker)
upload_end = text.find(upload_end_marker, upload_start)
if upload_start < 0 or upload_end < 0:
    raise SystemExit('Missing v8 texture upload block')
upload_end += len(upload_end_marker)
original_upload = '''    glBindTexture(GL_TEXTURE_2D, gl->glTextures[pageId]);
    glTexImage2D(GL_TEXTURE_2D, 0, BS_GL_TEXTURE_INTERNAL_FORMAT,
                 w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);

    free(pixels);'''
text = text[:upload_start] + original_upload + text[upload_end:]
renderer.write_text(text)


# Restore Retro68's tested console target. Besides preserving startup output,
# this removes the custom stdio shim from the runtime equation entirely.
root = Path('/tmp/Butterscotch/CMakeLists.txt')
text = root.read_text()
text = replace_once(
    text,
    '    add_application(butterscotch ${SOURCES} ${PLATFORM_SOURCES} ${AUDIO_SOURCES})',
    '    add_application(butterscotch ${SOURCES} ${PLATFORM_SOURCES} ${AUDIO_SOURCES} CONSOLE)',
    'restore Retro68 console target',
)
root.write_text(text)

mac_cmake = Path('/tmp/Butterscotch/macos9/CMakeLists.txt')
text = mac_cmake.read_text()
text = replace_once(
    text,
    '''    "${CMAKE_CURRENT_SOURCE_DIR}/../src/audio/macos9/mac_audio_system.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/macos9_silent_console.c"''',
    '    "${CMAKE_CURRENT_SOURCE_DIR}/../src/audio/macos9/mac_audio_system.c"',
    'remove custom silent console source',
)
text = replace_once(
    text,
    'add_compile_options(-mcpu=750 -mtune=750 -O3 -fomit-frame-pointer -fno-math-errno)',
    'add_compile_options(-mcpu=750 -mtune=750)',
    'restore conservative G3 compile flags',
)
mac_cmake.write_text(text)


# Restore the audio settings that were already hardware-tested in v7. Audio can
# be optimized separately after the renderer remains stable.
audio = Path('/tmp/Butterscotch/src/audio/macos9/mac_audio_system.c')
text = audio.read_text()
text = replace_once(text, '#define MAC_AUDIO_OUTPUT_RATE 22050',
                    '#define MAC_AUDIO_OUTPUT_RATE 44100', 'restore audio rate')
text = replace_once(text, '#define MAC_AUDIO_BUFFER_FRAMES 1024',
                    '#define MAC_AUDIO_BUFFER_FRAMES 2048', 'restore audio buffer size')
audio.write_text(text)
