#!/usr/bin/env python3
"""
Verification script for real-time attendance sync.
Tests that editing Class Schedule times updates Attendance Session and Attendance Summary.
"""

import frappe
from frappe.utils import get_datetime

def test_realtime_sync():
    """Test real-time sync from Class Schedule to Attendance Session and Attendance Summary"""
    
    print("\n" + "="*80)
    print("REAL-TIME ATTENDANCE SYNC VERIFICATION")
    print("="*80)
    
    # Find a Class Schedule with an Attendance Session
    class_schedule = frappe.db.sql("""
        SELECT cs.name, cs.from_time, cs.to_time, cs.duration_hours, cs.course_offering
        FROM `tabClass Schedule` cs
        WHERE EXISTS (
            SELECT 1 FROM `tabAttendance Session` ats
            WHERE ats.class_schedule = cs.name
        )
        LIMIT 1
    """, as_dict=True)
    
    if not class_schedule:
        print("❌ No Class Schedule with Attendance Session found. Please create one first.")
        return
    
    cs = class_schedule[0]
    print(f"\n📋 Testing with Class Schedule: {cs.name}")
    print(f"   Course Offering: {cs.course_offering}")
    print(f"   Original From Time: {cs.from_time}")
    print(f"   Original To Time: {cs.to_time}")
    print(f"   Original Duration: {cs.duration_hours} hours")
    
    # Get the linked Attendance Session
    session = frappe.db.get_value("Attendance Session", 
        {"class_schedule": cs.name}, 
        ["name", "session_start_time", "session_end_time", "duration_hours"],
        as_dict=True
    )
    
    if not session:
        print(f"❌ No Attendance Session found for {cs.name}")
        return
    
    print(f"\n📊 Linked Attendance Session: {session.name}")
    print(f"   Original Session Start: {session.session_start_time}")
    print(f"   Original Session End: {session.session_end_time}")
    print(f"   Original Duration: {session.duration_hours} hours")
    
    # Get Attendance Summary for a student
    student = frappe.db.sql("""
        SELECT DISTINCT student
        FROM `tabStudent Attendance`
        WHERE course_offer = %s
        LIMIT 1
    """, cs.course_offering, as_dict=True)
    
    if not student:
        print(f"\n⚠️  No students found with attendance records for {cs.course_offering}")
        print("   Skipping Attendance Summary check")
        summary_before = None
    else:
        student_id = student[0].student
        summary = frappe.db.get_value("Attendance Summary",
            {"student": student_id, "course_offering": cs.course_offering},
            ["name", "total_class_hours"],
            as_dict=True
        )
        
        if summary:
            print(f"\n👤 Testing with Student: {student_id}")
            print(f"   Attendance Summary: {summary.name}")
            print(f"   Original Total Class Hours: {summary.total_class_hours} hours")
            summary_before = summary
        else:
            print(f"\n⚠️  No Attendance Summary found for student {student_id}")
            summary_before = None
    
    # Simulate the real-time update
    print("\n" + "-"*80)
    print("🔄 SIMULATING REAL-TIME UPDATE")
    print("-"*80)
    
    # Change the times (add 1 hour to both start and end)
    from datetime import datetime, timedelta
    
    original_from = datetime.strptime(str(cs.from_time), "%H:%M:%S")
    original_to = datetime.strptime(str(cs.to_time), "%H:%M:%S")
    
    new_from = (original_from - timedelta(hours=1)).time()
    new_to = original_to.time()
    
    # Calculate new duration
    new_duration = (original_to - (original_from - timedelta(hours=1))).total_seconds() / 3600
    
    print(f"\n📝 New Times:")
    print(f"   New From Time: {new_from}")
    print(f"   New To Time: {new_to}")
    print(f"   New Duration: {new_duration} hours")
    
    # Call the real-time update method
    from slcm.slcm.doctype.class_schedule.class_schedule import update_attendance_session_realtime
    
    result = update_attendance_session_realtime(
        class_schedule_name=cs.name,
        from_time=str(new_from),
        to_time=str(new_to),
        schedule_date=frappe.db.get_value("Class Schedule", cs.name, "schedule_date"),
        duration_hours=new_duration
    )
    
    print(f"\n📤 API Response: {result}")
    
    # Verify the changes
    print("\n" + "-"*80)
    print("✅ VERIFICATION")
    print("-"*80)
    
    # Check Attendance Session
    session_after = frappe.db.get_value("Attendance Session",
        session.name,
        ["session_start_time", "session_end_time", "duration_hours"],
        as_dict=True
    )
    
    print(f"\n📊 Attendance Session After Update:")
    print(f"   Session Start: {session_after.session_start_time} (Expected: {new_from})")
    print(f"   Session End: {session_after.session_end_time} (Expected: {new_to})")
    print(f"   Duration: {session_after.duration_hours} hours (Expected: {new_duration} hours)")
    
    session_updated = (
        str(session_after.session_start_time) == str(new_from) and
        str(session_after.session_end_time) == str(new_to) and
        abs(session_after.duration_hours - new_duration) < 0.01
    )
    
    if session_updated:
        print("   ✅ Attendance Session updated correctly!")
    else:
        print("   ❌ Attendance Session NOT updated correctly!")
    
    # Check Attendance Summary
    if summary_before:
        summary_after = frappe.db.get_value("Attendance Summary",
            summary_before.name,
            ["total_class_hours"],
            as_dict=True
        )
        
        print(f"\n👤 Attendance Summary After Update:")
        print(f"   Total Class Hours: {summary_after.total_class_hours} hours")
        print(f"   Previous: {summary_before.total_class_hours} hours")
        print(f"   Expected Change: +{new_duration - cs.duration_hours} hours")
        
        expected_total = summary_before.total_class_hours + (new_duration - cs.duration_hours)
        
        if abs(summary_after.total_class_hours - expected_total) < 0.01:
            print("   ✅ Attendance Summary updated correctly!")
        else:
            print(f"   ❌ Attendance Summary NOT updated correctly!")
            print(f"      Expected: {expected_total}, Got: {summary_after.total_class_hours}")
    
    print("\n" + "="*80)
    print("VERIFICATION COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_realtime_sync()
