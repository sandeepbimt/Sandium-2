"""Run installed libclang's real C++ semantic warning checks without a driver."""
import ctypes as C
import ctypes.util

def diagnostics(path, args):
    libname = ctypes.util.find_library('clang-19')
    if not libname:
        raise RuntimeError('libclang-19 unavailable')
    lib = C.CDLL(libname)
    class String(C.Structure):
        _fields_ = [('data', C.c_void_p), ('flags', C.c_uint)]
    lib.clang_createIndex.argtypes = [C.c_int, C.c_int]
    lib.clang_createIndex.restype = C.c_void_p
    lib.clang_parseTranslationUnit.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(C.c_char_p), C.c_int, C.c_void_p, C.c_uint, C.c_uint]
    lib.clang_parseTranslationUnit.restype = C.c_void_p
    lib.clang_getNumDiagnostics.argtypes = [C.c_void_p]
    lib.clang_getDiagnostic.argtypes = [C.c_void_p, C.c_uint]
    lib.clang_getDiagnostic.restype = C.c_void_p
    lib.clang_formatDiagnostic.argtypes = [C.c_void_p, C.c_uint]
    lib.clang_formatDiagnostic.restype = String
    lib.clang_getCString.argtypes = [String]
    lib.clang_getCString.restype = C.c_char_p
    lib.clang_disposeString.argtypes = [String]
    lib.clang_disposeDiagnostic.argtypes = [C.c_void_p]
    lib.clang_disposeTranslationUnit.argtypes = [C.c_void_p]
    lib.clang_disposeIndex.argtypes = [C.c_void_p]
    index = lib.clang_createIndex(0, 0)
    argv = (C.c_char_p * len(args))(*(s.encode() for s in args))
    tu = lib.clang_parseTranslationUnit(index, str(path).encode(), argv, len(args), None, 0, 0)
    if not tu:
        raise RuntimeError('Clang parse failed')
    result = []
    for i in range(lib.clang_getNumDiagnostics(tu)):
        diagnostic = lib.clang_getDiagnostic(tu, i)
        string = lib.clang_formatDiagnostic(diagnostic, 0)
        result.append(lib.clang_getCString(string).decode())
        lib.clang_disposeString(string)
        lib.clang_disposeDiagnostic(diagnostic)
    lib.clang_disposeTranslationUnit(tu)
    lib.clang_disposeIndex(index)
    return result
