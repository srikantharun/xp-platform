# StaticAnalyzers.cmake — optional clang-tidy / cppcheck run as part of compilation.
# Off by default so the core build has no extra tool requirements.

option(XP_ENABLE_CLANG_TIDY "Run clang-tidy on project sources while compiling" OFF)
option(XP_ENABLE_CPPCHECK "Run cppcheck on project sources while compiling" OFF)

if(XP_ENABLE_CLANG_TIDY)
  find_program(XP_CLANG_TIDY_EXE NAMES clang-tidy REQUIRED)
endif()
if(XP_ENABLE_CPPCHECK)
  find_program(XP_CPPCHECK_EXE NAMES cppcheck REQUIRED)
endif()

function(xp_enable_static_analyzers target)
  if(XP_ENABLE_CLANG_TIDY)
    # Checks come from the nearest .clang-tidy file, not from here.
    set_target_properties(${target} PROPERTIES CXX_CLANG_TIDY
                                               "${XP_CLANG_TIDY_EXE};--warnings-as-errors=*")
  endif()
  if(XP_ENABLE_CPPCHECK)
    set_target_properties(
      ${target}
      PROPERTIES
        CXX_CPPCHECK
        "${XP_CPPCHECK_EXE};--enable=warning,performance,portability;--inline-suppr;--error-exitcode=1;--suppress=missingIncludeSystem"
    )
  endif()
endfunction()
