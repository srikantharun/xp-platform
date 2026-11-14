# Sanitizers.cmake — opt-in runtime sanitizers, selected by a preset via XP_SANITIZERS.
# Values: "" (off), "address;undefined", "thread". ASan and TSan are mutually exclusive.
# Only project targets are instrumented; vcpkg dependencies are not.

set(XP_SANITIZERS "" CACHE STRING "Semicolon list of sanitizers: address, undefined, thread")

if("thread" IN_LIST XP_SANITIZERS AND "address" IN_LIST XP_SANITIZERS)
  message(FATAL_ERROR "XP_SANITIZERS: 'thread' cannot be combined with 'address'")
endif()

function(xp_enable_sanitizers target)
  if(NOT XP_SANITIZERS)
    return()
  endif()

  if(MSVC)
    # MSVC supports AddressSanitizer only.
    if("address" IN_LIST XP_SANITIZERS)
      target_compile_options(${target} PRIVATE /fsanitize=address)
    endif()
    return()
  endif()

  list(JOIN XP_SANITIZERS "," _list)
  target_compile_options(${target} PRIVATE -fsanitize=${_list} -fno-omit-frame-pointer
                                           -fno-sanitize-recover=all)
  target_link_options(${target} PRIVATE -fsanitize=${_list})
endfunction()
