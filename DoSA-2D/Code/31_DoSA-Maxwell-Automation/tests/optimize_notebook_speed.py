"""Optimize notebook: mixed live/dry-run for speed."""
import json
from pathlib import Path

NB = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

patches = {
    # VCM 2D -> dry-run (빠름)
    ("builder_vcm = MaxwellSessionBuilder(", "live=True"): ("live=False", "VCM 2D → dry-run"),
    # VCM 3D -> dry-run (빠름)  
    ("builder_vcm_3d = MaxwellSessionBuilder(", "live=True"): ("live=False", "VCM 3D → dry-run"),
}

count = 0
for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    s = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
    for (builder_check, old_live), (new_live, desc) in patches.items():
        if builder_check in s and old_live in s:
            new_s = s.replace(old_live, new_live)
            cell["source"] = new_s.splitlines(keepends=True)
            count += 1
            print(f"✓ {desc}: {builder_check[:30]}...")

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\nPatched: {count} cells")
print("\nFinal config:")
print("  Cell 9 (Solenoid 2D):  live=True  + new_desktop=True  (AEDT 기동)")
print("  Cell 12 (VCM 2D):      live=False (dry-run, 빠름)")
print("  Cell 14 (Solenoid 3D): live=True  + new_desktop=False (데스크톱 재사용)")
print("  Cell 16 (VCM 3D):      live=False (dry-run, 빠름)")
print("  Cell 20: Cleanup")
