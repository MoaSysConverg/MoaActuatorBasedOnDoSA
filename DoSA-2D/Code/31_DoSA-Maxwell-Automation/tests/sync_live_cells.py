"""Sync notebook live-build cells to disk:
- Cell 5 (Solenoid 2D) and Cell 7 (VCM 2D) -> live=True + project_path print.
"""
import json
from pathlib import Path

NB = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

def patch(src_str: str, var: str) -> str:
    s = src_str
    s = s.replace(f"{var} = builder.build(live=False)", f"{var} = builder.build(live=True)")
    s = s.replace(f"{var} = builder_vcm.build(live=False)", f"{var} = builder_vcm.build(live=True)")
    if "AEDT project file" not in s:
        # insert before optional 'if ...errors:' or append
        lines = s.splitlines(keepends=True)
        insert_line = f'print(f"AEDT project file: {{{var}.project_path}}")\n'
        out = []
        inserted = False
        for ln in lines:
            if not inserted and ln.lstrip().startswith("if ") and ".errors" in ln:
                out.append(insert_line)
                inserted = True
            out.append(ln)
        if not inserted:
            if not out or not out[-1].endswith("\n"):
                if out:
                    out[-1] = out[-1] + "\n"
            out.append(insert_line)
        s = "".join(out)
    return s

count = 0
for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    src = cell["source"]
    src_str = "".join(src) if isinstance(src, list) else src
    new = src_str
    if "result = builder.build(" in src_str and "builder_3d" not in src_str and "builder_vcm" not in src_str:
        new = patch(src_str, "result")
    elif "result_vcm = builder_vcm.build(" in src_str:
        new = patch(src_str, "result_vcm")
    if new != src_str:
        cell["source"] = new.splitlines(keepends=True)
        count += 1
        print("Patched cell containing:", src_str.splitlines()[0][:60])

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Total patched: {count}")
