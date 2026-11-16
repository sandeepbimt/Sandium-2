json_reader.h is unmodified Chromium source at commit
d331de35ca8ab1358c7a17e4bd41627d55eaef51, path base/json/json_reader.h.
SHA256: cc11fc68ff19fafde085c15349a2b6d17b09d21b4a75fc81c1e158eeee648548.

The #1201 regression compiles the actual production ReadDict call against this
header, with narrow stubs for unrelated Chromium value/export dependencies.
The old one-argument call must fail compilation; the explicit strict RFC8259
option must compile. This does not test Chromium's JSON parser implementation
or replace full native compilation/runtime testing.
