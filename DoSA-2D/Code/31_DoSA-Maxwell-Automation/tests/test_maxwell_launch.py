#!/usr/bin/env python3
"""Test Maxwell session startup and lifecycle."""
import sys
import time
import tempfile
from pathlib import Path

try:
    from ansys.aedt.core import Maxwell2d
    print("✓ pyaedt imported")
except ImportError as e:
    print(f"✗ pyaedt not found: {e}")
    sys.exit(1)

temp_dir = tempfile.TemporaryDirectory(suffix=".ansys")
project_file = str(Path(temp_dir.name) / "test.aedt")

print(f"Project: {project_file}")

try:
    print("\n[1/3] Launching Maxwell2d with new_desktop=True...")
    m2d = Maxwell2d(
        project=project_file,
        design="TestDesign",
        solution_type="MagnetostaticXY",
        non_graphical=True,
        new_desktop=True,
        remove_lock=True,
    )
    print(f"  ✓ Maxwell2d created: {m2d.project_name}")
    print(f"  ✓ Project file: {m2d.project_file}")
    
    print("\n[2/3] Setting units...")
    m2d.modeler.model_units = "mm"
    print("  ✓ Units set to mm")
    
    print("\n[3/3] Saving and releasing...")
    m2d.save_project()
    print("  ✓ Saved")
    m2d.release_desktop(close_projects=False, close_desktop=False)
    print("  ✓ Released (desktop alive)")
    time.sleep(1)
    
    print("\n✓ SUCCESS: Maxwell can be launched and released properly")
    print(f"  Saved to: {project_file}")
    
except Exception as e:
    print(f"\n✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    temp_dir.cleanup()
