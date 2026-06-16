"""Append project_path print into live build cells of the tutorial notebook."""
import json
from pathlib import Path

NB = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

PATCHES = [
    ("result = builder.build(live=True)", "result"),
    ("result_3d = builder_3d.build(live=True)", "result_3d"),
    ("result_vcm_3d = builder_vcm_3d.build(live=True)", "result_vcm_3d"),
]

count = 0
for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    src = cell["source"]
    src_str = "".join(src) if isinstance(src, list) else src
    if "AEDT project file" in src_str:
        continue
    for marker, var in PATCHES:
        if marker in src_str:
            insert_line = f'print(f"AEDT project file: {{{var}.project_path}}")\n'
            # Insert before "if ...errors:" line
            new_lines = []
            inserted = False
            for line in src_str.splitlines(keepends=True):
                if not inserted and line.lstrip().startswith("if ") and ".errors" in line:
                    new_lines.append(insert_line)
                    inserted = True
                new_lines.append(line)
            if not inserted:
                new_lines.append("\n" + insert_line)
            cell["source"] = new_lines
            count += 1
            print(f"Patched cell with marker: {marker}")
            break

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Total patched: {count}")
