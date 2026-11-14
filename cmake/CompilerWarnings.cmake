# CompilerWarnings.cmake — warning set declared once per compiler family.
# Warnings-as-errors uses CMake's COMPILE_WARNING_AS_ERROR property (maps to
# -Werror / /WX per compiler); override with `--compile-no-warning-as-error`.

option(XP_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" ON)

set(_xp_warnings_msvc
    /W4 /permissive- /w14242 /w14254 /w14263 /w14265 /w14287 /w14296 /w14311 /w14545 /w14546
    /w14547 /w14549 /w14555 /w14619 /w14640 /w14826 /w14905 /w14906 /w14928)

set(_xp_warnings_common # shared by GCC and Clang
    -Wall -Wextra -Wpedantic -Wshadow -Wnon-virtual-dtor -Wold-style-cast -Wcast-align -Wunused
    -Woverloaded-virtual -Wconversion -Wsign-conversion -Wnull-dereference -Wdouble-promotion
    -Wformat=2 -Wimplicit-fallthrough)

set(_xp_warnings_gcc ${_xp_warnings_common} -Wmisleading-indentation -Wduplicated-cond
                     -Wduplicated-branches -Wlogical-op -Wuseless-cast)

set(_xp_warnings_clang ${_xp_warnings_common})

function(xp_set_warnings target)
  target_compile_options(
    ${target}
    PRIVATE $<$<CXX_COMPILER_ID:MSVC>:${_xp_warnings_msvc}>
            $<$<CXX_COMPILER_ID:GNU>:${_xp_warnings_gcc}>
            $<$<CXX_COMPILER_ID:Clang,AppleClang>:${_xp_warnings_clang}>)
  set_target_properties(${target} PROPERTIES COMPILE_WARNING_AS_ERROR ${XP_WARNINGS_AS_ERRORS})
endfunction()
