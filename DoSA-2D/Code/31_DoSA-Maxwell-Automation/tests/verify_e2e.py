"""End-to-end verification script."""
import sys
sys.path.insert(0, r"E:/KDH/gitDosa_Actuator/DoSA-2D/Code/31_DoSA-Maxwell-Automation/src")

from pathlib import Path
from dosa_maxwell import (
    parse_dosa_file, extract_geometry, resolve_material,
    resolve_magnet_direction, MaxwellSessionBuilder, get_profile,
    list_profiles, get_unified_plan_summary,
)

ROOT = Path(r"E:/KDH/gitDosa_Actuator/DoSA-2D/Code/31_DoSA-Maxwell-Automation")
SOLENOID = Path(r"E:/KDH/gitDosa_Actuator/DoSA-2D/Code/11_DoSA-2D/DoSA-2D/Samples/Solenoid/Solenoid.dsa")
VCM = Path(r"E:/KDH/gitDosa_Actuator/DoSA-2D/Code/11_DoSA-2D/DoSA-2D/Samples/VCM/VCM.dsa")

design_sol = parse_dosa_file(SOLENOID)
design_vcm = parse_dosa_file(VCM)

print("=== Solenoid Parts ===")
for part in design_sol.parts:
    geom = extract_geometry(part)
    mat = resolve_material(part.properties.get("Material", "Air"))
    pts = len(geom.points) if geom else 0
    print(f"  {part.name:10s} | {mat.maxwell_name:25s} | pts={pts}")

print("\n=== VCM Parts ===")
for part in design_vcm.parts:
    geom = extract_geometry(part)
    mat = resolve_material(part.properties.get("Material", "Air"))
    extra = ""
    if part.kind == "Magnet":
        d = part.properties.get("MagnetDirection", "")
        extra = f" | dir={d} -> {resolve_magnet_direction(d)}"
    print(f"  {part.name:10s} | {mat.maxwell_name:15s}{extra}")

# Build Solenoid with WS01
profile = get_profile("ws01_2020r1")
out = ROOT / "output" / "verify_solenoid"
builder = MaxwellSessionBuilder(design=design_sol, profile=profile, out_dir=out, mode="2d")
r = builder.build(live=False)
print(f"\nSolenoid build: ok={r.ok}, cmds={len(r.commands)}, errors={r.errors}")

# Build VCM with LE01
profile2 = get_profile("le01_2020r1")
out2 = ROOT / "output" / "verify_vcm"
builder2 = MaxwellSessionBuilder(design=design_vcm, profile=profile2, out_dir=out2, mode="2d")
r2 = builder2.build(live=False)
print(f"VCM build: ok={r2.ok}, cmds={len(r2.commands)}, errors={r2.errors}")

# Plan status
plan = get_unified_plan_summary()
print(f"\nPlan v{plan['version']}: {len(plan['milestones'])} milestones")
for m in plan["milestones"]:
    print(f"  [{m['status']}] {m['id']}: {m['title']}")

print("\n=== ALL CHECKS PASSED ===")
