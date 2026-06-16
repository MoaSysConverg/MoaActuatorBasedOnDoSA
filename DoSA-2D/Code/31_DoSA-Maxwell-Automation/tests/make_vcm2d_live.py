"""Make VCM 2D cell live + reuse desktop."""
import json
from pathlib import Path

NB = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    s = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
    if "builder_vcm = MaxwellSessionBuilder(" in s and "result_vcm = builder_vcm.build(live=False)" in s:
        # Replace builder constructor and build call
        new = s.replace(
            'builder_vcm = MaxwellSessionBuilder(\n    design=design_vcm, profile=profile_le01, out_dir=out_vcm, mode="2d"\n)',
            'builder_vcm = MaxwellSessionBuilder(\n    design=design_vcm, profile=profile_le01, out_dir=out_vcm, mode="2d", new_desktop=False,\n)',
        ).replace(
            "result_vcm = builder_vcm.build(live=False)",
            "result_vcm = builder_vcm.build(live=True)",
        )
        # Add AEDT path print after build
        if "AEDT project file: {result_vcm.project_path}" not in new:
            new = new.replace(
                'print(f"\\nVCM build (LE01): ok={result_vcm.ok}, commands={len(result_vcm.commands)}")',
                'print(f"\\nVCM build (LE01): ok={result_vcm.ok}, commands={len(result_vcm.commands)}")\nprint(f"AEDT project file: {result_vcm.project_path}")',
            )
        cell["source"] = new.splitlines(keepends=True)
        print("Patched VCM 2D cell")
        break

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
