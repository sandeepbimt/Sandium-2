rc_header.py is the unmodified official Chromium GRIT formatter from pinned
revision d331de35ca8ab1358c7a17e4bd41627d55eaef51:
https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/tools/grit/grit/format/rc_header.py

The loader test supplies an XML-node adapter to this actual formatter and
compiles the generated header on the host. This verifies prepend emit suppresses
the Windows-only default atlres.h include. It is not a full GN/GRIT Android build.
