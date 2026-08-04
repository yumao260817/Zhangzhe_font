import json

from .gb2312 import level1_chars
from .paths import (
    ASSETS_CANDIDATES,
    ASSETS_LABELED,
    ASSETS_RADICALS,
    REPORTS,
    TARGET,
)


def _list_images(root):
    if not root.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
    return sorted(str(p) for p in root.rglob("*") if p.suffix.lower() in exts)


def run_import() -> None:
    manifest = {
        "labeled": _list_images(ASSETS_LABELED) + _list_images(TARGET),
        "candidates": _list_images(ASSETS_CANDIDATES),
        "radicals": _list_images(ASSETS_RADICALS),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = REPORTS / "asset_manifest.json"
    report.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for v in manifest.values())
    print(f"素材盘点完成: 已标注 {len(manifest['labeled'])} 张, 备选 {len(manifest['candidates'])} 张, 部首 {len(manifest['radicals'])} 张, 合计 {total} 张")
    print(f"目标字符集: GB2312 一级 {len(level1_chars())} 字")
    print(f"清单已写入 {report}")
