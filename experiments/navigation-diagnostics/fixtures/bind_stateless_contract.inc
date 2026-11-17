// Exact IsStateless check from Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51
// base/functional/bind_internal.h, lines 1752-1761; BSD license.
  template <typename Traits, bool v = Traits::is_stateless>
  struct IsStateless {
    static constexpr bool value = [] {
      static_assert(
          v, "Capturing lambdas and stateful functors are intentionally not "
             "supported. Use a non-capturing lambda or stateless functor (i.e. "
             "has no non-static data members) and bind arguments directly.");
      return v;
    }();
  };
