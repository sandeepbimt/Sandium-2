# #1164 Privacy Settings crash

The Nov 15 08:31:31 device bugreport contains current crashes at 08:25:49 and
08:31:21 local time: `NullPointerException` writing `Preference.v` in
`BravePrivacySettings.T1(String, Bundle)`. Startup/browsing now work by user test.
This is distinct from historical startup exceptions elsewhere in the report.

Wallet removal deletes the decentralized-DNS `unstoppable_domains` XML row.
The shared Privacy Settings class still unconditionally looked it up and bound
`mUstoppableDomains.setOnPreferenceChangeListener(this)`. No row means null.

Remove that dead field and binding in the same Wallet removal transform, with
exact anchor checks. Do not reinstate the removed feature or broadly catch the
exception. ENS/SNS rows have no equivalent direct binding. Retained Shields,
cookies and ordinary privacy listeners are preserved. Existing reset/replay
restores the pinned source before applying the corrected transform.

Regression tests cover absent DNS rows/binding, retained listeners, atomic
failure on anchor drift, and full composition/reset/replay/recovery. Android
runtime validation still requires the successor APK and device testing; an
obfuscated stack alone does not provide a deobfuscated source line.

Independent review also found main Settings ordering the removed Wallet row
through a non-null helper. Remove that dead ordering call too. The removed-row
cache cannot supply a preference that was never inflated. Preserve ordinary
Settings ordering and leave null-safe lookup/removal paths intact.
