"""
List fonts installed on the host OS.
Reads TTF/OTF font family names using fontTools, so the dropdown shows the
real CSS-compatible family name (e.g. "Arial" instead of "arialbd").
"""
import os
from functools import lru_cache
from fastapi import APIRouter

from fontTools.ttLib import TTFont, TTCollection

router = APIRouter(prefix="/api", tags=["fonts"])

FONT_EXTS = {".ttf", ".otf", ".ttc"}


def _family_from_font(font: TTFont) -> str | None:
    """Extract the Typographic Family (id 16) or fallback to Family Name (id 1)."""
    try:
        name_table = font["name"]
    except KeyError:
        return None

    # Prefer Typographic Family (16), fall back to Font Family (1)
    for name_id in (16, 1):
        record = (
            name_table.getName(name_id, 3, 1, 0x409)  # Windows Unicode English
            or name_table.getName(name_id, 1, 0, 0)   # Mac Roman
            or name_table.getName(name_id, 3, 1)      # Windows Unicode any lang
        )
        if record:
            try:
                return record.toUnicode().strip()
            except Exception:
                continue
    return None


def _families_from_file(path: str):
    names = []
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".ttc":
            tt = TTCollection(path, lazy=True)
            for font in tt.fonts:
                n = _family_from_font(font)
                if n:
                    names.append(n)
        else:
            font = TTFont(path, lazy=True, fontNumber=0)
            n = _family_from_font(font)
            if n:
                names.append(n)
    except Exception:
        pass
    return names


def _list_font_dir(path: str):
    try:
        return [
            os.path.join(path, f) for f in os.listdir(path)
            if os.path.splitext(f)[1].lower() in FONT_EXTS
        ]
    except (FileNotFoundError, PermissionError):
        return []


@lru_cache(maxsize=1)
def _all_fonts():
    dirs = [
        r"C:\Windows\Fonts",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts"),
    ]
    names = set()
    for d in dirs:
        for path in _list_font_dir(d):
            for family in _families_from_file(path):
                names.add(family)
    return sorted(names, key=str.lower)


@router.get("/fonts")
def list_fonts():
    """Return sorted, de-duplicated list of installed font family names."""
    return {"fonts": _all_fonts()}
