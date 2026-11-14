# vcpkg triplet: x64 Linux, static libraries, every port compiled with the image's clang 17
# against gcc-toolset-13's libstdc++ (chainloaded toolchain).
set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_CMAKE_SYSTEM_NAME Linux)
set(VCPKG_CHAINLOAD_TOOLCHAIN_FILE
    "${CMAKE_CURRENT_LIST_DIR}/../cmake/toolchains/linux-rhel8-clang17.cmake")
set(VCPKG_BUILD_TYPE release) # see x64-linux-rhel8-gcc13.cmake
