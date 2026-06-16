"""Ensure Solenoid 2D build cell uses live=True and prints project_path."""
import json
from pathlib import Path

NB = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    src = cell["source"]
    src_str = "".join(src) if isinstance(src, list) else src
    # Identify Solenoid 2D build cell (uses bare 'builder' and not 'builder_3d')
    if "result = builder.build(" in src_str and "builder_3d" not in src_str:
        new = src_str.replace("builder.build(live=False)", "builder.build(live=True)")
        if "AEDT project file" not in new:
            # insert before optional 'if result.errors:' or at end
            lines = new.splitlines(keepends=True)
            insert_line = 'print(f"AEDT project file: {result.project_path}")\n'
            inserted = False
            out = []
            for ln in lines:
                if not inserted and ln.lstrip().startswith("if ") and "result.errors" in ln:
                    out.append(insert_line)
                    inserted = True
                out.append(ln)
            if not inserted:
                if not out[-1].endswith("\n"):
                    out[-1] = out[-1] + "\n"
                out.append(insert_line)
            new = "".join(out)
        cell["source"] = new.splitlines(keepends=True)
        print("Patched Solenoid 2D cell -> live=True with project_path")
        break
else:
    raise SystemExit("Solenoid 2D cell not found")

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
