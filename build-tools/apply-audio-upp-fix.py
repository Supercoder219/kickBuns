#!/usr/bin/env python3
"""Apply the PowerPC CFM Sound Manager callback fix to the patched source."""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-audio-upp-fix.py <Butterscotch source root>")

    source = Path(sys.argv[1]) / "src/audio/macos9/mac_audio_system.c"
    text = source.read_text()

    text = replace_once(
        text,
        "    SndChannelPtr channel;\n"
        "    SndDoubleBufferHeader header;",
        "    SndChannelPtr channel;\n"
        "    SndDoubleBackUPP doubleBackUPP;\n"
        "    SndDoubleBufferHeader header;",
        "audio state UPP field",
    )

    text = replace_once(
        text,
        "static void macDoubleBack(SndChannelPtr channel, SndDoubleBufferPtr buffer) {",
        "static pascal void macDoubleBack(SndChannelPtr channel, SndDoubleBufferPtr buffer) {",
        "Sound Manager callback calling convention",
    )

    text = replace_once(
        text,
        "    mac->header.dbhSampleRate = (Fixed)((UInt32)MAC_AUDIO_OUTPUT_RATE << 16);\n"
        "    mac->header.dbhDoubleBack = (SndDoubleBackUPP)macDoubleBack;",
        "    mac->header.dbhSampleRate = (Fixed)((UInt32)MAC_AUDIO_OUTPUT_RATE << 16);\n"
        "\n"
        "    /* PowerPC CFM callbacks must be wrapped in a Routine Descriptor. */\n"
        "    mac->doubleBackUPP = NewSndDoubleBackUPP(macDoubleBack);\n"
        "    if (mac->doubleBackUPP == NULL) {\n"
        "        fprintf(stderr, \"Mac audio: NewSndDoubleBackUPP failed; continuing without sound\\n\");\n"
        "        MacTrace_stage(\"audio init failed: callback UPP allocation\");\n"
        "        SndDisposeChannel(mac->channel, true);\n"
        "        mac->channel = NULL;\n"
        "        return;\n"
        "    }\n"
        "    mac->header.dbhDoubleBack = mac->doubleBackUPP;",
        "Sound Manager Routine Descriptor creation",
    )

    text = replace_once(
        text,
        "    if (err != noErr) {\n"
        "        fprintf(stderr, \"Mac audio: SndPlayDoubleBuffer failed (%d); continuing without sound\\n\", (int)err);\n"
        "        MacTrace_stage(\"audio init failed: SndPlayDoubleBuffer\");\n"
        "        return;\n"
        "    }",
        "    if (err != noErr) {\n"
        "        fprintf(stderr, \"Mac audio: SndPlayDoubleBuffer failed (%d); continuing without sound\\n\", (int)err);\n"
        "        MacTrace_stage(\"audio init failed: SndPlayDoubleBuffer\");\n"
        "        gMacAudio = NULL;\n"
        "        return;\n"
        "    }",
        "Sound Manager failed-start cleanup",
    )

    text = replace_once(
        text,
        "    if (mac->channel != NULL) SndDisposeChannel(mac->channel, true);\n"
        "    for (i = 0; i < 2; ++i) free(mac->buffers[i]);",
        "    if (mac->channel != NULL) {\n"
        "        SndDisposeChannel(mac->channel, true);\n"
        "        mac->channel = NULL;\n"
        "    }\n"
        "    if (mac->doubleBackUPP != NULL) {\n"
        "        DisposeSndDoubleBackUPP(mac->doubleBackUPP);\n"
        "        mac->doubleBackUPP = NULL;\n"
        "    }\n"
        "    for (i = 0; i < 2; ++i) free(mac->buffers[i]);",
        "Sound Manager Routine Descriptor disposal",
    )

    source.write_text(text)
    print(f"Applied asserted Sound Manager UPP fix to {source}")


if __name__ == "__main__":
    main()
