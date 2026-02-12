import frappe
from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
from slcm.api.bulk_attendance import mark_attendance
import concurrent.futures

def mark_attendance_wrapper(i):
    try:
        mark_attendance(
            students_present=[{"student": "BALLB26001"}],
            students_absent=[],
            class_schedule="CSH-2026-00001",
            date="2026-02-12",
            based_on="Class Schedule"
        )
        frappe.db.commit()
    except Exception as e:
        print(f"Error: {e}")

def reproduce_issue():
    print("Deleting existing summaries for cleanup...")
    frappe.db.delete("Attendance Summary", {"student": "BALLB26001"})
    frappe.db.commit()

    print("\nRunning concurrent requests...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(mark_attendance_wrapper, i) for i in range(2)]
        concurrent.futures.wait(futures)

    # 3. Inspect summaries again
    print("\nPost-Attendance State:")
    summaries = frappe.get_all("Attendance Summary", filters={"student": "BALLB26001"}, fields=["name", "course_offering", "total_attended_class_hours"])
    for s in summaries:
        print(f"Summary: {s.name}, Offering: {repr(s.course_offering)}, Hours: {s.total_attended_class_hours}")

    if len(summaries) > 1:
        print(f"\nFAILURE: Found {len(summaries)} summaries (duplicates)!")
    else:
        print(f"\nSUCCESS: Only {len(summaries)} summary found.")

reproduce_issue()
