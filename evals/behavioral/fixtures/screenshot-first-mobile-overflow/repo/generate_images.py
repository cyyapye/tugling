#!/usr/bin/env python3
"""Generate two dependency-free synthetic UI screenshots."""

from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path


INK = (35, 34, 31)
MUTED = (117, 113, 105)
CANVAS = (247, 245, 239)
PAPER = (255, 255, 252)
LINE = (214, 210, 200)

GLYPHS = {
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "111", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"),
    "8": ("111", "101", "111", "101", "111"),
    "$": ("011", "110", "010", "011", "110"),
    "-": ("000", "000", "111", "000", "000"),
}


def canvas(width: int, height: int, color: tuple[int, int, int]) -> list[list[tuple[int, int, int]]]:
    return [[color for _ in range(width)] for _ in range(height)]


def rect(pixels, x: int, y: int, width: int, height: int, color) -> None:
    max_y = min(len(pixels), y + height)
    max_x = min(len(pixels[0]), x + width)
    for row in range(max(0, y), max_y):
        for column in range(max(0, x), max_x):
            pixels[row][column] = color


def outline(pixels, x: int, y: int, width: int, height: int, color) -> None:
    rect(pixels, x, y, width, 1, color)
    rect(pixels, x, y + height - 1, width, 1, color)
    rect(pixels, x, y, 1, height, color)
    rect(pixels, x + width - 1, y, 1, height, color)


def text(pixels, x: int, y: int, value: str, color=INK, scale: int = 3) -> None:
    cursor = x
    for character in value.upper():
        if character == " ":
            cursor += 4 * scale
            continue
        glyph = GLYPHS.get(character)
        if glyph is None:
            cursor += 4 * scale
            continue
        for row, pattern in enumerate(glyph):
            for column, bit in enumerate(pattern):
                if bit == "1":
                    rect(pixels, cursor + column * scale, y + row * scale, scale, scale, color)
        cursor += 4 * scale


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)


def write_png(path: Path, pixels) -> None:
    height = len(pixels)
    width = len(pixels[0])
    rows = []
    for row in pixels:
        rows.append(b"\x00" + bytes(channel for pixel in row for channel in pixel))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += png_chunk(b"IHDR", header)
    data += png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
    data += png_chunk(b"IEND", b"")
    path.write_bytes(data)


def draw_desktop() -> None:
    pixels = canvas(960, 640, CANVAS)
    rect(pixels, 0, 0, 960, 64, PAPER)
    rect(pixels, 120, 105, 720, 130, PAPER)
    text(pixels, 120, 30, "PORTFOLIO", scale=3)
    text(pixels, 145, 132, "SUMMARY", scale=4)
    text(pixels, 145, 188, "$120", scale=4)
    text(pixels, 120, 282, "HOLDINGS", scale=4)
    rect(pixels, 120, 325, 720, 190, PAPER)
    outline(pixels, 120, 325, 720, 190, LINE)
    text(pixels, 145, 350, "NAME", MUTED, 3)
    text(pixels, 560, 350, "VALUE", MUTED, 3)
    rect(pixels, 120, 385, 720, 1, LINE)
    text(pixels, 145, 415, "ALPHA", scale=3)
    text(pixels, 560, 415, "$120", scale=3)
    text(pixels, 720, 415, "VIEW", scale=3)
    rect(pixels, 120, 455, 720, 1, LINE)
    text(pixels, 145, 480, "BETA", scale=3)
    text(pixels, 560, 480, "$80", scale=3)
    text(pixels, 720, 480, "VIEW", scale=3)
    write_png(Path("desktop.png"), pixels)


def draw_mobile() -> None:
    pixels = canvas(390, 780, CANVAS)
    rect(pixels, 0, 0, 390, 58, PAPER)
    text(pixels, 20, 24, "PORTFOLIO", scale=2)
    rect(pixels, 20, 92, 350, 125, PAPER)
    text(pixels, 40, 118, "SUMMARY", scale=3)
    text(pixels, 40, 165, "$120", scale=3)
    text(pixels, 20, 260, "HOLDINGS", scale=3)
    # The desktop table is incorrectly kept at 520 px, so its value and action
    # columns are clipped outside the 390 px viewport.
    rect(pixels, 20, 305, 520, 220, PAPER)
    outline(pixels, 20, 305, 520, 220, LINE)
    text(pixels, 40, 332, "NAME", MUTED, 2)
    text(pixels, 300, 332, "VALUE", MUTED, 2)
    rect(pixels, 20, 370, 520, 1, LINE)
    text(pixels, 40, 402, "ALPHA", scale=3)
    text(pixels, 300, 402, "$120", scale=3)
    text(pixels, 455, 402, "VIEW", scale=3)
    rect(pixels, 20, 460, 520, 1, LINE)
    text(pixels, 40, 487, "BETA", scale=3)
    text(pixels, 300, 487, "$80", scale=3)
    text(pixels, 455, 487, "VIEW", scale=3)
    # A bottom scrollbar makes the structural failure explicit.
    rect(pixels, 20, 550, 350, 5, LINE)
    rect(pixels, 20, 550, 230, 5, INK)
    write_png(Path("mobile.png"), pixels)


draw_desktop()
draw_mobile()
