cmake_minimum_required(VERSION 3.16)
project(ButterscotchMacOS9 C CXX)

# Configure the parent project for a small native PowerPC Classic Mac OS build.
set(PLATFORM macos9 CACHE STRING "" FORCE)
set(DESKTOP_BACKEND macos9 CACHE STRING "" FORCE)
set(AUDIO_BACKEND none CACHE STRING "" FORCE)
set(ENABLE_WAD14 OFF CACHE BOOL "" FORCE)
set(ENABLE_WAD16 ON CACHE BOOL "" FORCE)
set(ENABLE_WAD17 OFF CACHE BOOL "" FORCE)
set(ENABLE_LEGACY_GL ON CACHE BOOL "" FORCE)
set(ENABLE_MODERN_GL OFF CACHE BOOL "" FORCE)
set(ENABLE_VM_GML_PROFILER OFF CACHE BOOL "" FORCE)
set(ENABLE_VM_TRACING OFF CACHE BOOL "" FORCE)
set(ENABLE_VM_OPCODE_PROFILER OFF CACHE BOOL "" FORCE)
set(ENABLE_VM_STUB_LOGS OFF CACHE BOOL "" FORCE)
set(BUTTERSCOTCH_COMMIT_HASH "macos9-port" CACHE STRING "" FORCE)
set(BUTTERSCOTCH_COMMIT_DATE "2026-07-31" CACHE STRING "" FORCE)

# Retro68's stock Carbon template requests only a 1 MB Classic Mac memory
# partition. Use a port-specific template sized for the runner and data.win.
if(CMAKE_SYSTEM_NAME MATCHES "RetroPPC")
    set(REZ_TEMPLATES_PATH "${CMAKE_CURRENT_SOURCE_DIR}/resources")
endif()

add_subdirectory(.. ButterscotchBuild)

# Native Classic Sound Manager backend. It mixes and streams Ogg/WAV assets
# without expanding an entire music track into RAM.
target_sources(butterscotch PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/audio/macos9/mac_audio_system.c"
)
target_include_directories(butterscotch PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/../src/audio/macos9"
)
target_compile_definitions(butterscotch PRIVATE USE_MACOS9_AUDIO)
target_link_libraries(butterscotch SoundLib)
