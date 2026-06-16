"""Configure live build cells to share one AEDT Desktop session.

- Cell 5 (Solenoid 2D, first live cell): new_desktop=True (default)
- Cell 9 (Solenoid 3D), Cell 11 (VCM 3D): new_desktop=False
- Append a final cell to release the shared desktop.
"""
import json
from pathlib import Path

NB = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

def src_of(cell):
    s = cell["source"]
    return "".join(s) if isinstance(s, list) else s

def add_new_desktop_false(src: str, builder_var: str) -> str:
    """Insert ``new_desktop=False,`` into the MaxwellSessionBuilder(...) kwargs
    of the given variable name, if not already present."""
    if "new_desktop=" in src:
        return src
    needle = f"{builder_var} = MaxwellSessionBuilder("
    idx = src.find(needle)
    if idx < 0:
        return src
    # insert before the closing ')' of the constructor
    end = src.find(")", idx)
    if end < 0:
        return src
    # find last comma or '(' to detect indentation
    chunk = src[idx:end]
    # If multi-line builder call (has newline), insert on a new indented line
    if "\n" in chunk:
        # determine indent from a kwarg line
        lines = chunk.split("\n")
        indent = ""
        for ln in lines[1:]:
            stripped = ln.lstrip()
            if stripped and not stripped.startswith(")"):
                indent = ln[: len(ln) - len(stripped)]
                break
        # ensure trailing comma on previous content; insert before ')'
        # find the line index that contains ')'
        before = src[:end]
        if not before.rstrip().endswith(","):
            before = before.rstrip() + ",\n" + indent + "new_desktop=False,\n"
        else:
            before = before + indent + "new_desktop=False,\n"
        return before + src[end:]
    else:
        # single line
        return src[:end].rstrip().rstrip(",") + ", new_desktop=False" + src[end:]

count = 0
for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    s = src_of(cell)
    new = s
    if "result_3d = builder_3d.build(live=True)" in s:
        new = add_new_desktop_false(s, "builder_3d")
    elif "result_vcm_3d = builder_vcm_3d.build(live=True)" in s:
        new = add_new_desktop_false(s, "builder_vcm_3d")
    if new != s:
        cell["source"] = new.splitlines(keepends=True)
        count += 1

# Append a final cleanup cell if not already present
already = any(
    "release_desktop" in src_of(c) and c["cell_type"] == "code"
    for c in nb["cells"]
)
if not already:
    cleanup = {
        "cell_type": "code",
        "id": "aedtcleanup",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": (
            "# Shared AEDT Desktop 세션 정리 (튜토리얼 종료)\n"
            "try:\n"
            "    from ansys.aedt.core import Desktop\n"
            "    Desktop().release_desktop(close_projects=True, close_desktop=True)\n"
            "    print(\"AEDT desktop released.\")\n"
            "except Exception as e:\n"
            "    print(f\"Cleanup skipped: {e}\")\n"
        ).splitlines(keepends=True),
    }
    nb["cells"].append(cleanup)
    count += 1

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Patched cells: {count}")
