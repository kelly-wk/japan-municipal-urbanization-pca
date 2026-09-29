#!/usr/bin/env python3
"""Download pinned official e-Stat source workbooks with hash verification."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen


BASE = "https://www.e-stat.go.jp/stat-search/file-download?fileKind=0&statInfId="
SOURCES = {
    "2024": {
        "A.xls": ("000040186221", "0ba40bbd7aa9aca93ede59f306ab492f3d5b83decca87ddae7b198dffbc1ae83"),
        "B.xls": ("000040186222", "7962eda57272788788d0eb3d48bbbbc64d303e06f2092fe96ac2c552567cac04"),
        "C.xls": ("000040186223", "af5e0a06ba6b22a4308c62acad28d3bcac67088ad7744f9d369ba100854e7b43"),
        "F.xls": ("000040186226", "697c375726b5c4bc59214420010f655b2db7ec3426cc2260dd4878b903cb3732"),
        "H.xls": ("000040186228", "22847f425807a062e9aca90ae2c84c9426f5f100f2c704e0ef9f37068854a2d4"),
        "I.xls": ("000040186229", "b48544c8e82bda5b9dce826e2a0a689e6bf8d98c9ef17dd8381d504a6f230846"),
    },
    "2026": {
        "A.xls": ("000040463584", "bff101b575a03ddc5a944cf008a7314cb8a736afb3cbda87465e181db0835ad5"),
        "B.xls": ("000040463585", "59c3460f3c04ea25286fd7e07ddb4963673664e72a849941c3e13c07c0758a18"),
        "C.xls": ("000040463586", "4b4f4144e71b25c95e92057e72189ec6463a0231c82cb7ade7c792ef47c693bb"),
        "F.xls": ("000040463589", "446d5b0d60bdf4086a341707e2db30b0a877dcffda8ee67bf6c0006be7914bf9"),
        "H.xls": ("000040463591", "22eae2589e51b2d5a2a4b74d3d77747c894fb864258856b341153f667076cd8f"),
        "I.xls": ("000040463592", "b76cc27fed59f80f654e9c09b07858fb8c3ede3e767187c9b82983a55d5150d0"),
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(output: Path) -> None:
    for release, files in SOURCES.items():
        release_dir = output / release
        release_dir.mkdir(parents=True, exist_ok=True)
        for filename, (stat_id, expected) in files.items():
            destination = release_dir / filename
            if destination.exists() and sha256(destination) == expected:
                print(f"verified {destination}")
                continue
            request = Request(
                BASE + stat_id,
                headers={"User-Agent": "municipal-urbanization-reproducibility/1.0"},
            )
            with tempfile.NamedTemporaryFile(dir=release_dir, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                with urlopen(request, timeout=120) as response:
                    shutil.copyfileobj(response, temporary)
            actual = sha256(temporary_path)
            if actual != expected:
                temporary_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Hash mismatch for {release}/{filename}: expected {expected}, got {actual}. "
                    "The upstream file may have been revised; review before updating the pin."
                )
            temporary_path.replace(destination)
            print(f"downloaded {destination}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    download(args.output)


if __name__ == "__main__":
    main()

