# Unified Development Plan

This document unifies development references across DoSA code, PyAEDT implementation, and Maxwell lecture PDFs.

## Inputs and sources

- DoSA-2D source: Code/11_DoSA-2D/DoSA-2D
- DoSA-3D source: DoSA-3D/Code/01_DoSA-3D/DoSA-3D
- PDF WS01: E:/KDH/gitDosa_Actuator/DoSA-2D/MAXW_Actuator_2020R1_EN_WS01.pdf
- PDF LE01: E:/KDH/gitDosa_Actuator/DoSA-2D/MAXW_Actuator_2020R1_EN_LE01.pdf

## Single-source strategy

1. Keep runtime presets and traceability in config/unified_plan.json.
2. Load execution profiles from unified_plan.json in code.
3. Use one CLI command to print unified plan status before implementation runs.

## Traceability matrix (summary)

- CCoil -> PDF coil setup -> Maxwell winding and current assignment
- CMagnet -> PDF magnet orientation -> Maxwell magnet material and direction mapping
- Force Test -> PDF force extraction -> Maxwell postprocess and report output

## Milestones

- M1 schema and parser freeze
- M2 2d dry-run with profile
- M3 2d geometry mapping
- M4 3d step import and run

## Process rule

Always update config/unified_plan.json first, then implement code changes that consume it.
