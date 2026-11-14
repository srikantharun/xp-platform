# linux-rhel8-clang17.cmake — RHEL 8 / AlmaLinux 8 with clang 17 (llvm-toolset) on top of
# gcc-toolset-13's libstdc++ (docker/toolchain.Dockerfile). Same role as the gcc13 file:
# project via presets, ports via triplets/x64-linux-rhel8-clang17.cmake.

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

find_program(XP_CLANG NAMES clang-17 clang REQUIRED)
find_program(XP_CLANGXX NAMES clang++-17 clang++ REQUIRED)

execute_process(COMMAND "${XP_CLANGXX}" -dumpversion OUTPUT_VARIABLE _xp_ver
                OUTPUT_STRIP_TRAILING_WHITESPACE)
if(NOT _xp_ver MATCHES "^17\\.")
  message(FATAL_ERROR "linux-rhel8-clang17: expected clang 17, found ${_xp_ver} (${XP_CLANGXX}). "
                      "Build inside docker/toolchain.Dockerfile (or the devcontainer).")
endif()

set(CMAKE_C_COMPILER "${XP_CLANG}")
set(CMAKE_CXX_COMPILER "${XP_CLANGXX}")
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Without this, clang on RHEL 8 picks the system GCC 8 libstdc++ (incomplete C++20 library).
# Pointing it at gcc-toolset-13 gives the same headers/ABI as the gcc13 toolchain while
# keeping the glibc 2.28 / system libstdc++.so.6 runtime floor.
set(XP_GCC_TOOLSET_ROOT "/opt/rh/gcc-toolset-13/root/usr" CACHE PATH "gcc-toolset-13 prefix")
if(EXISTS "${XP_GCC_TOOLSET_ROOT}/lib/gcc/x86_64-redhat-linux/13")
  foreach(_xp_var CMAKE_C_FLAGS_INIT CMAKE_CXX_FLAGS_INIT CMAKE_EXE_LINKER_FLAGS_INIT
                  CMAKE_SHARED_LINKER_FLAGS_INIT CMAKE_MODULE_LINKER_FLAGS_INIT)
    string(APPEND ${_xp_var} " --gcc-toolchain=${XP_GCC_TOOLSET_ROOT}")
  endforeach()
endif()
