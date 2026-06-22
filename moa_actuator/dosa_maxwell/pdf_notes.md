# Maxwell Lecture Notes Integration

This note tracks how external Maxwell lecture/reference PDFs are mapped into
the DoSA-Maxwell automation workflow.

## Referenced PDFs

- refDoc/MAXW_Actuator_2020R1_EN_WS01.pdf
- refDoc/MAXW_Actuator_2020R1_EN_LE01.pdf
- refDoc/coupling_solenoid_1114_2014.pdf
- refDoc/TPC_Solenoid_1210_2014.pdf

## 2014 PDF Summaries

The two 2014 documents were added to profile mapping and notebook execution
flow. The summary below is written from integration perspective first.

### coupling_solenoid_1114_2014.pdf

1. Purpose
- Provide a coupling-solenoid oriented reference case for actuator magnetic
	behavior under time-varying excitation.

2. Model Scope
- Solenoid-centered geometry and coil-driven electromagnetic response.
- Focus is compatible with 2D Maxwell actuator workflow used in this project.

3. Setup/Simulation Pattern
- Mapped profile id: `coupling_1114_2014`
- Current integration values in `unified_plan.json`:
	- solution_type: `Transient`
	- time_step: `0.2ms`
	- stop_time: `20ms`
	- mesh_hint: `medium_fine`

4. Result Focus
- Time-domain behavior trend analysis (force/current/field progression) is the
	primary expected usage in this automation context.

5. Automation Implications
- Keep transient setup defaults as profile-driven values.
- Validate coil polarity and excitation sign conventions first when result
	direction mismatches appear.
- Keep this profile as the default 2014 transient benchmark in tutorial runs.

### TPC_Solenoid_1210_2014.pdf

1. Purpose
- Provide a TPC-solenoid style reference emphasizing static operating-point
	validation and field-force interpretation.

2. Model Scope
- Solenoid and magnetic path configuration suitable for magnetostatic checks.
- Intended as a contrast against transient-oriented coupling profile.

3. Setup/Simulation Pattern
- Mapped profile id: `tpc_1210_2014`
- Current integration values in `unified_plan.json`:
	- solution_type: `Magnetostatic`
	- time_step: `1ms`
	- stop_time: `5ms`
	- mesh_hint: `balanced`

4. Result Focus
- Steady-state field and force trend checks under fixed current settings.

5. Automation Implications
- Use this profile for fast geometry/material sanity checks before expensive
	transient runs.
- Prefer this profile for CI-like quick verification in non-graphical mode.

## Cross-Document Integration Notes (2014)

- Common:
	- Both are now discoverable through `source_pdf` and auto-executed by the
		notebook PDF-profile section.
	- Both are represented as named presets in `config/unified_plan.json`.

- Difference:
	- `coupling_1114_2014` is transient-oriented.
	- `tpc_1210_2014` is magnetostatic-oriented.

- Recommended usage order:
	1. Run `tpc_1210_2014` for baseline geometry/material validation.
	2. Run `coupling_1114_2014` for time-domain behavior checks.

## Verification and Follow-up

1. Verify profile id and source_pdf consistency:
- `coupling_1114_2014` <-> `coupling_solenoid_1114_2014.pdf`
- `tpc_1210_2014` <-> `TPC_Solenoid_1210_2014.pdf`

2. Verify notebook execution path:
- PDF profile auto-discovery includes both 2014 profiles.

3. Follow-up TODO
- Add page-level evidence mapping (page number -> setup/result statement) after
	stable text extraction or manual page review is completed.
