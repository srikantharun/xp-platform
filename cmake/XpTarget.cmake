# XpTarget.cmake — one entry point that applies every project-wide policy to a target.
# Keeps per-target CMakeLists free of flag plumbing: call xp_configure_target(<tgt>).

function(xp_configure_target target)
  target_compile_features(${target} PUBLIC cxx_std_20)
  set_target_properties(${target} PROPERTIES CXX_EXTENSIONS OFF POSITION_INDEPENDENT_CODE ON
  )# xp::core is linked into the Python extension
  xp_set_warnings(${target})
  xp_enable_sanitizers(${target})
  xp_enable_static_analyzers(${target})
endfunction()
