# GitVersion.cmake — resolve the project version from git tags (included before project()).
# Sets XP_VERSION (numeric X.Y.Z, for project()) and XP_VERSION_FULL (for package names).
# Precedence: -DXP_VERSION=X.Y.Z (CI passes the release tag)
#           > SKBUILD_PROJECT_VERSION (wheel builds: setuptools-scm already read the tag)
#           > `git describe --tags --match v*` (e.g. v0.2.0-3-gabc1234 -> 0.2.0 / 0.2.0-3-gabc1234)
#           > "version-semver" in vcpkg.json (tarball builds without .git).

set(XP_VERSION "" CACHE STRING "Override project version (X.Y.Z); normally derived from git tags")
set(_XP_GITVERSION_DIR "${CMAKE_CURRENT_LIST_DIR}")  # dir of this file (platform/cmake)

function(_xp_version_from_vcpkg out)
  set(_mf "${_XP_GITVERSION_DIR}/../vcpkg.json")            # split layout: platform/vcpkg.json
  if(NOT EXISTS "${_mf}")
    set(_mf "${CMAKE_CURRENT_SOURCE_DIR}/vcpkg.json")        # xp-pricer layout: ./vcpkg.json
  endif()
  file(READ "${_mf}" _manifest)
  string(JSON _v GET "${_manifest}" "version-semver")
  set(${out} "${_v}" PARENT_SCOPE)
endfunction()

if(XP_VERSION)
  set(_full "${XP_VERSION}")
elseif(DEFINED SKBUILD_PROJECT_VERSION)
  # Untagged wheel builds give e.g. 0.1 (full: 0.1.dev4+gabc1234); padded to X.Y.Z below.
  if(DEFINED SKBUILD_PROJECT_VERSION_FULL)
    set(_full "${SKBUILD_PROJECT_VERSION_FULL}")
  else()
    set(_full "${SKBUILD_PROJECT_VERSION}")
  endif()
else()
  find_package(Git QUIET)
  if(Git_FOUND)
    execute_process(
      COMMAND "${GIT_EXECUTABLE}" describe --tags --match "v[0-9]*.[0-9]*.[0-9]*"
      WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
      OUTPUT_VARIABLE _describe
      OUTPUT_STRIP_TRAILING_WHITESPACE
      RESULT_VARIABLE _rc
      ERROR_QUIET)
  endif()
  if(Git_FOUND AND _rc EQUAL 0)
    string(REGEX REPLACE "^v" "" _full "${_describe}")
  else()
    _xp_version_from_vcpkg(_full)
  endif()
endif()

string(REGEX MATCH "^[0-9]+(\\.[0-9]+)?(\\.[0-9]+)?" _numeric "${_full}")
if(NOT _numeric)
  message(FATAL_ERROR "GitVersion: cannot parse a version from '${_full}'")
endif()
string(REGEX MATCHALL "[0-9]+" _parts "${_numeric}")
list(LENGTH _parts _n)
while(_n LESS 3) # project(VERSION) wants X.Y.Z; pad 0.1 -> 0.1.0
  string(APPEND _numeric ".0")
  math(EXPR _n "${_n} + 1")
endwhile()
set(XP_VERSION_NUMERIC "${_numeric}")
set(XP_VERSION_FULL "${_full}")
message(STATUS "xp-pricer version: ${XP_VERSION_FULL}")
