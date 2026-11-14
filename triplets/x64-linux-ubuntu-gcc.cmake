# vcpkg triplet: x64 Linux (Ubuntu), static libraries, every port compiled with the image's
# gcc via the chainloaded toolchain, so the vcpkg ABI hash keys on that exact compiler.
# NEW platform, modelled on x64-linux-rhel8-gcc13.cmake. UNTESTED on this box.
set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_CMAKE_SYSTEM_NAME Linux)
set(VCPKG_CHAINLOAD_TOOLCHAIN_FILE
    "${CMAKE_CURRENT_LIST_DIR}/../toolchains/linux-ubuntu-gcc.cmake")
# Release-only dependencies: Debug/sanitizer builds link them fine on Linux and halve
# dependency build time.
set(VCPKG_BUILD_TYPE release)
