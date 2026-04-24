"""Regenerate catalog.json — a manifest of every motion-graphics template
available locally. Both the frontend (for dynamic imports) and the backend
Gemma director (for prompt construction) read this file.

Run from anywhere: python build_catalog.py
"""
import os
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))


def scan(dirpath, ext):
    if not os.path.isdir(dirpath):
        return []
    out = []
    for name in sorted(os.listdir(dirpath)):
        p = os.path.join(dirpath, name)
        if os.path.isfile(p) and name.endswith(ext):
            out.append(os.path.splitext(name)[0])
    return out


catalog = {
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "libraries": {},
}

# Magic UI — flat tree of .tsx
catalog["libraries"]["magic-ui"] = {
    "license": "MIT",
    "source": "https://github.com/magicuidesign/magicui",
    "ext": ".tsx",
    "path": "magic-ui",
    "components": scan(os.path.join(ROOT, "magic-ui"), ".tsx"),
}

# Motion Primitives — flat tree of .tsx
catalog["libraries"]["motion-primitives"] = {
    "license": "MIT",
    "source": "https://github.com/ibelick/motion-primitives",
    "ext": ".tsx",
    "path": "motion-primitives",
    "components": scan(os.path.join(ROOT, "motion-primitives"), ".tsx"),
}

# React Bits — categorized .jsx
rb_root = os.path.join(ROOT, "react-bits")
catalog["libraries"]["react-bits"] = {
    "license": "MIT",
    "source": "https://github.com/DavidHDev/react-bits",
    "ext": ".jsx",
    "path": "react-bits",
    "categories": {
        cat: scan(os.path.join(rb_root, cat), ".jsx")
        for cat in ["text", "animations", "backgrounds", "components"]
    },
}

# Lotties — JSON files
lot_root = os.path.join(ROOT, "lotties")
catalog["libraries"]["lotties"] = {
    "license": "See individual files — LottieFiles free tier + lottie-web/RN test assets",
    "path": "lotties",
    "ext": ".json",
    "assets": scan(lot_root, ".json"),
}

totals = {
    "magic-ui": len(catalog["libraries"]["magic-ui"]["components"]),
    "motion-primitives": len(catalog["libraries"]["motion-primitives"]["components"]),
    "react-bits": sum(
        len(v) for v in catalog["libraries"]["react-bits"]["categories"].values()
    ),
    "lotties": len(catalog["libraries"]["lotties"]["assets"]),
}
totals["total"] = sum(totals.values())
catalog["totals"] = totals

out = os.path.join(ROOT, "catalog.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(catalog, f, indent=2)

print(f"wrote {out}")
print(json.dumps(totals, indent=2))
