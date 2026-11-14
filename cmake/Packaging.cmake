# Packaging.cmake — CPack settings for the `package` presets.
# Archive formats only: no installer tooling required on CI runners.

set(CPACK_PACKAGE_NAME "${PROJECT_NAME}")
set(CPACK_PACKAGE_VERSION "${XP_VERSION_FULL}") # tag-derived, see GitVersion.cmake
set(CPACK_PACKAGE_VENDOR "xp")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "${PROJECT_DESCRIPTION}")
set(CPACK_PACKAGE_DIRECTORY "${PROJECT_BINARY_DIR}/packages")
if(WIN32)
  set(CPACK_GENERATOR "ZIP")
else()
  set(CPACK_GENERATOR "TGZ")
endif()
# Only the runtime/dev components; the Python module ships as a wheel instead.
set(CPACK_COMPONENTS_ALL runtime dev)
set(CPACK_ARCHIVE_COMPONENT_INSTALL OFF)

# Statically linked deps (QuantLib, Boost, fmt) are invisible to binary SBOM scanners, so
# ship vcpkg's per-port SPDX documents and license files inside the archive.
if(DEFINED VCPKG_INSTALLED_DIR AND DEFINED VCPKG_TARGET_TRIPLET)
  install(
    DIRECTORY "${VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/share/"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/${PROJECT_NAME}/third-party"
    COMPONENT runtime
    FILES_MATCHING
    PATTERN "vcpkg.spdx.json"
    PATTERN "copyright")
endif()

include(CPack)
