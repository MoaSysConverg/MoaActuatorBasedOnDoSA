"""Insert 3D demo cells into tutorial notebook before the Unified Plan section."""
import json
from pathlib import Path
import uuid

NB = Path(__file__).parents[1] / "tutorial_dosa_maxwell_mvp.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

def mkcell(cell_type, source):
    cell = {
        "cell_type": cell_type,
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    return cell

new_cells = [
    mkcell("markdown", """## 5. Maxwell 3D 빌드 — 축대칭 단면을 360도 회전

DoSA 2D 데이터는 축대칭(X=반경, Y=축)이므로,
3D 모드에서는 단면 sheet를 자동으로 Y축 기준 360도 회전시켜 솔리드를 생성합니다."""),
    mkcell("code", """# Solenoid를 3D 모델로 빌드 (revolve)
out_sol_3d = ROOT / "output" / "tutorial_solenoid_3d"
builder_3d = MaxwellSessionBuilder(
    design=design_sol,
    profile=profile_ws01,
    out_dir=out_sol_3d,
    mode="3d",
)
# live=True: 실제 AEDT 세션에 3D 프로젝트 생성
result_3d = builder_3d.build(live=True)

print(f"3D Build result: ok={result_3d.ok}, commands={len(result_3d.commands)}, errors={len(result_3d.errors)}")
if result_3d.errors:
    print("\\nErrors:")
    for e in result_3d.errors:
        print(f"  - {e}")"""),
    mkcell("code", """# 3D 빌드 커맨드 로그 확인 (sweep_around_axis 포함)
cmd_log_3d = json.loads((out_sol_3d / "maxwell_commands.json").read_text(encoding="utf-8"))

print(f"Total 3D commands: {len(cmd_log_3d['commands'])}")
print(f"Profile: {cmd_log_3d['profile']['name']} ({cmd_log_3d['profile']['solution_type']})")
print("\\n3D command sequence:")
for i, cmd in enumerate(cmd_log_3d['commands'], 1):
    args_summary = ', '.join(f"{k}={v}" for k, v in cmd['args'].items() if k != 'points')
    print(f"  {i:2d}. {cmd['method']:32s} | {args_summary}")"""),
    mkcell("code", """# VCM도 3D로 빌드 (자석 포함 모델)
out_vcm_3d = ROOT / "output" / "tutorial_vcm_3d"
builder_vcm_3d = MaxwellSessionBuilder(
    design=design_vcm,
    profile=get_profile("le01_2020r1"),
    out_dir=out_vcm_3d,
    mode="3d",
)
result_vcm_3d = builder_vcm_3d.build(live=True)

print(f"VCM 3D build: ok={result_vcm_3d.ok}, commands={len(result_vcm_3d.commands)}, errors={len(result_vcm_3d.errors)}")
if result_vcm_3d.errors:
    print("\\nErrors:")
    for e in result_vcm_3d.errors:
        print(f"  - {e}")"""),
]

# Find index of "## 5. Unified Plan" markdown cell and rename to "## 6."
for i, c in enumerate(nb["cells"]):
    src = c.get("source", "")
    if isinstance(src, list):
        src_str = "".join(src)
    else:
        src_str = src
    if c["cell_type"] == "markdown" and "Unified Plan" in src_str and "## 5." in src_str:
        # Renumber to 6
        new_src = src_str.replace("## 5.", "## 6.")
        c["source"] = new_src.splitlines(keepends=True)
        # Insert new cells before this
        nb["cells"] = nb["cells"][:i] + new_cells + nb["cells"][i:]
        print(f"Inserted {len(new_cells)} cells before index {i}")
        break
else:
    raise SystemExit("Could not find Unified Plan markdown cell")

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Wrote {NB} | total cells now: {len(nb['cells'])}")
