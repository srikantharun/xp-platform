# linux-ubuntu-gcc.cmake — Ubuntu with the distro's gcc (NEW platform; modelled on
# linux-rhel8-gcc13.cmake). Unlike RHEL's gcc-toolset, Ubuntu's gcc is on the default PATH,
# so there is no /opt/rh prefix to search. Loaded for the project (presets:
# VCPKG_CHAINLOAD_TOOLCHAIN_FILE) and for every vcpkg port (triplets/x64-linux-ubuntu-gcc.cmake)
# so dependencies and project share one compiler.
# UNTESTED on this box (no Ubuntu toolchain image here) — see xp-platform/README.md.

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

# Prefer gcc-13 if present (matches the RHEL target's language level), else the default gcc.
find_program(XP_GCC NAMES gcc-13 gcc REQUIRED)
find_program(XP_GXX NAMES g++-13 g++ REQUIRED)

execute_process(COMMAND "${XP_GXX}" -dumpversion OUTPUT_VARIABLE _xp_ver
                OUTPUT_STRIP_TRAILING_WHITESPACE)
if(_xp_ver VERSION_LESS 12)
  message(FATAL_ERROR "linux-ubuntu-gcc: need GCC >= 12 for C++20, found ${_xp_ver} (${XP_GXX}).")
endif()

set(CMAKE_C_COMPILER "${XP_GCC}")
set(CMAKE_CXX_COMPILER "${XP_GXX}")

# Chainloading replaces vcpkg's default Linux toolchain, which enables PIC; keep it on
# (static deps are linked into the Python extension module).
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
