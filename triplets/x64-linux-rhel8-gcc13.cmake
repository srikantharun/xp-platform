# vcpkg triplet: x64 Linux, static libraries, every port compiled with the image's gcc-toolset-13
# (chainloaded toolchain), so the vcpkg ABI hash keys on that exact compiler.
set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_CMAKE_SYSTEM_NAME Linux)
set(VCPKG_CHAINLOAD_TOOLCHAIN_FILE
    "${CMAKE_CURRENT_LIST_DIR}/../cmake/toolchains/linux-rhel8-gcc13.cmake")
# Release-only dependencies: Debug/sanitizer builds of xp-pricer link them fine on Linux
# (no debug-CRT split as on Windows) and dependency build time halves.
set(VCPKG_BUILD_TYPE release)
