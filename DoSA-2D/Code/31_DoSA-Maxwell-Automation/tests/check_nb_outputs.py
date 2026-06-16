import json
from pathlib import Path

nb_path = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(nb_path.read_text(encoding="utf-8"))

def out_text(o):
    t = o.get("output_type")
    if t == "stream":
        v = o.get("text", "")
    elif t in ("execute_result", "display_data"):
        v = o.get("data", {}).get("text/plain", "")
    elif t == "error":
        return "!!ERROR!! " + o.get("ename", "") + ": " + o.get("evalue", "")
    else:
        v = ""
    if isinstance(v, list):
        v = "".join(v)
    return v

idx = 0
for c in nb["cells"]:
    if c["cell_type"] != "code":
        continue
    idx += 1
    text = "".join(out_text(o) for o in c.get("outputs", []))
    has_err = any(o.get("output_type") == "error" for o in c.get("outputs", []))
    marker = "[ERR]" if has_err else "[OK ]"
    print(f"=== {marker} Code Cell {idx} ===")
    print(text[:1200])
    print()
