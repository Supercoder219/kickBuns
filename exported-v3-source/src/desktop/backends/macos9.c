#include <Types.h>
#include <Quickdraw.h>
#include <Windows.h>
#include <Events.h>
#include <OSUtils.h>
#include <ToolUtils.h>
/* CFM declarations are provided through Types.h. */
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common.h"
#include "desktop/platformdefs.h"
#include "gettime.h"
#include "input_recording.h"
#include "runner_keyboard.h"
#include "runner_mouse.h"

/*
 * Native Classic Mac OS Toolbox + AGL backend.
 *
 * OpenGLLibrary is loaded through Code Fragment Manager instead of linked.
 * This keeps the Retro68 build independent of a particular OpenGL import
 * library and gives GLAD a real get-proc-address implementation on Mac OS 9.
 */

typedef void* AGLPixelFormat;
typedef void* AGLContext;
typedef void* AGLDrawable;
typedef unsigned char AGLBoolean;
typedef int AGLInt;

#define AGL_NONE          0
#define AGL_RGBA          4
#define AGL_DOUBLEBUFFER  5

typedef AGLPixelFormat (*PFN_AGL_CHOOSE_PIXEL_FORMAT)(GDHandle*, AGLInt, const AGLInt*);
typedef AGLContext (*PFN_AGL_CREATE_CONTEXT)(AGLPixelFormat, AGLContext);
typedef void (*PFN_AGL_DESTROY_PIXEL_FORMAT)(AGLPixelFormat);
typedef AGLBoolean (*PFN_AGL_SET_DRAWABLE)(AGLContext, AGLDrawable);
typedef AGLBoolean (*PFN_AGL_SET_CURRENT_CONTEXT)(AGLContext);
typedef AGLBoolean (*PFN_AGL_SWAP_BUFFERS)(AGLContext);
typedef AGLBoolean (*PFN_AGL_UPDATE_CONTEXT)(AGLContext);
typedef AGLBoolean (*PFN_AGL_DESTROY_CONTEXT)(AGLContext);
typedef unsigned int (*PFN_AGL_GET_ERROR)(void);

static WindowRef g_window = NULL;
static AGLContext g_context = NULL;
static ConnectionID g_openGLConnection = 0;
static bool g_openGLLibraryLoaded = false;
static bool g_windowActive = true;
static int32_t g_windowWidth = 0;
static int32_t g_windowHeight = 0;
static Runner* g_runner = NULL;

static PFN_AGL_CHOOSE_PIXEL_FORMAT p_aglChoosePixelFormat = NULL;
static PFN_AGL_CREATE_CONTEXT p_aglCreateContext = NULL;
static PFN_AGL_DESTROY_PIXEL_FORMAT p_aglDestroyPixelFormat = NULL;
static PFN_AGL_SET_DRAWABLE p_aglSetDrawable = NULL;
static PFN_AGL_SET_CURRENT_CONTEXT p_aglSetCurrentContext = NULL;
static PFN_AGL_SWAP_BUFFERS p_aglSwapBuffers = NULL;
static PFN_AGL_UPDATE_CONTEXT p_aglUpdateContext = NULL;
static PFN_AGL_DESTROY_CONTEXT p_aglDestroyContext = NULL;
static PFN_AGL_GET_ERROR p_aglGetError = NULL;

static void makePascalString(const char* src, unsigned char* dst, size_t maxChars) {
    size_t len = strlen(src);
    if (len > maxChars) len = maxChars;
    dst[0] = (unsigned char)len;
    if (len != 0) memcpy(dst + 1, src, len);
}

static void* findOpenGLSymbol(const char* name) {
    Ptr address = NULL;
    SymClass symbolClass;
    Str255 symbolName;

    if (!g_openGLLibraryLoaded) return NULL;
    makePascalString(name, symbolName, 255);
    if (FindSymbol(g_openGLConnection, symbolName, &address, &symbolClass) != noErr)
        return NULL;
    return (void*)address;
}

static bool loadOpenGLLibrary(void) {
    Str63 libraryName;
    Str255 errorName;
    Ptr mainAddress = NULL;

    if (g_openGLLibraryLoaded) return true;

    makePascalString("OpenGLLibrary", libraryName, 63);
    if (GetSharedLibrary(libraryName, kPowerPCArch, kReferenceCFrag,
                         &g_openGLConnection, &mainAddress, errorName) != noErr) {
        fprintf(stderr, "Mac OS 9: Could not load OpenGLLibrary. Install Apple OpenGL 1.2.1.\n");
        return false;
    }
    g_openGLLibraryLoaded = true;

#define LOAD_AGL(name, type) do { \
    p_##name = (type)findOpenGLSymbol(#name); \
    if (!p_##name) { \
        fprintf(stderr, "Mac OS 9: OpenGLLibrary is missing %s.\n", #name); \
        return false; \
    } \
} while (0)

    LOAD_AGL(aglChoosePixelFormat, PFN_AGL_CHOOSE_PIXEL_FORMAT);
    LOAD_AGL(aglCreateContext, PFN_AGL_CREATE_CONTEXT);
    LOAD_AGL(aglDestroyPixelFormat, PFN_AGL_DESTROY_PIXEL_FORMAT);
    LOAD_AGL(aglSetDrawable, PFN_AGL_SET_DRAWABLE);
    LOAD_AGL(aglSetCurrentContext, PFN_AGL_SET_CURRENT_CONTEXT);
    LOAD_AGL(aglSwapBuffers, PFN_AGL_SWAP_BUFFERS);
    LOAD_AGL(aglUpdateContext, PFN_AGL_UPDATE_CONTEXT);
    LOAD_AGL(aglDestroyContext, PFN_AGL_DESTROY_CONTEXT);
    LOAD_AGL(aglGetError, PFN_AGL_GET_ERROR);
#undef LOAD_AGL

    return true;
}

void* platformGetProcAddress(const char* name) {
    void* result = findOpenGLSymbol(name);

    /* OpenGL 1.2 exposes a few later-core entry points under ARB/EXT names. */
    if (!result && strcmp(name, "glActiveTexture") == 0)
        result = findOpenGLSymbol("glActiveTextureARB");
    if (!result && strcmp(name, "glClientActiveTexture") == 0)
        result = findOpenGLSymbol("glClientActiveTextureARB");
    if (!result && strcmp(name, "glBlendFuncSeparate") == 0)
        result = findOpenGLSymbol("glBlendFuncSeparateEXT");
    if (!result && strcmp(name, "glBlendEquation") == 0)
        result = findOpenGLSymbol("glBlendEquationEXT");

    return result;
}

static void setPascalWindowTitle(const char* title) {
    Str255 pTitle;
    makePascalString(title, pTitle, 255);
    if (g_window) SetWTitle(g_window, pTitle);
}

void platformSetWindowTitle(const char* title) {
    char fullTitle[256];
    snprintf(fullTitle, sizeof(fullTitle), "Butterscotch - %s", title ? title : "Undertale");
    setPascalWindowTitle(fullTitle);
}

static bool platformGetWindowFocus(void) {
    return g_windowActive;
}

static void platformSetCursor(int32_t cursorType) {
    if (cursorType == GML_CR_NONE)
        HideCursor();
    else {
        InitCursor();
        ShowCursor();
    }
}

bool platformGetWindowSize(int32_t* outW, int32_t* outH) {
    if (!outW || !outH || !g_window) return false;
    *outW = g_windowWidth;
    *outH = g_windowHeight;
    return true;
}

bool platformGetScaledWindowSize(int32_t* outW, int32_t* outH) {
    return platformGetWindowSize(outW, outH);
}

void platformSetWindowSize(int32_t width, int32_t height) {
    if (!g_window || width <= 0 || height <= 0) return;
    g_windowWidth = width;
    g_windowHeight = height;
    SizeWindow(g_window, (short)width, (short)height, true);
    if (g_context && p_aglUpdateContext) p_aglUpdateContext(g_context);
}

void platformGetMousePos(double* xPos, double* yPos) {
    Point point;
    if (!xPos || !yPos || !g_window) return;
    SetPort((GrafPtr)g_window);
    GetMouse(&point);
    *xPos = (double)point.h;
    *yPos = (double)point.v;
}

bool platformInit(int32_t reqW, int32_t reqH, const char* title, bool headless) {
    Rect bounds;
    AGLInt attributes[] = { AGL_RGBA, AGL_DOUBLEBUFFER, AGL_NONE };
    AGLPixelFormat pixelFormat;
    Str255 initialTitle;

    if (headless) {
        fprintf(stderr, "Mac OS 9: Headless mode is unavailable.\n");
        return false;
    }
    if (gfx != LEGACY_GL) {
        fprintf(stderr, "Mac OS 9: This port only supports the legacy OpenGL renderer.\n");
        return false;
    }
    if (!loadOpenGLLibrary()) return false;

    SetRect(&bounds, 60, 60, (short)(60 + reqW), (short)(60 + reqH));
    makePascalString(title ? title : "Undertale", initialTitle, 255);
    g_window = NewCWindow(NULL, &bounds, initialTitle, false, documentProc,
                          (WindowPtr)-1L, true, 0);
    if (!g_window) {
        fprintf(stderr, "Mac OS 9: NewCWindow failed.\n");
        return false;
    }

    g_windowWidth = reqW;
    g_windowHeight = reqH;
    platformSetWindowTitle(title);

    pixelFormat = p_aglChoosePixelFormat(NULL, 0, attributes);
    if (!pixelFormat) {
        fprintf(stderr, "Mac OS 9: aglChoosePixelFormat failed (0x%X).\n",
                p_aglGetError ? p_aglGetError() : 0);
        DisposeWindow(g_window);
        g_window = NULL;
        return false;
    }

    g_context = p_aglCreateContext(pixelFormat, NULL);
    p_aglDestroyPixelFormat(pixelFormat);
    if (!g_context) {
        fprintf(stderr, "Mac OS 9: aglCreateContext failed (0x%X).\n",
                p_aglGetError ? p_aglGetError() : 0);
        DisposeWindow(g_window);
        g_window = NULL;
        return false;
    }

    if (!p_aglSetDrawable(g_context, (AGLDrawable)g_window) ||
        !p_aglSetCurrentContext(g_context)) {
        fprintf(stderr, "Mac OS 9: Could not attach the AGL context (0x%X).\n",
                p_aglGetError ? p_aglGetError() : 0);
        p_aglDestroyContext(g_context);
        g_context = NULL;
        DisposeWindow(g_window);
        g_window = NULL;
        return false;
    }

    ShowWindow(g_window);
    SelectWindow(g_window);
    InitCursor();
    return true;
}

void platformInitFunctions(Runner* runner) {
    int i;
    g_runner = runner;
    runner->windowHasFocus = platformGetWindowFocus;
    runner->setCursor = platformSetCursor;
    runner->currentCursor = GML_CR_DEFAULT;

    runner->gamepads->connectedCount = 0;
    for (i = 0; i < MAX_GAMEPADS; ++i)
        runner->gamepads->slots[i].connected = false;
}

void platformSwapBuffers(void) {
    if (g_context && p_aglSwapBuffers) p_aglSwapBuffers(g_context);
}

void platformExit(void) {
    if (g_context) {
        if (p_aglSetCurrentContext) p_aglSetCurrentContext(NULL);
        if (p_aglSetDrawable) p_aglSetDrawable(g_context, NULL);
        if (p_aglDestroyContext) p_aglDestroyContext(g_context);
        g_context = NULL;
    }
    if (g_window) {
        DisposeWindow(g_window);
        g_window = NULL;
    }
    if (g_openGLLibraryLoaded) {
        CloseConnection(&g_openGLConnection);
        g_openGLLibraryLoaded = false;
        g_openGLConnection = 0;
    }
}

static int32_t macKeyToGml(UInt32 message) {
    unsigned char charCode = (unsigned char)(message & charCodeMask);
    unsigned char keyCode = (unsigned char)((message & keyCodeMask) >> 8);

    if (charCode >= 'a' && charCode <= 'z') return toupper(charCode);
    if (charCode >= 'A' && charCode <= 'Z') return charCode;
    if (charCode >= '0' && charCode <= '9') return charCode;

    switch (keyCode) {
        case 0x24: return VK_ENTER;
        case 0x30: return VK_TAB;
        case 0x31: return VK_SPACE;
        case 0x33: return VK_BACKSPACE;
        case 0x35: return VK_ESCAPE;
        case 0x38:
        case 0x3C: return VK_SHIFT;
        case 0x3B:
        case 0x3E: return VK_CONTROL;
        case 0x3A:
        case 0x3D: return VK_ALT;
        case 0x72: return VK_INSERT;
        case 0x73: return VK_HOME;
        case 0x74: return VK_PAGEUP;
        case 0x75: return VK_DELETE;
        case 0x77: return VK_END;
        case 0x79: return VK_PAGEDOWN;
        case 0x7B: return VK_LEFT;
        case 0x7C: return VK_RIGHT;
        case 0x7D: return VK_DOWN;
        case 0x7E: return VK_UP;
        case 0x7A: return VK_F1;
        case 0x78: return VK_F2;
        case 0x63: return VK_F3;
        case 0x76: return VK_F4;
        case 0x60: return VK_F5;
        case 0x61: return VK_F6;
        case 0x62: return VK_F7;
        case 0x64: return VK_F8;
        case 0x65: return VK_F9;
        case 0x6D: return VK_F10;
        case 0x67: return VK_F11;
        case 0x6F: return VK_F12;
        default: return -1;
    }
}

static void handleMouseDown(const EventRecord* event, bool* shouldQuit) {
    WindowRef hitWindow = NULL;
    short part = FindWindow(event->where, &hitWindow);

    if (part == inGoAway && hitWindow == g_window) {
        if (TrackGoAway(g_window, event->where)) *shouldQuit = true;
        return;
    }
    if (part == inDrag && hitWindow == g_window) {
        Rect dragBounds = qd.screenBits.bounds;
        InsetRect(&dragBounds, 4, 4);
        DragWindow(g_window, event->where, &dragBounds);
        return;
    }
    if (part == inContent && hitWindow == g_window) {
        SelectWindow(g_window);
        if (!InputRecording_isPlaybackActive(globalInputRecording)) {
            int32_t button = (event->modifiers & ControlKey) ? GML_MB_RIGHT : GML_MB_LEFT;
            RunnerMouse_onButtonDown(g_runner->mouse, button);
        }
    }
}

bool platformHandleEvents(void) {
    EventRecord event;
    bool shouldQuit = false;

    while (WaitNextEvent(everyEvent, &event, 0, NULL)) {
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
                    BeginUpdate(g_window);
                    EndUpdate(g_window);
                    if (g_context && p_aglUpdateContext) p_aglUpdateContext(g_context);
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
    return false;
}

void platformSleepUntil(uint64_t targetTime) {
    while (nowNanos() < targetTime) {
        uint64_t remaining = targetTime - nowNanos();
        EventRecord ignored;
        UInt32 ticks = (UInt32)(remaining / 16666667ULL);
        if (ticks == 0) ticks = 1;
        if (ticks > 4) ticks = 4;
        WaitNextEvent(0, &ignored, ticks, NULL);
    }
}
