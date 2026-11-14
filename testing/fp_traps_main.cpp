// fp_traps_main.cpp — Catch2 entry point that turns on floating-point traps first.
// glibc: feenableexcept; MSVC: _controlfp_s (a cleared mask bit = trap enabled).
#include <catch2/catch_session.hpp>
#include <cfenv>
#include <cstdio>

#include "fp_traps.hpp"

#if defined(_MSC_VER)
#include <float.h>
#endif

namespace xp::test {

bool enable_fp_traps() noexcept {
#if defined(_MSC_VER)
  unsigned int current = 0;
  _clearfp();
  return _controlfp_s(
             &current,
             ~static_cast<unsigned int>(_EM_INVALID | _EM_ZERODIVIDE | _EM_OVERFLOW) & _MCW_EM,
             _MCW_EM) == 0;
#elif defined(__GLIBC__)
  std::feclearexcept(FE_ALL_EXCEPT);
  return feenableexcept(FE_INVALID | FE_DIVBYZERO | FE_OVERFLOW) != -1;
#else
  return false;
#endif
}

bool fp_traps_enabled() noexcept {
#if defined(_MSC_VER)
  unsigned int current = 0;
  _controlfp_s(&current, 0, 0);
  return (current & (_EM_INVALID | _EM_ZERODIVIDE | _EM_OVERFLOW)) == 0;
#elif defined(__GLIBC__)
  constexpr int wanted = FE_INVALID | FE_DIVBYZERO | FE_OVERFLOW;
  return (fegetexcept() & wanted) == wanted;
#else
  return false;
#endif
}

}  // namespace xp::test

int main(int argc, char* argv[]) {
  if (!xp::test::enable_fp_traps()) {
    std::fputs("warning: floating-point traps unavailable on this platform\n", stderr);
  }
  return Catch::Session().run(argc, argv);
}
