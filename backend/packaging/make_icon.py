"""Gera o ícone do MultiMind (PNG + ICO) sem dependências externas.

Desenha um quadrado arredondado com gradiente (índigo → fúcsia) e três nós
ligados, representando agentes a colaborar.
"""

from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path


def _png(size: int) -> bytes:
    s = size
    r = s * 0.22  # raio dos cantos
    nodes = [(0.30, 0.34), (0.70, 0.34), (0.50, 0.70)]
    node_r = s * 0.085
    line_w = s * 0.045
    edges = [(0, 1), (0, 2), (1, 2)]

    def inside_rounded(x: float, y: float) -> float:
        dx = max(r - x, 0, x - (s - r))
        dy = max(r - y, 0, y - (s - r))
        d = math.hypot(dx, dy)
        return max(0.0, min(1.0, r - d + 0.5)) if (dx or dy) else 1.0

    def seg_dist(px, py, ax, ay, bx, by) -> float:
        vx, vy = bx - ax, by - ay
        t = max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
        return math.hypot(px - (ax + t * vx), py - (ay + t * vy))

    pts = [(x * s, y * s) for x, y in nodes]
    rows = []
    for y in range(s):
        row = bytearray([0])
        for x in range(s):
            cx, cy = x + 0.5, y + 0.5
            a = inside_rounded(cx, cy)
            t = (cx + cy) / (2 * s)
            base = (
                int(79 + (192 - 79) * t),  # 4f46e5 → c026d3
                int(70 + (38 - 70) * t),
                int(229 + (211 - 229) * t),
            )
            white = 0.0
            for i, j in edges:
                d = seg_dist(cx, cy, *pts[i], *pts[j])
                white = max(white, max(0.0, min(1.0, line_w / 2 - d + 0.5)))
            for px, py in pts:
                d = math.hypot(cx - px, cy - py)
                white = max(white, max(0.0, min(1.0, node_r - d + 0.5)))
            color = tuple(int(c + (255 - c) * white) for c in base)
            row += bytes((*color, int(255 * a)))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    header = struct.pack(">IIBBBBB", s, s, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _ico(images: list[tuple[int, bytes]]) -> bytes:
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    body = b""
    for size, png in images:
        dim = 0 if size >= 256 else size
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(body))
        body += png
    return out + body


def main(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    images = [(size, _png(size)) for size in (16, 32, 48, 256)]
    (target / "multimind.ico").write_bytes(_ico(images))
    (target / "multimind.png").write_bytes(images[-1][1])
    print(f"Ícone gerado em {target}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent)
