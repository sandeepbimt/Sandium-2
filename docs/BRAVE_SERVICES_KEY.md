# Brave Services key for Sandium

Sandium uses the pinned Brave Core v1.98.62 build path. Brave forwards
`brave_services_key` from `brave/.env` into GN and compiles the result into
the `BraveServiceKey` request header.

## Configure CircleCI

1. Obtain a Brave Services key that you are authorized to use for your fork.
2. In CircleCI project settings, add a project environment variable named
   `BRAVE_SERVICES_KEY`.
3. Set it to your own key. Do not put the value in Git, commit messages, CI
   configuration, build logs, or issue comments.
4. Run the Sandium Fast Mode pipeline.

The pipeline checks that the variable exists before checkout. Stage 1 writes it
to `brave/.env` as `brave_services_key=...` with file mode `0600`. Helper
output redacts the value; Brave's existing build tooling forwards it into GN.

## Important

Do not copy the key extracted from the official Brave APK or its network log
into Sandium. Brave's published build instructions say external developers
must provide their own values for service-backed settings.

The value is compiled into the Android client, so it is a client application
key rather than a server-only secret. Use a key authorized for this app and
protect CircleCI and its generated build artifacts accordingly.
