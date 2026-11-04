# Vanilla Brave Android upgrade

- Brave Core: \`v1.99.54\`
- Chromium: \`157.0.8103.30\` (SHA resolved in Stage 1 and saved in the source pin manifest)
- Build: upstream Brave Release, ARM64
- Package ID: \`com.brave.browser\`
- App label: \`Brave\`

This branch builds upstream Brave without Sandium branding, UI modifications, injected filter lists, ad-blocker patches, updater changes or package-name overrides. Brave Shields, its native ad blocker and filter-list catalogue remain exactly as supplied by Brave v1.99.54.

The official Brave Release build uses the ARM64 AAB-to-Universal-APK distribution route with secondary ABI disabled. The read-only APK size audit requires only \`arm64-v8a\` native libraries and AArch64 ELF headers. The supplied screenshot shows \`Bravearm64Universal.apk\` at 203 MB; that is the comparison target, not a guaranteed output size.

The source upgrade changes both Brave and Chromium, so Full Mode is required to regenerate the GN/Ninja graph. The canonical 26GB reference at commit \`3c8004b\` remains protected and unchanged. Full Mode preserves the staged Siso/BuildBuddy workspace and validates the APK and archive shards before promoting the new v1.99.54 reference. Ordinary changes should use Fast Mode after the new reference is successfully promoted.
