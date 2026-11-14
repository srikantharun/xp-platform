# bad: a second statement after xp_pricer() smuggles compiler behavior past the
# missing-FLAGS argument and past semgrep's deny-list. The allow-list guard must reject it.
xp_pricer(NAME black_scholes SOURCES black_scholes.cpp USES QuantLib::QuantLib)
target_compile_options(black_scholes PRIVATE -fno-exceptions)
set_target_properties(black_scholes PROPERTIES CXX_STANDARD 17)
