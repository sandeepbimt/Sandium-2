#!/usr/bin/env python3
"""Generate deterministic Android-density PNGs using only the Python standard library."""
from __future__ import annotations

import argparse
import math
import shutil
import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
ASSETS = ("app_icon.png", "layered_app_icon.png", "layered_app_icon_background.png")


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_indexed_png(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"not a PNG file: {path}")
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = compression = filter_method = interlace = None
    palette = None
    transparency = b""
    idat = bytearray()
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError(f"truncated PNG chunk in {path}")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        chunk = data[offset + 8:offset + 8 + length]
        if len(chunk) != length:
            raise ValueError(f"truncated PNG data in {path}")
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif kind == b"PLTE":
            palette = chunk
        elif kind == b"tRNS":
            transparency = chunk
        elif kind == b"IDAT":
            idat.extend(chunk)
        elif kind == b"IEND":
            break
        offset += length + 12

    if (bit_depth, color_type, compression, filter_method, interlace) != (8, 3, 0, 0, 0):
        raise ValueError(
            f"expected non-interlaced 8-bit indexed PNG at {path}; got "
            f"depth={bit_depth}, color_type={color_type}, interlace={interlace}"
        )
    if not width or not height or not palette or len(palette) % 3:
        raise ValueError(f"invalid dimensions or palette in {path}")

    raw = zlib.decompress(bytes(idat))
    row_bytes = width
    if len(raw) != height * (row_bytes + 1):
        raise ValueError(f"unexpected decompressed PNG length in {path}")
    indices: list[bytes] = []
    previous = bytearray(row_bytes)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        scan = bytearray(raw[cursor + 1:cursor + 1 + row_bytes])
        cursor += row_bytes + 1
        for i in range(row_bytes):
            left = scan[i - 1] if i else 0
            up = previous[i]
            upper_left = previous[i - 1] if i else 0
            if filter_type == 1:
                scan[i] = (scan[i] + left) & 255
            elif filter_type == 2:
                scan[i] = (scan[i] + up) & 255
            elif filter_type == 3:
                scan[i] = (scan[i] + ((left + up) // 2)) & 255
            elif filter_type == 4:
                scan[i] = (scan[i] + paeth(left, up, upper_left)) & 255
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter {filter_type} in {path}")
        indices.append(bytes(scan))
        previous = scan

    colors = []
    palette_entries = len(palette) // 3
    for row in indices:
        rgba = []
        for index in row:
            if index >= palette_entries:
                raise ValueError(f"palette index out of range in {path}")
            p = index * 3
            alpha = transparency[index] if index < len(transparency) else 255
            rgba.append((palette[p], palette[p + 1], palette[p + 2], alpha))
        colors.extend(rgba)
    return width, height, colors


def premultiply(pixels: list[tuple[int, int, int, int]]) -> list[tuple[float, float, float, float]]:
    result = []
    for red, green, blue, alpha in pixels:
        a = alpha / 255.0
        result.append((red * a, green * a, blue * a, float(alpha)))
    return result


def resize_box(
    source: list[tuple[float, float, float, float]],
    sw: int, sh: int, dw: int, dh: int
) -> list[tuple[float, float, float, float]]:
    output = []
    for y in range(dh):
        y0, y1 = y * sh / dh, (y + 1) * sh / dh
        sy0, sy1 = math.floor(y0), math.ceil(y1)
        for x in range(dw):
            x0, x1 = x * sw / dw, (x + 1) * sw / dw
            sx0, sx1 = math.floor(x0), math.ceil(x1)
            sums = [0.0, 0.0, 0.0, 0.0]
            total = 0.0
            for sy in range(sy0, min(sy1, sh)):
                wy = max(0.0, min(y1, sy + 1) - max(y0, sy))
                for sx in range(sx0, min(sx1, sw)):
                    wx = max(0.0, min(x1, sx + 1) - max(x0, sx))
                    weight = wx * wy
                    pixel = source[sy * sw + sx]
                    for c in range(4):
                        sums[c] += pixel[c] * weight
                    total += weight
            output.append(tuple(v / total for v in sums))
    return output


def resize_bilinear(
    source: list[tuple[float, float, float, float]],
    sw: int, sh: int, dw: int, dh: int
) -> list[tuple[float, float, float, float]]:
    output = []
    for y in range(dh):
        sy = min(max((y + 0.5) * sh / dh - 0.5, 0.0), sh - 1.0)
        y0 = int(math.floor(sy))
        y1 = min(y0 + 1, sh - 1)
        fy = sy - y0
        for x in range(dw):
            sx = min(max((x + 0.5) * sw / dw - 0.5, 0.0), sw - 1.0)
            x0 = int(math.floor(sx))
            x1 = min(x0 + 1, sw - 1)
            fx = sx - x0
            p00 = source[y0 * sw + x0]
            p10 = source[y0 * sw + x1]
            p01 = source[y1 * sw + x0]
            p11 = source[y1 * sw + x1]
            out_pixel = []
            for c in range(4):
                top = p00[c] * (1 - fx) + p10[c] * fx
                bottom = p01[c] * (1 - fx) + p11[c] * fx
                out_pixel.append(top * (1 - fy) + bottom * fy)
            output.append(tuple(out_pixel))
    return output


def rgba_bytes(pixels: list[tuple[float, float, float, float]]) -> bytes:
    out = bytearray()
    for red, green, blue, alpha in pixels:
        a = min(255.0, max(0.0, alpha))
        if a > 0.0001:
            scale = 255.0 / a
            red, green, blue = red * scale, green * scale, blue * scale
        else:
            red = green = blue = 0.0
        out.extend((
            int(round(min(255.0, max(0.0, red)))),
            int(round(min(255.0, max(0.0, green)))),
            int(round(min(255.0, max(0.0, blue)))),
            int(round(a)),
        ))
    return bytes(out)


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)


def write_rgba_png(path: Path, size: int, pixels: list[tuple[float, float, float, float]]) -> None:
    row = rgba_bytes(pixels)
    stride = size * 4
    raw = b"".join(b"\x00" + row[y * stride:(y + 1) * stride] for y in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    encoded = PNG_SIGNATURE + png_chunk(b"IHDR", header) + png_chunk(b"IDAT", zlib.compress(raw, 9)) + png_chunk(b"IEND", b"")
    path.write_bytes(encoded)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gn-file", type=Path, required=True)
    args = parser.parse_args()

    if not args.gn_file.is_file():
        raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL missing upstream GN file: {args.gn_file}")
    gn = args.gn_file.read_text(encoding="utf-8")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for child in args.output_dir.glob("mipmap-*"):
        if child.is_dir():
            shutil.rmtree(child)

    decoded = {}
    for name in ASSETS:
        source_path = args.source_dir / name
        if not source_path.is_file():
            raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL missing master image: {source_path}")
        sw, sh, pixels = read_indexed_png(source_path)
        if (sw, sh) != (128, 128):
            raise SystemExit(
                f"SANDIUM_BRANDING_GATE=FAIL expected 128x128 checked-in master {source_path}; got {sw}x{sh}"
            )
        decoded[name] = (sw, sh, premultiply(pixels))

    total = 0
    for density, size in SIZES.items():
        target_dir = args.output_dir / f"mipmap-{density}"
        target_dir.mkdir(parents=True, exist_ok=True)
        for name, (sw, sh, source) in decoded.items():
            relative = f"java/res_chromium_base/mipmap-{density}/{name}"
            count = gn.count(relative)
            if count != 2:
                raise SystemExit(
                    f"SANDIUM_BRANDING_GATE=FAIL expected two unchanged GN declarations "
                    f"for {relative}; found {count}"
                )
            scaled = (
                resize_box(source, sw, sh, size, size)
                if size < sw
                else resize_bilinear(source, sw, sh, size, size)
            )
            destination = target_dir / name
            write_rgba_png(destination, size, scaled)
            total += 1
        print(f"SANDIUM_BRANDING_GENERATE=PASS density={density} size={size}")
    print(f"SANDIUM_BRANDING_GN_DECLARATIONS=PASS untouched=true resources={total}")


if __name__ == "__main__":
    main()
