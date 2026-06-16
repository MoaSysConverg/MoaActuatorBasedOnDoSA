"""Fix the VCM 3D cell where new_desktop=False got mis-inserted into get_profile(...)."""
import json
from pathlib import Path

NB = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    s = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
    if "builder_vcm_3d = MaxwellSessionBuilder(" in s and "get_profile(\"le01_2020r1\",\n    new_desktop=False," in s:
        fixed = s.replace(
            "    profile=get_profile(\"le01_2020r1\",\n    new_desktop=False,\n),\n    out_dir=out_vcm_3d,\n    mode=\"3d\",\n)",
            "    profile=get_profile(\"le01_2020r1\"),\n    out_dir=out_vcm_3d,\n    mode=\"3d\",\n    new_desktop=False,\n)",
        )
        if fixed != s:
            cell["source"] = fixed.splitlines(keepends=True)
            print("Fixed VCM 3D cell")
            break
        else:
            print("Pattern not matched; manual inspection needed")
            print(s)
            break

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
