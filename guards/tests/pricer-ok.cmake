# ok: a pricer CMakeLists with only the single xp_pricer() call and comments.
xp_pricer(
  NAME     black_scholes
  SOURCES  black_scholes.cpp
  TESTS    test_black_scholes.cpp
  USES     QuantLib::QuantLib
)
