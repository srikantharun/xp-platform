# vcpkg triplet for the Windows trader CLI: MSVC toolset v143 (Visual Studio 2022),
# static libraries, dynamic CRT.
#
# Dynamic CRT = /MD (/MDd in Debug). xp-cli.exe then imports vcruntime140.dll and
# msvcp140.dll (the UCRT ships with Windows 10+). Target desktops need the
# "Microsoft Visual C++ 2015-2022 Redistributable (x64)" at least as new as the toolset used,
# or the DLLs deployed next to the exe (CMake's InstallRequiredSystemLibraries can package
# them). /MD is chosen over /MT so every module shares one heap and one CRT state, and CRT
# security fixes arrive through Windows Update instead of a rebuild.
# QuantLib's port is static-only on Windows, hence static libraries with the dynamic CRT.
set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_PLATFORM_TOOLSET v143)
# Debug and Release are both built: /MDd and /MD objects cannot be mixed at link time.
