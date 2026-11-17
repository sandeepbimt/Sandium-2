# Pinned callback contract

`bind_stateless_contract.inc` copies the `IsStateless` static assertion unchanged
from Chromium `d331de35ca8ab1358c7a17e4bd41627d55eaef51`,
`base/functional/bind_internal.h`, lines1752–1761.
Source: https://chromium.googlesource.com/chromium/src/+/d331de35ca8ab1358c7a17e4bd41627d55eaef51/base/functional/bind_internal.h

The same header's `DecayedFunctorTraits` specialization for lambdas uses
`static constexpr bool is_stateless = std::is_empty_v<Functor>;` (line653).
The host lifecycle harness models this trait and `Unretained` pointer binding,
then executes the exact popup producer body. It also restores the forbidden
capturing callback and requires compilation to fail with the native diagnostic.
This is an extracted native contract regression, not a compile of all Chromium
BindOnce headers or the Android target. Full native compilation remains required.
