# Brave Services key — not used by Sandium filter subscriptions

Sandium's uBlock-compatible filter lists are now registered as ordinary native
filter-list URL subscriptions. The browser downloads each public list directly
from its maintainer and uses Brave's native adblock engine to apply it.

No `BRAVE_SERVICES_KEY` CircleCI variable is required for this integration.
Do not copy the official Brave APK's private service key into Sandium. The
BuildBuddy key remains separate and is still required for remote compilation.

See [SANDIUM_FILTER_SUBSCRIPTIONS.md](SANDIUM_FILTER_SUBSCRIPTIONS.md) for the
selected 25 lists, update behavior, compatibility boundaries, and validation.
