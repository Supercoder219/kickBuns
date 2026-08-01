from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected source block: {label}")
    return text.replace(old, new, 1)


backend = Path('/tmp/Butterscotch/src/desktop/backends/macos9.c')
text = backend.read_text()

# The first hardware trace stopped inside platformHandleEvents(). The original
# backend attempted to drain every pending event with WaitNextEvent(). AGL can
# continuously regenerate updateEvt messages, so the drain loop may never end
# and the runner never gets a chance to execute its first GML step or draw.
text = replace_once(
    text,
    '#include "runner_mouse.h"\n',
    '#include "runner_mouse.h"\n#include "macos9_trace.h"\n',
    'Mac trace include in backend',
)

start_marker = 'bool platformHandleEvents(void) {'
end_marker = '\nvoid platformSleepUntil(uint64_t targetTime) {'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('Could not locate Classic Mac event loop')

new_event_loop = r'''bool platformHandleEvents(void) {
    EventRecord event;
    bool shouldQuit = false;
    int processed = 0;
    static int traceBudget = 24;

    /*
     * Do not drain the Event Manager forever. AGL/updateEvt traffic can
     * replenish the queue while it is being drained. Process a bounded batch
     * and return to the runner so GML and rendering always receive CPU time.
     * GetNextEvent is deliberately non-blocking here; frame pacing happens in
     * platformSleepUntil().
     */
    while (processed < 32 && GetNextEvent(everyEvent, &event)) {
        if (traceBudget > 0) {
            char stage[80];
            snprintf(stage, sizeof(stage), "event: what=%d batch=%d", (int)event.what, processed);
            MacTrace_stage(stage);
            traceBudget--;
        }
        processed++;

        switch (event.what) {
            case keyDown:
            case autoKey: {
                int32_t gmlKey;
                unsigned char character = (unsigned char)(event.message & charCodeMask);
                if ((event.modifiers & cmdKey) && (character == 'q' || character == 'Q'))
                    return true;
                if (InputRecording_isPlaybackActive(globalInputRecording)) break;
                gmlKey = macKeyToGml(event.message);
                if (gmlKey >= 0) RunnerKeyboard_onKeyDown(g_runner->keyboard, gmlKey);
                if (character >= 32 && character != 127)
                    RunnerKeyboard_onCharacter(g_runner->keyboard, character);
                break;
            }
            case keyUp: {
                int32_t gmlKey;
                if (InputRecording_isPlaybackActive(globalInputRecording)) break;
                gmlKey = macKeyToGml(event.message);
                if (gmlKey >= 0) RunnerKeyboard_onKeyUp(g_runner->keyboard, gmlKey);
                break;
            }
            case mouseDown:
                handleMouseDown(&event, &shouldQuit);
                break;
            case mouseUp:
                if (!InputRecording_isPlaybackActive(globalInputRecording)) {
                    int32_t button = (event.modifiers & ControlKey) ? GML_MB_RIGHT : GML_MB_LEFT;
                    RunnerMouse_onButtonUp(g_runner->mouse, button);
                }
                break;
            case updateEvt:
                if ((WindowRef)event.message == g_window) {
                    SetPort((GrafPtr)g_window);
                    BeginUpdate(g_window);
                    EndUpdate(g_window);
                    /*
                     * Do not call aglUpdateContext here. Updating the AGL
                     * context from every updateEvt can immediately create more
                     * update events. The context is updated when the window is
                     * explicitly resized instead.
                     */
                }
                break;
            case activateEvt:
                if ((WindowRef)event.message == g_window)
                    g_windowActive = (event.modifiers & activeFlag) != 0;
                break;
            default:
                break;
        }
        if (shouldQuit) return true;
    }

    if (traceBudget > 0) {
        char stage[80];
        snprintf(stage, sizeof(stage), "event: poll returned count=%d", processed);
        MacTrace_stage(stage);
        traceBudget--;
    }
    return false;
}
'''

text = text[:start] + new_event_loop + text[end:]
backend.write_text(text)
