# RawS reviewed passive scriptlet lane (detached, default off)

The only runnable operations are two tiny fixed scripts that remove approved
ad metadata. Nothing reads cookies, storage, page JS variables or credentials;
nothing sets URLs, event handlers, display styles, document text, or code.
The ordinary browser retains renderer isolation, CSP and navigation. This is
not arbitrary uBO/Brave scriptlet support or a general blocker parity build.

## Immutable policy and existing-list provenance

The reviewed shapes occur in the existing uBlock Ads root (catalog index 0,
unchanged URL, title, key and settings) at uAssets a21816ca2ebafbc46cfe5191f2fccaeb5286fb2e,
Git blob c98d54230833c1b5a4aecddc1316564027cc1fc0, lines 9338 and 10691:
remove-attr alias ra with data-popunder-url, and ra with data-ppcnt_ads and
main[onclick]. No fixed publisher host or newly authored rule is present.
Only a current, preprocessed and enabled slot-0 rule may author a positive.
A bounded shadow engine projects the existing exact browser-admitted
scoped lines (at most 16) without changing any of the 30 list permissions.
Primary and ordinary additional engines still own all original matching,
including vetoes from other currently active lists.

Rust emits only two recognized zero-mask operation bits and the typed
exact/blanket scriptlet exceptions, after its original native scope and
uninject processing. C++ intersects the slot-0 proof with the normally
loaded additional engine and vetoes exact/blanket any-lane exceptions.
A missing/malformed JSON result, pending/failed replacement generation,
or a duplicate source index results in no effect. No resource storage,
generated injected_script, filter-provided JS/selector/source text or
permissions cross the execution boundary. Brace/quote/wildcard changes,
other attributes, optional modes and unsupported grammar are ignored.

Brave 1.100.58 pins its resolver code, not the separately-updated
resources.json installed by Android. The same source tree's iOS test archive
has a remove-attr primitive with a zero required mask; that archive is not
Android asset provenance. This code implements the two reviewed shapes
independently and does not redistribute a Brave resource or filter list.

## Execution and scope

Disabled by default, behind RawSReviewedPassiveScriptlets. If explicitly
enabled for an isolated test, begin request work at DOMContentLoaded, on a
visible regular active primary secure HTTPS document. No view-source,
internal/opaque docs, login/payment/consent/encoded paths, credentials,
query/fragment, nonstandard port, retained protected domains, prerender,
subframe or private-profile expansion. Browser rechecks enabled Shields,
native JS policy, live weak document, token, same final URL and worker
generation before dispatch; replies at or after 300 ms are ignored. When
the matcher refuses admission (not ready, refreshing, or busy), try again
up to four times, spaced 60 ms apart, within the same 300 ms window. An
accepted request never retries, even if its result is empty or discarded.
Each retry and reply is bound to the original navigation epoch and exact
document; a committed main-frame navigation cancels reuse, including a
same-document URL change or an away-and-back restore of a live document.
No scriptlet is replayed when a parked tab becomes visible.
Renderer rechecks token, current active secure HTML document and exact URL
and accepts only known mask bits. Each compiled isolated-world script does
one synchronous pass, at most 4,096 elements and 16 mutations, without
listeners, timers, observers or an internal binding. Linked native browser
integration and real apparatus still require proof. It is not a document-start
shim and cannot promise to preempt inline page code or later dynamic nodes.

Tests include host C++ selection/projection/veto fixtures, actual compiled-in
JS running on guarded Node DOM doubles, extracted browser methods running
against host doubles for busy/ready, invalidation, timeout and no replay, and mandatory assertions added to
the real host engine smoke before its existing canonical success marker.
The actual Rust/CXX/GN/Android execution is not a result from this checkout.
Before releasing, require that native smoke plus handset checks of isolated
world, CSP, fresh document/Back, concurrent refresh, negative protected paths,
legitimate first-party content and load cost; only then consider activation
under a separate reviewed build.
