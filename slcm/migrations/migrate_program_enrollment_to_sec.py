"""
Migration: Program Enrollment → Student Enrollment Course

Converts existing Program Enrollment child rows (linked to Course) into
Student Enrollment Course rows (linked to Course Offering).

Run once after deploying the schema changes:
    bench execute slcm.migrations.migrate_program_enrollment_to_sec.run
"""

import frappe


def run():
    migrated = 0
    skipped_no_offering = 0
    skipped_already_exists = 0

    # Fetch all Program Enrollment rows that belong to Student Enrollment
    pe_rows = frappe.db.sql(
        """
        SELECT pe.name, pe.parent, pe.course, pe.course_name,
               pe.course_type, pe.course_status, pe.credit_value, pe.idx,
               se.cohort
        FROM `tabProgram Enrollment` pe
        JOIN `tabStudent Enrollment` se ON se.name = pe.parent
        WHERE pe.parenttype = 'Student Enrollment'
          AND pe.course IS NOT NULL
          AND pe.course != ''
        ORDER BY pe.parent, pe.idx
        """,
        as_dict=True,
    )

    print(f"Found {len(pe_rows)} Program Enrollment rows to migrate.")

    for row in pe_rows:
        # Find the matching Course Offering for this course + cohort
        offering = frappe.db.get_value(
            "Course Offering",
            {"course_title": row.course, "cohort": row.cohort},
            "name",
        )

        if not offering:
            print(f"  SKIP: No Course Offering found for course={row.course}, cohort={row.cohort} (parent={row.parent})")
            skipped_no_offering += 1
            continue

        # Skip if a Student Enrollment Course row already exists for this offering
        already_exists = frappe.db.exists(
            "Student Enrollment Course",
            {"parent": row.parent, "course_offering": offering},
        )
        if already_exists:
            skipped_already_exists += 1
            continue

        # Map course_status → enrollment status
        status = "Dropped" if (row.course_status or "").lower() == "dropped" else "Enrolled"

        doc = frappe.get_doc(row.parent, row.parent)  # Student Enrollment parent
        doc.append("enrolled_courses", {
            "course_offering": offering,
            "course_type": row.course_type or "",
            "status": status,
        })
        doc.save(ignore_permissions=True)
        migrated += 1

    frappe.db.commit()
    print(f"\nMigration complete.")
    print(f"  Migrated:              {migrated}")
    print(f"  Skipped (no offering): {skipped_no_offering}")
    print(f"  Skipped (duplicate):   {skipped_already_exists}")

    if skipped_no_offering:
        print(
            "\nNOTE: Some rows were skipped because no matching Course Offering exists."
            "\nCreate the missing Course Offerings and re-run to migrate those rows."
        )
