# XpPricer.cmake — the ONLY CMake call a quant developer makes.
#
#   xp_pricer(
#     NAME     black_scholes          # target, aliased xp::black_scholes
#     SOURCES  pricer.cpp             # implementation files (relative to this folder)
#     HEADERS  include/xp/pricer.hpp  # public headers, installed under include/xp/
#     TESTS    test_pricer.cpp        # Catch2 tests; built with the platform FP-trap main
#     USES     QuantLib::QuantLib     # APPROVED libraries only (see XP_APPROVED_LIBS)
#   )
#
# A quant says WHAT; this function decides HOW (C++20, warnings-as-errors, sanitizers,
# clang-tidy, the FP-trap test harness, the install layout) via xp_configure_target().
#
# There is deliberately NO FLAGS / OPTIONS / COMPILE_DEFINITIONS / COMPILE_OPTIONS
# parameter, so nothing a quant writes here reaches the compiler command line: no -O0,
# no -ffast-math. USES is checked against the approved-library allow-list. The function
# lives in the platform repo (build-eng owns it, pinned by tag); quants call it, never edit
# it. The allow-list CI guard (guards/check_pricer_cmakelists.py) ensures a pricer's
# CMakeLists.txt contains ONLY this call — the one build file CODEOWNERS leaves with quants.

include_guard(GLOBAL)

include(XpTarget)        # xp_configure_target: C++20, warnings, sanitizers, clang-tidy
include(Quarantine)      # flaky-test quarantine for generated test targets

# Platform FP-trap main, compiled into every pricer's tests so NaN/Inf arithmetic aborts
# the test instead of returning a silently wrong price.
set(XP_FP_TRAPS_MAIN "${CMAKE_CURRENT_LIST_DIR}/../testing/fp_traps_main.cpp"
    CACHE FILEPATH "platform FP-trap test main")

# Libraries a pricer may link. Extending this is a build-engineer change to the platform
# repo (a reviewed MR + new tag), never a quant's.
set(XP_APPROVED_LIBS
    "QuantLib::QuantLib"
    "fmt::fmt"
    CACHE INTERNAL "libraries a pricer may link via xp_pricer(USES ...)")

function(xp_pricer)
  cmake_parse_arguments(P "" "NAME" "SOURCES;HEADERS;TESTS;USES" ${ARGN})

  if(NOT P_NAME)
    message(FATAL_ERROR "xp_pricer: NAME is required")
  endif()
  if(NOT P_SOURCES)
    message(FATAL_ERROR "xp_pricer(${P_NAME}): SOURCES is required")
  endif()
  if(P_UNPARSED_ARGUMENTS)
    message(FATAL_ERROR
      "xp_pricer(${P_NAME}): unexpected argument(s) '${P_UNPARSED_ARGUMENTS}'. The only "
      "keywords are NAME, SOURCES, HEADERS, TESTS, USES — there is no way to pass compiler "
      "flags. How it builds is decided by the platform, not here.")
  endif()

  foreach(lib IN LISTS P_USES)
    if(NOT lib IN_LIST XP_APPROVED_LIBS)
      message(FATAL_ERROR
        "xp_pricer(${P_NAME}): '${lib}' is not an approved library.\n"
        "  Approved: ${XP_APPROVED_LIBS}\n"
        "  To add one, open an MR on xp-platform (build-eng owns the allow-list) and cut a tag.")
    endif()
  endforeach()

  add_library(${P_NAME} ${P_SOURCES})
  add_library(xp::${P_NAME} ALIAS ${P_NAME})
  # Self-contained pricer folder: its own include/ holds xp/<name>.hpp.
  target_include_directories(${P_NAME}
    PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
           $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
  if(P_USES)
    target_link_libraries(${P_NAME} PRIVATE ${P_USES})
  endif()
  xp_configure_target(${P_NAME})

  install(TARGETS ${P_NAME} EXPORT xp-targets)
  foreach(h IN LISTS P_HEADERS)
    install(FILES "${h}" DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/xp")
  endforeach()

  if(P_TESTS AND XP_BUILD_TESTS)
    set(_tests ${P_NAME}_tests)
    add_executable(${_tests} "${XP_FP_TRAPS_MAIN}" ${P_TESTS})
    target_link_libraries(${_tests} PRIVATE xp::${P_NAME} Catch2::Catch2 ${P_USES})
    xp_configure_target(${_tests})
    catch_discover_tests(${_tests} TEST_PREFIX "unit.${P_NAME}." DISCOVERY_MODE PRE_TEST)
  endif()
endfunction()
