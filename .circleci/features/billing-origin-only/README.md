# Origin-only shared billing

Remove VPN/Leo product IDs, monthly/yearly queries, subscription purchase/price APIs, renewal-message hooks and receipt branches. Preserve Origin one-time purchase lookup, purchase, receipt acknowledgement/profile prefs, recovery/link-order URLs and QA consume-existing-Origin API. Unknown receipts are ignored before acknowledgement, not routed to an implicit default. No user data or legal notices are deleted. This is not an entitlement bypass.

Requires exclusive VPN/Leo callers removed from the Android source graph first. Origin callers remain compiled. Manifest also removes BraveActivity subscription-renewal invocation; duplicate VPN removal is safe when exact block is already absent.

Test: `python test.py --source /path/to/pinned/brave-core`. Tests cover exact pinned source, replay, atomic drift rejection and Origin-preservation contracts; Android compilation/device billing test still required. Billing wrapper and LinkSubscriptionUtils additionally passed javalang syntax parsing; shared BraveActivity uses modern Java unsupported by that parser.
