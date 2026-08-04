from pathlib import Path

main = Path('/tmp/Butterscotch/src/desktop/main.c')
text = main.read_text()
needle = 'glBindFramebuffer(GL_FRAMEBUFFER, *hostFramebuffer);'
count = text.count(needle)
if count < 1:
    raise SystemExit('Expected host framebuffer bind was not found')

# Older Apple OpenGL drivers do not expose EXT_framebuffer_object. The Mac OS
# 9 port deliberately supports rendering directly into the window in that
# case, but desktop/main.c still unconditionally called the missing function
# pointer while clearing/restoring the host framebuffer. Guard every such bind.
replacement = '''#ifdef PLATFORM_MACOS9
                    if (glad_glBindFramebuffer != NULL)
                        glBindFramebuffer(GL_FRAMEBUFFER, *hostFramebuffer);
#else
                    glBindFramebuffer(GL_FRAMEBUFFER, *hostFramebuffer);
#endif'''
text = text.replace(needle, replacement)
main.write_text(text)
print(f'Guarded {count} host framebuffer bind call(s)')
