# XpProject.cmake — the project-level build setup every quant version shares.
# Owned by @platform/build-eng (CODEOWNERS). A quant version's root CMakeLists.txt only
# include()s this and calls xp_project(); it carries NO build policy a quant could edit.
# All "how" (standard, warnings, sanitizers, deps, test harness) is decided here, once.
#
# Fixes the bypass where the root CMakeLists.txt was [Code]-owned and full of knobs: a
# quant could have dropped add_compile_options(-O0) in it and only another quant would
# have approved. Now that file is [Platform]-owned and nearly empty.

include_guard(GLOBAL)

# A macro, not a function: project()/enable_testing() must take effect in the caller's
# (top-level) scope, which a function's private scope would swallow.
macro(xp_project name)
  include(GitVersion)                       # version from the git tag vX.Y.Z
  project(${name} VERSION ${XP_VERSION_NUMERIC} LANGUAGES CXX)

  include(GNUInstallDirs)
  option(XP_BUILD_TESTS "Build the Catch2 test suite" ON)

  include(XpPricer)                         # the one call quants get + its guard rails

  find_package(fmt CONFIG REQUIRED)
  find_package(QuantLib CONFIG REQUIRED)

  if(XP_BUILD_TESTS)
    enable_testing()
    find_package(Catch2 3 CONFIG REQUIRED)
    include(Catch)
  endif()
endmacro()
