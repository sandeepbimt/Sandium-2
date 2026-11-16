JniType.java is the unmodified Chromium/JNI Zero source at Chromium commit
d331de35ca8ab1358c7a17e4bd41627d55eaef51, path
third_party/jni_zero/java/src/org/jni_zero/JniType.java.
SHA256: d9a715da7c4d1da5e91f28fe2e26211e29b36e4d5c525d260bc177c06a03ba8e.
Its TYPE_USE target is essential to reproducing #1197. The compilation test
uses this actual annotation and the exact transformed ThemeClient; other Android
and Chromium APIs are stubs. This is not a full Android build.
