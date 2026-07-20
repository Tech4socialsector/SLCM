import os
import glob

test_dir = "/home/bsoft/frappe16-bench/apps/slcm/slcm/tests/merit_system"

for filepath in glob.glob(os.path.join(test_dir, "*.py")):
    with open(filepath, "r") as f:
        content = f.read()
    
    if "ms.execute_advanced_allocation_logic(" in content:
        content = content.replace(
            "import slcm.admission.doctype.merit_generation.merit_service as ms",
            "import slcm.admission.doctype.merit_generation.merit_service as ms"
        )
        # some files might already import ms, so we handle duplicate imports safely (python allows it)
        content = content.replace("ms.execute_advanced_allocation_logic(", "ms.ms.execute_advanced_allocation_logic(")
        
        with open(filepath, "w") as f:
            f.write(content)
print("Done patching tests.")
