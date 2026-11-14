# linux-rhel8-gcc13.cmake — RHEL 8 / AlmaLinux 8 with gcc-toolset-13 (docker/toolchain.Dockerfile).
# Loaded for the project (presets: VCPKG_CHAINLOAD_TOOLCHAIN_FILE) and for every vcpkg port
# (triplets/x64-linux-rhel8-gcc13.cmake), so dependencies and project share one compiler.
# gcc-toolset's libstdc++ links symbols newer than GCC 8 statically (libstdc++_nonshared.a)
# and the rest against the system libstdc++.so.6, so binaries run on stock RHEL 8.

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

# Standard gcc-toolset prefix on RHEL-family systems; searched before PATH.
set(XP_GCC_TOOLSET_ROOT "/opt/rh/gcc-toolset-13/root/usr" CACHE PATH "gcc-toolset-13 prefix")
find_program(XP_GCC NAMES gcc HINTS "${XP_GCC_TOOLSET_ROOT}/bin" REQUIRED)
find_program(XP_GXX NAMES g++ HINTS "${XP_GCC_TOOLSET_ROOT}/bin" REQUIRED)

execute_process(COMMAND "${XP_GXX}" -dumpversion OUTPUT_VARIABLE _xp_ver
                OUTPUT_STRIP_TRAILING_WHITESPACE)
if(NOT _xp_ver MATCHES "^13(\\.|$)")
  message(FATAL_ERROR "linux-rhel8-gcc13: expected GCC 13, found ${_xp_ver} (${XP_GXX}). "
                      "Build inside docker/toolchain.Dockerfile (or the devcontainer).")
endif()

set(CMAKE_C_COMPILER "${XP_GCC}")
set(CMAKE_CXX_COMPILER "${XP_GXX}")

# vcpkg's default Linux toolchain enables PIC; chainloading replaces it, so keep that here
# (static deps are linked into the Python extension module).
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
