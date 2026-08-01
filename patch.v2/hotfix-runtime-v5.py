from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected source block: {label}")
    return text.replace(old, new, 1)


# Compile for the PowerPC 750 used by slot-loading iMac G3 systems. This also
# prevents the compiler from selecting AltiVec or post-G3 instructions.
cmake = Path('/tmp/Butterscotch/macos9/CMakeLists.txt')
text = cmake.read_text()
anchor = 'set(BUTTERSCOTCH_COMMIT_DATE "2026-07-31" CACHE STRING "" FORCE)\n'
text = replace_once(
    text,
    anchor,
    anchor + '\n# Generate code that is safe for the original PowerPC 750/G3.\n'
             'add_compile_options(-mcpu=750 -mtune=750)\n',
    'G3 compiler flags',
)
cmake.write_text(text)


main = Path('/tmp/Butterscotch/src/desktop/main.c')
text = main.read_text()

# Exit directly through the Toolbox on final shutdown. Retro68/newlib normally
# reaches ExitToShell too, but only after running a large cleanup chain. The
# hardware report shows the Type 3 trap is in that cleanup path, not startup.
text = replace_once(
    text,
    '#include <signal.h>\n',
    '#include <signal.h>\n#ifdef PLATFORM_MACOS9\n#include <Processes.h>\n#endif\n',
    'Processes include',
)

# First-frame flight recorder. Only the first three frames are logged so a
# successful run does not grow the startup file forever.
replacements = [
    (
        '        while (true) {\n            if (runner->shouldExit || shouldWindowClose) {',
        '        while (true) {\n#ifdef PLATFORM_MACOS9\n'
        '            if (runner->frameCount < 3) MacTrace_stage("frame: loop top");\n'
        '#endif\n            if (runner->shouldExit || shouldWindowClose) {',
        'loop top trace',
    ),
    (
        '            uint64_t frameStartNow = nowNanos();\n            runner->deltaTime = (int64_t)(frameStartNow - lastFrameStartTime) / 1000.0;',
        '#ifdef PLATFORM_MACOS9\n'
        '            if (runner->frameCount < 3) MacTrace_stage("frame: timing begin");\n'
        '#endif\n            uint64_t frameStartNow = nowNanos();\n'
        '            runner->deltaTime = (int64_t)(frameStartNow - lastFrameStartTime) / 1000.0;\n'
        '#ifdef PLATFORM_MACOS9\n'
        '            if (runner->frameCount < 3) MacTrace_stage("frame: timing complete");\n'
        '#endif',
        'timing trace',
    ),
    (
        '            RunnerKeyboard_beginFrame(runner->keyboard);\n            RunnerGamepad_beginFrame(runner->gamepads);\n            RunnerMouse_beginFrame(runner->mouse);\n            if (platformHandleEvents()) {',
        '#ifdef PLATFORM_MACOS9\n'
        '            if (runner->frameCount < 3) MacTrace_stage("frame: input reset begin");\n'
        '#endif\n            RunnerKeyboard_beginFrame(runner->keyboard);\n'
        '            RunnerGamepad_beginFrame(runner->gamepads);\n'
        '            RunnerMouse_beginFrame(runner->mouse);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '            if (runner->frameCount < 3) MacTrace_stage("frame: event polling begin");\n'
        '#endif\n            if (platformHandleEvents()) {\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                MacTrace_stage("frame: close requested");\n'
        '#endif',
        'input and event trace',
    ),
    (
        '                continue;\n            }\n\n            // Debug key bindings',
        '                continue;\n            }\n#ifdef PLATFORM_MACOS9\n'
        '            if (runner->frameCount < 3) MacTrace_stage("frame: event polling complete");\n'
        '#endif\n\n            // Debug key bindings',
        'event completion trace',
    ),
    (
        '                InputRecording_processFrame(globalInputRecording, runner->keyboard, inputFrameCount++);',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: input recording begin");\n'
        '#endif\n                InputRecording_processFrame(globalInputRecording, runner->keyboard, inputFrameCount++);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: input recording complete");\n'
        '#endif',
        'input recording trace',
    ),
    (
        '                // Run one game step (Begin Step, Keyboard, Alarms, Step, End Step, room transitions)\n                Runner_step(runner);',
        '                // Run one game step (Begin Step, Keyboard, Alarms, Step, End Step, room transitions)\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: Runner_step begin");\n'
        '#endif\n                Runner_step(runner);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: Runner_step complete");\n'
        '#endif',
        'Runner_step trace',
    ),
    (
        '                runner->audioSystem->vtable->update(runner->audioSystem, dt);',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: audio update begin");\n'
        '#endif\n                runner->audioSystem->vtable->update(runner->audioSystem, dt);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: audio update complete");\n'
        '#endif',
        'audio update trace',
    ),
    (
        '                // Clear the default framebuffer (window background) to black',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: framebuffer clear begin");\n'
        '#endif\n                // Clear the default framebuffer (window background) to black',
        'framebuffer clear begin trace',
    ),
    (
        '                // Query actual framebuffer size\n                int32_t fbWidth, fbHeight;',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: framebuffer clear complete");\n'
        '#endif\n                // Query actual framebuffer size\n                int32_t fbWidth, fbHeight;',
        'framebuffer clear complete trace',
    ),
    (
        '                Runner_drawPre(runner, fbWidth, fbHeight);',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: drawPre begin");\n'
        '#endif\n                Runner_drawPre(runner, fbWidth, fbHeight);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: drawPre complete");\n'
        '#endif',
        'drawPre trace',
    ),
    (
        '                Runner_beginFrame(runner, gameW, gameH, winW, winH, fbWidth, fbHeight);',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: beginFrame begin");\n'
        '#endif\n                Runner_beginFrame(runner, gameW, gameH, winW, winH, fbWidth, fbHeight);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: beginFrame complete");\n'
        '#endif',
        'beginFrame trace',
    ),
    (
        '                Runner_drawViews(runner, gameW, gameH, debugShowCollisionMasks);\n                renderer->vtable->endFrameInit(renderer);\n                Runner_drawPost(runner, fbWidth, fbHeight);\n                renderer->vtable->endFrameEnd(renderer);\n                Runner_drawGUI(runner, fbWidth, fbHeight, gameW, gameH);',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: drawViews begin");\n'
        '#endif\n                Runner_drawViews(runner, gameW, gameH, debugShowCollisionMasks);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: drawViews complete; endFrameInit begin");\n'
        '#endif\n                renderer->vtable->endFrameInit(renderer);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: endFrameInit complete; drawPost begin");\n'
        '#endif\n                Runner_drawPost(runner, fbWidth, fbHeight);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: drawPost complete; endFrameEnd begin");\n'
        '#endif\n                renderer->vtable->endFrameEnd(renderer);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: endFrameEnd complete; drawGUI begin");\n'
        '#endif\n                Runner_drawGUI(runner, fbWidth, fbHeight, gameW, gameH);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: drawGUI complete");\n'
        '#endif',
        'draw pipeline trace',
    ),
    (
        '                if (runner->pendingRoom == -1)\n                    platformSwapBuffers();\n                Runner_handlePendingRoomChange(runner);',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: swap begin");\n'
        '#endif\n                if (runner->pendingRoom == -1)\n                    platformSwapBuffers();\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: swap complete; pending room begin");\n'
        '#endif\n                Runner_handlePendingRoomChange(runner);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: pending room complete");\n'
        '#endif',
        'swap trace',
    ),
    (
        '                platformSleepUntil(nextFrameTime);',
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: limiter sleep begin");\n'
        '#endif\n                platformSleepUntil(nextFrameTime);\n'
        '#ifdef PLATFORM_MACOS9\n'
        '                if (runner->frameCount < 3) MacTrace_stage("frame: limiter sleep complete");\n'
        '#endif',
        'frame limiter trace',
    ),
    (
        '            lastFrameTime = nowNanos();\n        }\n\n        saveInputRecording();',
        '            lastFrameTime = nowNanos();\n#ifdef PLATFORM_MACOS9\n'
        '            if (runner->frameCount < 3) MacTrace_stage("frame: iteration complete");\n'
        '#endif\n        }\n\n#ifdef PLATFORM_MACOS9\n'
        '        if (actuallyShuttingDown) {\n'
        '            MacTrace_stage("shutdown: direct ExitToShell");\n'
        '            ExitToShell();\n'
        '        }\n'
        '#endif\n        saveInputRecording();',
        'iteration and direct shutdown trace',
    ),
]

for old, new, label in replacements:
    text = replace_once(text, old, new, label)
main.write_text(text)


# Prepare the Sound Manager channel during startup, but do not start its
# asynchronous callback until several successful game-loop updates have run.
audio = Path('/tmp/Butterscotch/src/audio/macos9/mac_audio_system.c')
text = audio.read_text()
text = replace_once(
    text,
    '    bool initialized;\n    bool suspended;',
    '    bool initialized;\n    bool playbackStarted;\n    uint32_t updateCount;\n    bool suspended;',
    'audio delayed-start fields',
)
text = replace_once(
    text,
    '''    gMacAudio = mac;
    err = SndPlayDoubleBuffer(mac->channel, &mac->header);
    if (err != noErr) {
        fprintf(stderr, "Mac audio: SndPlayDoubleBuffer failed (%d); continuing without sound\\n", (int)err);
        MacTrace_stage("audio init failed: SndPlayDoubleBuffer");
        gMacAudio = NULL;
        return;
    }
    mac->initialized = true;
    fprintf(stderr, "Mac audio: Sound Manager mixer initialized at %d Hz\\n", MAC_AUDIO_OUTPUT_RATE);
    MacTrace_stage("audio init complete");''',
    '''    gMacAudio = mac;
    mac->initialized = true;
    mac->playbackStarted = false;
    mac->updateCount = 0;
    fprintf(stderr, "Mac audio: Sound Manager prepared at %d Hz; playback is delayed\\n", MAC_AUDIO_OUTPUT_RATE);
    MacTrace_stage("audio prepared; playback deferred");''',
    'defer SndPlayDoubleBuffer',
)
text = replace_once(
    text,
    '''    if (!mac->initialized) return;
    for (i = 0; i < 2; ++i) {''',
    '''    if (!mac->initialized) return;
    if (!mac->playbackStarted) {
        OSErr err;
        mac->updateCount++;
        if (mac->updateCount < 3) return;
        MacTrace_stage("audio playback start begin");
        err = SndPlayDoubleBuffer(mac->channel, &mac->header);
        if (err != noErr) {
            fprintf(stderr, "Mac audio: delayed SndPlayDoubleBuffer failed (%d); disabling sound\\n", (int)err);
            MacTrace_stage("audio playback start failed");
            gMacAudio = NULL;
            mac->initialized = false;
            return;
        }
        mac->playbackStarted = true;
        MacTrace_stage("audio playback start complete");
    }
    for (i = 0; i < 2; ++i) {''',
    'start audio after stable frames',
)
audio.write_text(text)
