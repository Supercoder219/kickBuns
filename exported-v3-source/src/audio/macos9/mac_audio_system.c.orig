/*
 * Classic Mac OS Sound Manager backend for Butterscotch.
 *
 * A single Sound Manager double-buffered channel is fed by a software mixer.
 * Ogg Vorbis assets are decoded incrementally from AUDO memory so music does
 * not need to be expanded into a giant PCM allocation on a 128 MB Macintosh.
 */

#define STB_VORBIS_NO_STDIO
#define STB_VORBIS_NO_PUSHDATA_API
#include "stb_vorbis.c"

#include <Types.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <math.h>

#include "mac_audio_system.h"
#include "data_win.h"
#include "file_system.h"
#include "utils.h"
#include "binary_utils.h"
#include "stb_ds.h"
#include "macos9_trace.h"

#define MAC_AUDIO_OUTPUT_RATE 44100
#define MAC_AUDIO_BUFFER_FRAMES 2048
#define MAC_AUDIO_DECODE_FRAMES 1024
#define MAC_AUDIO_MAX_VOICES 12
#define MAC_AUDIO_MAX_STREAMS 16
#define MAC_SOUND_INSTANCE_BASE 100000
#define MAC_AUDIO_STREAM_BASE 300000

typedef enum {
    MAC_SOURCE_NONE = 0,
    MAC_SOURCE_OGG,
    MAC_SOURCE_WAV
} MacSourceType;

typedef struct {
    bool active;
    bool paused;
    bool loop;
    int32_t soundIndex;
    int32_t instanceId;
    int32_t priority;
    float gain;
    float pitch;
    float pan;
    float fadeStart;
    float fadeTarget;
    float fadeRemaining;
    float fadeDuration;

    MacSourceType sourceType;
    const uint8_t* data;
    size_t dataSize;
    uint8_t* ownedData;

    stb_vorbis* vorbis;
    int sourceRate;
    int sourceChannels;
    uint32_t totalFrames;
    uint32_t sourceFramePosition;

    int16_t decodeBuffer[MAC_AUDIO_DECODE_FRAMES * 2];
    int decodeFrames;
    int decodeCursor;

    size_t wavDataOffset;
    size_t wavDataSize;
    uint16_t wavFormat;
    uint16_t wavChannels;
    uint16_t wavBits;
    uint32_t wavRate;
    uint32_t wavFrameCount;
    uint32_t wavFrameCursor;

    bool primed;
    double phase;
    int16_t currentL;
    int16_t currentR;
    int16_t nextL;
    int16_t nextR;
} MacVoice;

typedef struct {
    bool active;
    char* path;
    float gain;
    float pitch;
} MacStream;

typedef struct MacAudioSystem {
    AudioSystem base;
    FileSystem* fileSystem;
    SndChannelPtr channel;
    SndDoubleBufferHeader header;
    SndDoubleBufferPtr buffers[2];
    volatile bool bufferNeedsFill[2];
    bool initialized;
    bool suspended;
    float masterGain;
    MacVoice voices[MAC_AUDIO_MAX_VOICES];
    MacStream streams[MAC_AUDIO_MAX_STREAMS];
} MacAudioSystem;

static MacAudioSystem* gMacAudio = NULL;

static uint16_t readLE16(const uint8_t* p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t readLE32(const uint8_t* p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int16_t clampSample(double value) {
    if (value > 32767.0) return 32767;
    if (value < -32768.0) return -32768;
    return (int16_t)value;
}

static void releaseVoice(MacVoice* voice) {
    if (voice->vorbis != NULL) {
        stb_vorbis_close(voice->vorbis);
    }
    free(voice->ownedData);
    memset(voice, 0, sizeof(*voice));
}

static bool parseWav(MacVoice* voice) {
    const uint8_t* data = voice->data;
    size_t size = voice->dataSize;
    size_t pos = 12;
    bool haveFormat = false;
    bool haveData = false;

    if (size < 12 || memcmp(data, "RIFF", 4) != 0 || memcmp(data + 8, "WAVE", 4) != 0)
        return false;

    while (pos + 8 <= size) {
        const uint8_t* chunk = data + pos;
        uint32_t chunkSize = readLE32(chunk + 4);
        size_t payload = pos + 8;
        size_t next = payload + chunkSize + (chunkSize & 1u);
        if (payload + chunkSize > size) break;

        if (memcmp(chunk, "fmt ", 4) == 0 && chunkSize >= 16) {
            voice->wavFormat = readLE16(data + payload + 0);
            voice->wavChannels = readLE16(data + payload + 2);
            voice->wavRate = readLE32(data + payload + 4);
            voice->wavBits = readLE16(data + payload + 14);
            haveFormat = true;
        } else if (memcmp(chunk, "data", 4) == 0) {
            voice->wavDataOffset = payload;
            voice->wavDataSize = chunkSize;
            haveData = true;
        }
        pos = next;
    }

    if (!haveFormat || !haveData || voice->wavFormat != 1 ||
        (voice->wavChannels != 1 && voice->wavChannels != 2) ||
        (voice->wavBits != 8 && voice->wavBits != 16) || voice->wavRate == 0)
        return false;

    {
        uint32_t bytesPerFrame = (uint32_t)voice->wavChannels * ((uint32_t)voice->wavBits / 8u);
        if (bytesPerFrame == 0) return false;
        voice->wavFrameCount = (uint32_t)(voice->wavDataSize / bytesPerFrame);
    }
    voice->wavFrameCursor = 0;
    voice->sourceRate = (int)voice->wavRate;
    voice->sourceChannels = (int)voice->wavChannels;
    voice->totalFrames = voice->wavFrameCount;
    voice->sourceType = MAC_SOURCE_WAV;
    return true;
}

static bool openSource(MacVoice* voice, const uint8_t* data, size_t size) {
    int error = 0;
    stb_vorbis_info info;

    voice->data = data;
    voice->dataSize = size;
    voice->sourceFramePosition = 0;
    voice->decodeFrames = 0;
    voice->decodeCursor = 0;
    voice->phase = 0.0;
    voice->primed = false;

    if (size >= 4 && memcmp(data, "OggS", 4) == 0) {
        voice->vorbis = stb_vorbis_open_memory(data, (int)size, &error, NULL);
        if (voice->vorbis == NULL) {
            fprintf(stderr, "Mac audio: stb_vorbis_open_memory failed (%d)\n", error);
            return false;
        }
        info = stb_vorbis_get_info(voice->vorbis);
        voice->sourceRate = (int)info.sample_rate;
        voice->sourceChannels = info.channels;
        {
            int total = stb_vorbis_stream_length_in_samples(voice->vorbis);
            voice->totalFrames = total > 0 ? (uint32_t)total : 0;
        }
        voice->sourceType = MAC_SOURCE_OGG;
        return voice->sourceRate > 0;
    }

    if (parseWav(voice)) return true;

    fprintf(stderr, "Mac audio: unsupported asset format (not Ogg Vorbis or PCM WAV)\n");
    return false;
}

static bool rewindVoice(MacVoice* voice) {
    voice->decodeFrames = 0;
    voice->decodeCursor = 0;
    voice->sourceFramePosition = 0;
    voice->phase = 0.0;
    if (voice->sourceType == MAC_SOURCE_OGG) {
        return stb_vorbis_seek_start(voice->vorbis) != 0;
    }
    if (voice->sourceType == MAC_SOURCE_WAV) {
        voice->wavFrameCursor = 0;
        return true;
    }
    return false;
}

static bool readOggFrame(MacVoice* voice, int16_t* left, int16_t* right) {
    if (voice->decodeCursor >= voice->decodeFrames) {
        voice->decodeFrames = stb_vorbis_get_samples_short_interleaved(
            voice->vorbis, 2, voice->decodeBuffer, MAC_AUDIO_DECODE_FRAMES * 2);
        voice->decodeCursor = 0;
        if (voice->decodeFrames <= 0) {
            if (!voice->loop || !rewindVoice(voice)) return false;
            voice->decodeFrames = stb_vorbis_get_samples_short_interleaved(
                voice->vorbis, 2, voice->decodeBuffer, MAC_AUDIO_DECODE_FRAMES * 2);
            if (voice->decodeFrames <= 0) return false;
        }
    }
    *left = voice->decodeBuffer[voice->decodeCursor * 2 + 0];
    *right = voice->decodeBuffer[voice->decodeCursor * 2 + 1];
    voice->decodeCursor++;
    voice->sourceFramePosition++;
    return true;
}

static bool readWavFrame(MacVoice* voice, int16_t* left, int16_t* right) {
    uint32_t bytesPerSample = (uint32_t)voice->wavBits / 8u;
    uint32_t bytesPerFrame = bytesPerSample * (uint32_t)voice->wavChannels;
    const uint8_t* p;
    int16_t l;
    int16_t r;

    if (voice->wavFrameCursor >= voice->wavFrameCount) {
        if (!voice->loop || !rewindVoice(voice)) return false;
    }
    p = voice->data + voice->wavDataOffset + (size_t)voice->wavFrameCursor * bytesPerFrame;
    if (voice->wavBits == 16) {
        l = (int16_t)readLE16(p);
        r = (voice->wavChannels == 2) ? (int16_t)readLE16(p + 2) : l;
    } else {
        l = (int16_t)(((int)p[0] - 128) << 8);
        r = (voice->wavChannels == 2) ? (int16_t)(((int)p[1] - 128) << 8) : l;
    }
    voice->wavFrameCursor++;
    voice->sourceFramePosition = voice->wavFrameCursor;
    *left = l;
    *right = r;
    return true;
}

static bool readSourceFrame(MacVoice* voice, int16_t* left, int16_t* right) {
    if (voice->sourceType == MAC_SOURCE_OGG) return readOggFrame(voice, left, right);
    if (voice->sourceType == MAC_SOURCE_WAV) return readWavFrame(voice, left, right);
    return false;
}

static bool primeVoice(MacVoice* voice) {
    if (!readSourceFrame(voice, &voice->currentL, &voice->currentR)) return false;
    if (!readSourceFrame(voice, &voice->nextL, &voice->nextR)) {
        voice->nextL = voice->currentL;
        voice->nextR = voice->currentR;
    }
    voice->primed = true;
    return true;
}

static bool sampleVoice(MacVoice* voice, double* left, double* right) {
    double ratio;
    double frac;

    if (!voice->active || voice->paused) {
        *left = 0.0;
        *right = 0.0;
        return voice->active;
    }
    if (!voice->primed && !primeVoice(voice)) {
        voice->active = false;
        *left = 0.0;
        *right = 0.0;
        return false;
    }

    frac = voice->phase;
    *left = (double)voice->currentL + ((double)voice->nextL - (double)voice->currentL) * frac;
    *right = (double)voice->currentR + ((double)voice->nextR - (double)voice->currentR) * frac;

    ratio = ((double)voice->sourceRate * (double)voice->pitch) / (double)MAC_AUDIO_OUTPUT_RATE;
    if (ratio < 0.05) ratio = 0.05;
    if (ratio > 4.0) ratio = 4.0;
    voice->phase += ratio;
    while (voice->phase >= 1.0) {
        voice->currentL = voice->nextL;
        voice->currentR = voice->nextR;
        if (!readSourceFrame(voice, &voice->nextL, &voice->nextR)) {
            voice->active = false;
            voice->nextL = voice->currentL;
            voice->nextR = voice->currentR;
            break;
        }
        voice->phase -= 1.0;
    }
    return true;
}

static void fillOutputBuffer(MacAudioSystem* mac, SndDoubleBufferPtr buffer) {
    int16_t* output = (int16_t*)buffer->dbSoundData;
    int frame;
    for (frame = 0; frame < MAC_AUDIO_BUFFER_FRAMES; ++frame) {
        double mixL = 0.0;
        double mixR = 0.0;
        int i;
        if (!mac->suspended) {
            for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i) {
                MacVoice* voice = &mac->voices[i];
                double sampleL;
                double sampleR;
                double gainL;
                double gainR;
                if (!voice->active || voice->paused) continue;
                if (!sampleVoice(voice, &sampleL, &sampleR)) continue;
                gainL = (double)voice->gain;
                gainR = (double)voice->gain;
                if (voice->pan > 0.0f) gainL *= (double)(1.0f - voice->pan);
                if (voice->pan < 0.0f) gainR *= (double)(1.0f + voice->pan);
                mixL += sampleL * gainL;
                mixR += sampleR * gainR;
            }
        }
        mixL *= (double)mac->masterGain;
        mixR *= (double)mac->masterGain;
        output[frame * 2 + 0] = clampSample(mixL);
        output[frame * 2 + 1] = clampSample(mixR);
    }
    buffer->dbNumFrames = MAC_AUDIO_BUFFER_FRAMES;
    buffer->dbFlags = dbBufferReady;
}

static void macDoubleBack(SndChannelPtr channel, SndDoubleBufferPtr buffer) {
    MacAudioSystem* mac = gMacAudio;
    (void)channel;
    if (mac == NULL || buffer == NULL) return;
    buffer->dbFlags = 0;
    if (buffer == mac->buffers[0]) mac->bufferNeedsFill[0] = true;
    if (buffer == mac->buffers[1]) mac->bufferNeedsFill[1] = true;
}

static uint8_t* loadFileBytes(const char* path, size_t* outSize) {
    FILE* file;
    long length;
    uint8_t* data;
    size_t read;
    *outSize = 0;
    file = fopen(path, "rb");
    if (file == NULL) return NULL;
    fseek(file, 0, SEEK_END);
    length = ftell(file);
    fseek(file, 0, SEEK_SET);
    if (length <= 0) { fclose(file); return NULL; }
    data = (uint8_t*)malloc((size_t)length);
    if (data == NULL) { fclose(file); return NULL; }
    read = fread(data, 1, (size_t)length, file);
    fclose(file);
    if (read != (size_t)length) { free(data); return NULL; }
    *outSize = (size_t)length;
    return data;
}

static MacVoice* findVoiceByInstance(MacAudioSystem* mac, int32_t instanceId) {
    int slot = (int)(instanceId - MAC_SOUND_INSTANCE_BASE);
    if (slot < 0 || slot >= MAC_AUDIO_MAX_VOICES) return NULL;
    if (!mac->voices[slot].active || mac->voices[slot].instanceId != instanceId) return NULL;
    return &mac->voices[slot];
}

static MacVoice* findFreeVoice(MacAudioSystem* mac, int32_t priority) {
    MacVoice* lowest = NULL;
    int i;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i) {
        if (!mac->voices[i].active) return &mac->voices[i];
        if (lowest == NULL || mac->voices[i].priority < lowest->priority)
            lowest = &mac->voices[i];
    }
    if (lowest != NULL && priority >= lowest->priority) {
        releaseVoice(lowest);
        return lowest;
    }
    return NULL;
}

static char* resolveExternalPath(MacAudioSystem* mac, Sound* sound) {
    char filename[512];
    bool hasExtension;
    if (sound->file == NULL || sound->file[0] == '\0') return NULL;
    hasExtension = strchr(sound->file, '.') != NULL;
    if (hasExtension) snprintf(filename, sizeof(filename), "%s", sound->file);
    else snprintf(filename, sizeof(filename), "%s.ogg", sound->file);
    return mac->fileSystem->vtable->resolvePath(mac->fileSystem, filename);
}

static void macInit(AudioSystem* audio, DataWin* dataWin, FileSystem* fileSystem) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    size_t bufferBytes = offsetof(SndDoubleBuffer, dbSoundData) +
                         MAC_AUDIO_BUFFER_FRAMES * 2 * sizeof(int16_t);
    OSErr err;
    int i;

    mac->base.dw = dataWin;
    arrput(mac->base.audioGroups, dataWin);
    mac->fileSystem = fileSystem;
    mac->masterGain = 1.0f;
    mac->suspended = false;
    MacTrace_stage("audio init: Sound Manager channel");

    err = SndNewChannel(&mac->channel, sampledSynth, 0, NULL);
    if (err != noErr || mac->channel == NULL) {
        fprintf(stderr, "Mac audio: SndNewChannel failed (%d); continuing without sound\n", (int)err);
        MacTrace_stage("audio init failed: SndNewChannel");
        return;
    }

    memset(&mac->header, 0, sizeof(mac->header));
    mac->header.dbhNumChannels = 2;
    mac->header.dbhSampleSize = 16;
    mac->header.dbhCompressionID = 0;
    mac->header.dbhPacketSize = 0;
    mac->header.dbhSampleRate = (Fixed)((UInt32)MAC_AUDIO_OUTPUT_RATE << 16);
    mac->header.dbhDoubleBack = (SndDoubleBackUPP)macDoubleBack;

    for (i = 0; i < 2; ++i) {
        mac->buffers[i] = (SndDoubleBufferPtr)calloc(1, bufferBytes);
        if (mac->buffers[i] == NULL) {
            fprintf(stderr, "Mac audio: output buffer allocation failed\n");
            MacTrace_stage("audio init failed: buffer allocation");
            return;
        }
        mac->header.dbhBufferPtr[i] = mac->buffers[i];
        mac->bufferNeedsFill[i] = false;
        fillOutputBuffer(mac, mac->buffers[i]);
    }

    gMacAudio = mac;
    err = SndPlayDoubleBuffer(mac->channel, &mac->header);
    if (err != noErr) {
        fprintf(stderr, "Mac audio: SndPlayDoubleBuffer failed (%d); continuing without sound\n", (int)err);
        MacTrace_stage("audio init failed: SndPlayDoubleBuffer");
        return;
    }
    mac->initialized = true;
    fprintf(stderr, "Mac audio: Sound Manager mixer initialized at %d Hz\n", MAC_AUDIO_OUTPUT_RATE);
    MacTrace_stage("audio init complete");
}

static void macDestroy(AudioSystem* audio) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    gMacAudio = NULL;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i) releaseVoice(&mac->voices[i]);
    if (mac->channel != NULL) SndDisposeChannel(mac->channel, true);
    for (i = 0; i < 2; ++i) free(mac->buffers[i]);
    for (i = 0; i < MAC_AUDIO_MAX_STREAMS; ++i) free(mac->streams[i].path);
    if (arrlen(mac->base.audioGroups) > 1) {
        for (i = 1; i < (int)arrlen(mac->base.audioGroups); ++i)
            DataWin_free(mac->base.audioGroups[i]);
    }
    arrfree(mac->base.audioGroups);
    free(mac);
}

static void macUpdate(AudioSystem* audio, float deltaTime) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i) {
        MacVoice* voice = &mac->voices[i];
        if (!voice->active) {
            if (voice->sourceType != MAC_SOURCE_NONE || voice->ownedData != NULL || voice->vorbis != NULL)
                releaseVoice(voice);
            continue;
        }
        if (voice->fadeRemaining > 0.0f) {
            float elapsed;
            float t;
            voice->fadeRemaining -= deltaTime;
            if (voice->fadeRemaining < 0.0f) voice->fadeRemaining = 0.0f;
            elapsed = voice->fadeDuration - voice->fadeRemaining;
            t = voice->fadeDuration > 0.0f ? elapsed / voice->fadeDuration : 1.0f;
            voice->gain = voice->fadeStart + (voice->fadeTarget - voice->fadeStart) * t;
        }
    }
    if (!mac->initialized) return;
    for (i = 0; i < 2; ++i) {
        if (mac->bufferNeedsFill[i]) {
            mac->bufferNeedsFill[i] = false;
            fillOutputBuffer(mac, mac->buffers[i]);
        }
    }
}

static bool prepareVoiceFromBytes(MacVoice* voice, const uint8_t* data, size_t size,
                                  uint8_t* ownedData) {
    voice->ownedData = ownedData;
    if (!openSource(voice, data, size)) {
        releaseVoice(voice);
        return false;
    }
    return true;
}

static int32_t macPlaySound(AudioSystem* audio, int32_t soundIndex, int32_t priority, bool loop) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    MacVoice* voice;
    const uint8_t* data = NULL;
    size_t dataSize = 0;
    uint8_t* ownedData = NULL;
    float gain = 1.0f;
    float pitch = 1.0f;
    float pan = 0.0f;
    int slotIndex;

    voice = findFreeVoice(mac, priority);
    if (voice == NULL) return -1;
    memset(voice, 0, sizeof(*voice));

    if (soundIndex >= MAC_AUDIO_STREAM_BASE) {
        int streamSlot = (int)(soundIndex - MAC_AUDIO_STREAM_BASE);
        if (streamSlot < 0 || streamSlot >= MAC_AUDIO_MAX_STREAMS || !mac->streams[streamSlot].active)
            return -1;
        ownedData = loadFileBytes(mac->streams[streamSlot].path, &dataSize);
        data = ownedData;
        gain = mac->streams[streamSlot].gain;
        pitch = mac->streams[streamSlot].pitch;
    } else {
        DataWin* root = mac->base.audioGroups[0];
        Sound* sound;
        bool isRegular;
        bool inAudo;
        if (soundIndex < 0 || (uint32_t)soundIndex >= root->sond.count) return -1;
        sound = &root->sond.sounds[soundIndex];
        gain = sound->volume;
        pitch = sound->pitch;
        pan = sound->pan;
        if (pitch <= 0.0f) pitch = 1.0f;

        while (sound->audioGroup >= (int32_t)arrlen(mac->base.audioGroups)) {
            audio->vtable->groupLoad(audio, (int32_t)arrlen(mac->base.audioGroups));
            if (sound->audioGroup >= (int32_t)arrlen(mac->base.audioGroups)) return -1;
        }

        isRegular = (sound->flags & AUDIO_ENTRY_FLAG_REGULAR) == AUDIO_ENTRY_FLAG_REGULAR;
        inAudo = !isRegular || (sound->flags & AUDIO_ENTRY_FLAG_IS_EMBEDDED) != 0 ||
                 (sound->flags & AUDIO_ENTRY_FLAG_IS_COMPRESSED) != 0;
        if (inAudo) {
            DataWin* group = mac->base.audioGroups[sound->audioGroup];
            AudioEntry* entry;
            if (sound->audioFile < 0 || (uint32_t)sound->audioFile >= group->audo.count) return -1;
            DataWin_loadAudoIfNeeded(group, (uint32_t)sound->audioFile);
            entry = &group->audo.entries[sound->audioFile];
            data = entry->data;
            dataSize = entry->dataSize;
        } else {
            char* path = resolveExternalPath(mac, sound);
            if (path == NULL) return -1;
            ownedData = loadFileBytes(path, &dataSize);
            free(path);
            data = ownedData;
        }
    }

    if (data == NULL || dataSize == 0 || !prepareVoiceFromBytes(voice, data, dataSize, ownedData))
        return -1;

    slotIndex = (int)(voice - mac->voices);
    voice->active = true;
    voice->paused = false;
    voice->loop = loop;
    voice->soundIndex = soundIndex;
    voice->instanceId = MAC_SOUND_INSTANCE_BASE + slotIndex;
    voice->priority = priority;
    voice->gain = gain;
    voice->pitch = pitch;
    voice->pan = pan;
    if (!primeVoice(voice)) {
        releaseVoice(voice);
        return -1;
    }
    return voice->instanceId;
}

static void forMatchingVoices(MacAudioSystem* mac, int32_t soundOrInstance,
                              void (*fn)(MacVoice*)) {
    int i;
    if (soundOrInstance >= MAC_SOUND_INSTANCE_BASE && soundOrInstance < MAC_AUDIO_STREAM_BASE) {
        MacVoice* voice = findVoiceByInstance(mac, soundOrInstance);
        if (voice != NULL) fn(voice);
        return;
    }
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i) {
        if (mac->voices[i].active && mac->voices[i].soundIndex == soundOrInstance)
            fn(&mac->voices[i]);
    }
}

static void stopVoice(MacVoice* voice) { releaseVoice(voice); }
static void pauseVoice(MacVoice* voice) { voice->paused = true; }
static void resumeVoice(MacVoice* voice) { voice->paused = false; }

static void macStopSound(AudioSystem* audio, int32_t soundOrInstance) {
    forMatchingVoices((MacAudioSystem*)audio, soundOrInstance, stopVoice);
}

static void macStopAll(AudioSystem* audio) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i) releaseVoice(&mac->voices[i]);
}

static bool macIsPlaying(AudioSystem* audio, int32_t soundOrInstance) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    if (soundOrInstance >= MAC_SOUND_INSTANCE_BASE && soundOrInstance < MAC_AUDIO_STREAM_BASE) {
        MacVoice* voice = findVoiceByInstance(mac, soundOrInstance);
        return voice != NULL && voice->active && !voice->paused;
    }
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i)
        if (mac->voices[i].active && !mac->voices[i].paused && mac->voices[i].soundIndex == soundOrInstance)
            return true;
    return false;
}

static void macPauseSound(AudioSystem* audio, int32_t soundOrInstance) {
    forMatchingVoices((MacAudioSystem*)audio, soundOrInstance, pauseVoice);
}

static void macResumeSound(AudioSystem* audio, int32_t soundOrInstance) {
    forMatchingVoices((MacAudioSystem*)audio, soundOrInstance, resumeVoice);
}

static void macPauseAll(AudioSystem* audio) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i) if (mac->voices[i].active) mac->voices[i].paused = true;
}

static void macResumeAll(AudioSystem* audio) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i) if (mac->voices[i].active) mac->voices[i].paused = false;
}

static void macSuspend(AudioSystem* audio) { ((MacAudioSystem*)audio)->suspended = true; }
static void macResume(AudioSystem* audio) { ((MacAudioSystem*)audio)->suspended = false; }

static void setVoiceGainDirect(MacVoice* voice, float gain, uint32_t timeMs) {
    if (timeMs == 0) {
        voice->gain = gain;
        voice->fadeRemaining = 0.0f;
        return;
    }
    voice->fadeStart = voice->gain;
    voice->fadeTarget = gain;
    voice->fadeDuration = (float)timeMs / 1000.0f;
    voice->fadeRemaining = voice->fadeDuration;
}

static float macGetSoundGain(AudioSystem* audio, int32_t soundOrInstance) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    MacVoice* voice = findVoiceByInstance(mac, soundOrInstance);
    if (voice != NULL) return voice->gain;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i)
        if (mac->voices[i].active && mac->voices[i].soundIndex == soundOrInstance) return mac->voices[i].gain;
    return 0.0f;
}

static void macSetSoundGain(AudioSystem* audio, int32_t soundOrInstance, float gain, uint32_t timeMs) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    MacVoice* voice;
    if (soundOrInstance >= MAC_AUDIO_STREAM_BASE) {
        int streamSlot = (int)(soundOrInstance - MAC_AUDIO_STREAM_BASE);
        if (streamSlot >= 0 && streamSlot < MAC_AUDIO_MAX_STREAMS && mac->streams[streamSlot].active)
            mac->streams[streamSlot].gain = gain;
    }
    voice = findVoiceByInstance(mac, soundOrInstance);
    if (voice != NULL) { setVoiceGainDirect(voice, gain, timeMs); return; }
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i)
        if (mac->voices[i].active && mac->voices[i].soundIndex == soundOrInstance)
            setVoiceGainDirect(&mac->voices[i], gain, timeMs);
}

static void macSetSoundPitch(AudioSystem* audio, int32_t soundOrInstance, float pitch) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    MacVoice* voice;
    if (pitch <= 0.0f) pitch = 0.05f;
    if (soundOrInstance >= MAC_AUDIO_STREAM_BASE) {
        int streamSlot = (int)(soundOrInstance - MAC_AUDIO_STREAM_BASE);
        if (streamSlot >= 0 && streamSlot < MAC_AUDIO_MAX_STREAMS && mac->streams[streamSlot].active)
            mac->streams[streamSlot].pitch = pitch;
    }
    voice = findVoiceByInstance(mac, soundOrInstance);
    if (voice != NULL) { voice->pitch = pitch; return; }
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i)
        if (mac->voices[i].active && mac->voices[i].soundIndex == soundOrInstance)
            mac->voices[i].pitch = pitch;
}

static float macGetSoundPitch(AudioSystem* audio, int32_t soundOrInstance) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    MacVoice* voice = findVoiceByInstance(mac, soundOrInstance);
    if (voice != NULL) return voice->pitch;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i)
        if (mac->voices[i].active && mac->voices[i].soundIndex == soundOrInstance) return mac->voices[i].pitch;
    return 1.0f;
}

static float voicePosition(const MacVoice* voice) {
    if (voice->sourceRate <= 0) return 0.0f;
    return (float)voice->sourceFramePosition / (float)voice->sourceRate;
}

static float macGetTrackPosition(AudioSystem* audio, int32_t soundOrInstance) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    MacVoice* voice = findVoiceByInstance(mac, soundOrInstance);
    if (voice != NULL) return voicePosition(voice);
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i)
        if (mac->voices[i].active && mac->voices[i].soundIndex == soundOrInstance)
            return voicePosition(&mac->voices[i]);
    return 0.0f;
}

static void seekVoice(MacVoice* voice, float seconds) {
    uint32_t frame;
    if (seconds < 0.0f) seconds = 0.0f;
    frame = (uint32_t)(seconds * (float)voice->sourceRate);
    if (voice->totalFrames > 0 && frame >= voice->totalFrames) frame = voice->totalFrames - 1;
    voice->decodeFrames = 0;
    voice->decodeCursor = 0;
    voice->phase = 0.0;
    voice->primed = false;
    if (voice->sourceType == MAC_SOURCE_OGG) {
        if (!stb_vorbis_seek(voice->vorbis, frame)) stb_vorbis_seek_start(voice->vorbis);
    } else if (voice->sourceType == MAC_SOURCE_WAV) {
        voice->wavFrameCursor = frame;
    }
    voice->sourceFramePosition = frame;
    primeVoice(voice);
}

static void macSetTrackPosition(AudioSystem* audio, int32_t soundOrInstance, float seconds) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    MacVoice* voice = findVoiceByInstance(mac, soundOrInstance);
    if (voice != NULL) { seekVoice(voice, seconds); return; }
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i)
        if (mac->voices[i].active && mac->voices[i].soundIndex == soundOrInstance)
            seekVoice(&mac->voices[i], seconds);
}

static float macGetSoundLength(AudioSystem* audio, int32_t soundOrInstance) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    MacVoice* voice = findVoiceByInstance(mac, soundOrInstance);
    if (voice != NULL && voice->sourceRate > 0)
        return (float)voice->totalFrames / (float)voice->sourceRate;
    for (i = 0; i < MAC_AUDIO_MAX_VOICES; ++i)
        if (mac->voices[i].active && mac->voices[i].soundIndex == soundOrInstance && mac->voices[i].sourceRate > 0)
            return (float)mac->voices[i].totalFrames / (float)mac->voices[i].sourceRate;
    return 1.0f;
}

static void macSetMasterGain(AudioSystem* audio, float gain) { ((MacAudioSystem*)audio)->masterGain = gain; }
static void macSetMasterGainForListener(AudioSystem* audio, float gain, int32_t listenerId) {
    (void)listenerId;
    ((MacAudioSystem*)audio)->masterGain = gain;
}
static void macSetChannelCount(AudioSystem* audio, int32_t count) { (void)audio; (void)count; }

static void macGroupLoad(AudioSystem* audio, int32_t groupIndex) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    DataWin* root = audio->dw;
    char filename[256];
    char* resolved;
    DataWinParserOptions options;
    DataWin* group;
    if (groupIndex <= 0 || (uint32_t)groupIndex >= root->agrp.count) return;
    if (groupIndex < (int32_t)arrlen(audio->audioGroups)) return;
    if (root->agrp.audioGroups[groupIndex].path != NULL)
        snprintf(filename, sizeof(filename), "%s", root->agrp.audioGroups[groupIndex].path);
    else
        snprintf(filename, sizeof(filename), "audiogroup%d.dat", (int)groupIndex);
    if (!mac->fileSystem->vtable->fileExists(mac->fileSystem, filename)) return;
    resolved = mac->fileSystem->vtable->resolvePath(mac->fileSystem, filename);
    if (resolved == NULL) return;
    memset(&options, 0, sizeof(options));
    options.parseAudo = true;
    options.lazyLoadAudio = root->lazyLoadAudio;
    options.loadType = DATAWINLOADTYPE_LOAD_PER_CHUNK;
    group = DataWin_parse(resolved, options);
    free(resolved);
    while ((int32_t)arrlen(audio->audioGroups) < groupIndex) {
        DataWin* empty = (DataWin*)safeCalloc(1, sizeof(DataWin));
        arrput(audio->audioGroups, empty);
    }
    arrput(audio->audioGroups, group);
}

static bool macGroupIsLoaded(AudioSystem* audio, int32_t groupIndex) {
    return groupIndex >= 0 && groupIndex < (int32_t)arrlen(audio->audioGroups);
}

static int32_t macCreateStream(AudioSystem* audio, const char* filename) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int i;
    char* resolved;
    for (i = 0; i < MAC_AUDIO_MAX_STREAMS; ++i) if (!mac->streams[i].active) break;
    if (i == MAC_AUDIO_MAX_STREAMS) return -1;
    resolved = mac->fileSystem->vtable->resolvePath(mac->fileSystem, filename);
    if (resolved == NULL) return -1;
    mac->streams[i].active = true;
    mac->streams[i].path = resolved;
    mac->streams[i].gain = 1.0f;
    mac->streams[i].pitch = 1.0f;
    return MAC_AUDIO_STREAM_BASE + i;
}

static bool macDestroyStream(AudioSystem* audio, int32_t streamIndex) {
    MacAudioSystem* mac = (MacAudioSystem*)audio;
    int slot = (int)(streamIndex - MAC_AUDIO_STREAM_BASE);
    if (slot < 0 || slot >= MAC_AUDIO_MAX_STREAMS || !mac->streams[slot].active) return false;
    macStopSound(audio, streamIndex);
    free(mac->streams[slot].path);
    memset(&mac->streams[slot], 0, sizeof(mac->streams[slot]));
    return true;
}

static AudioSystemVtable macVtable = {
    macInit,
    macDestroy,
    macUpdate,
    macPlaySound,
    macStopSound,
    macStopAll,
    macIsPlaying,
    macPauseSound,
    macResumeSound,
    macPauseAll,
    macResumeAll,
    macSuspend,
    macResume,
    macSetSoundGain,
    macGetSoundGain,
    macSetSoundPitch,
    macGetSoundPitch,
    macGetTrackPosition,
    macSetTrackPosition,
    macGetSoundLength,
    macSetMasterGain,
    macSetMasterGainForListener,
    macSetChannelCount,
    macGroupLoad,
    macGroupIsLoaded,
    macCreateStream,
    macDestroyStream
};

AudioSystem* MacAudioSystem_create(void) {
    MacAudioSystem* mac = (MacAudioSystem*)safeCalloc(1, sizeof(MacAudioSystem));
    mac->base.vtable = &macVtable;
    mac->masterGain = 1.0f;
    return (AudioSystem*)mac;
}
