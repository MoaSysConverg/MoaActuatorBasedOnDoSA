# DoSA Maxwell Automation (MVP)

This package provides an initial implementation to automate Ansys Maxwell analysis from DoSA design files.

## Scope of this MVP

- Parse DoSA text files (`.dsa`, `.dsa3d`) with `$begin` / `$end` blocks.
- Convert parsed tree to a canonical model for 2D/3D.
- Run CLI workflows:
  - `plan`: show unified plan summary loaded from `config/unified_plan.json`.
  - `inspect`: show summary of parts/tests.
  - `export-json`: export canonical model to JSON.
  - `profiles`: list available profile presets.
  - `run-2d` / `run-3d`: run Maxwell pipeline (currently a safe stub unless `ansys.aedt.core` is available).

## Location of referenced Maxwell lecture material

- `E:/KDH/gitDosa_Actuator/DoSA-2D/MAXW_Actuator_2020R1_EN_WS01.pdf`
- `E:/KDH/gitDosa_Actuator/DoSA-2D/MAXW_Actuator_2020R1_EN_LE01.pdf`

## Quick start

```powershell
cd E:/KDH/gitDosa_Actuator/DoSA-2D/Code/31_DoSA-Maxwell-Automation
pip install -e .
# optionally install Maxwell integration dependencies
pip install -e .[maxwell]

# Inspect a DoSA design file
dosa-maxwell inspect --input E:/path/to/design.dsa

# Export canonical json
dosa-maxwell export-json --input E:/path/to/design.dsa --output E:/tmp/design.json

# Dry-run Maxwell 2D workflow
dosa-maxwell run-2d --input E:/path/to/design.dsa --out-dir E:/tmp/mxw

# List and use PDF-based presets
dosa-maxwell plan
dosa-maxwell profiles
dosa-maxwell run-2d --input E:/path/to/design.dsa --out-dir E:/tmp/mxw --dry-run --profile ws01_2020r1
```

## Tutorial notebook

- `tutorial_dosa_maxwell_mvp.ipynb`
- This notebook demonstrates package install, sample DoSA file detection, inspect/export, and dry-run execution with `ws01_2020r1` profile.

## Next implementation items

- Implement geometry conversion from DoSA `Shape` blocks to Maxwell primitives.
- Implement material mapping table (DoSA -> Maxwell).
- Implement test scenario mapping for `FORCE_TEST`, `STROKE_TEST`, `CURRENT_TEST`.
- Add regression tests using real DoSA sample files.
