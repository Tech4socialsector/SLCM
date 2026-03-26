import frappe
from slcm.slcm.utils.attendance_calculator import get_or_create_summary

def test_fix():
    student = "BALLB26001"
    offering = "Law of Crime"
    
    # Cleaning up
    frappe.db.delete("Attendance Summary", {"student": student, "course_offering": offering})
    frappe.db.commit()
    
    print("Creating first summary...")
    s1 = get_or_create_summary(student, offering)
    print(f"Created {s1.name}")
    
    print("Creating second summary (should be same)...")
    s2 = get_or_create_summary(student, offering)
    print(f"Returned {s2.name}")
    
    if s1.name == s2.name:
        print("SUCCESS: IDs match.")
    else:
        print("FAILURE: IDs do not match (duplicates created).")

    # verify hash format
    import hashlib
    expected_hash = hashlib.md5(offering.encode("utf-8")).hexdigest()[:10]
    expected_name = f"ASU-{student}-{expected_hash}"
    
    if s1.name == expected_name:
         print(f"SUCCESS: Name format matches expected deterministic ID: {expected_name}")
    else:
         print(f"FAILURE: Name format mismatch. Got {s1.name}, expected {expected_name}")

test_fix()
