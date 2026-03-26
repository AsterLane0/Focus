from __future__ import annotations

import struct
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
SVG_PATH = ROOT / "icon.svg"
PNG_PATH = ROOT / "icon.png"
ICO_PATH = ROOT / "icon.ico"
ICNS_PATH = ROOT / "icon.icns"
ICONSET_DIR = ROOT / "icon.iconset"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def build_png() -> None:
    run([
        "qlmanage",
        "-t",
        "-s",
        "1024",
        "-o",
        str(ROOT),
        str(SVG_PATH),
    ])
    preview = ROOT / "icon.svg.png"
    if preview.exists():
        preview.replace(PNG_PATH)
    else:
        raise FileNotFoundError("PNG preview was not generated from icon.svg")


def build_ico() -> None:
    image = Image.open(PNG_PATH).convert("RGBA")
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    image.save(ICO_PATH, format="ICO", sizes=sizes)


def build_icns() -> None:
    if ICONSET_DIR.exists():
        for child in ICONSET_DIR.iterdir():
            child.unlink()
    else:
        ICONSET_DIR.mkdir(parents=True)

    sizes = [16, 32, 64, 128, 256, 512]
    for size in sizes:
        out = ICONSET_DIR / f"icon_{size}x{size}.png"
        out2 = ICONSET_DIR / f"icon_{size}x{size}@2x.png"
        run(["sips", "-z", str(size), str(size), str(PNG_PATH), "--out", str(out)])
        run(["sips", "-z", str(size * 2), str(size * 2), str(PNG_PATH), "--out", str(out2)])

    run(["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICNS_PATH)])


def main() -> None:
    build_png()
    build_ico()
    build_icns()
    print("Generated:", PNG_PATH.name, ICO_PATH.name, ICNS_PATH.name)


if __name__ == "__main__":
    main()
