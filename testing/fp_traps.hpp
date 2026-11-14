// fp_traps.hpp — portable enable/query of FE_INVALID | FE_DIVBYZERO | FE_OVERFLOW traps.
#pragma once

namespace xp::test {

// Unmask invalid, divide-by-zero and overflow traps for the calling thread.
// Returns false if the platform cannot enable traps.
bool enable_fp_traps() noexcept;

// True if all three traps are currently enabled on the calling thread.
bool fp_traps_enabled() noexcept;

}  // namespace xp::test
