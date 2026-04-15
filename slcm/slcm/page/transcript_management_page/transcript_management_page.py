# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _build_filters(search="", programme="", course="", academic_year="", batch="",
                   student_status="", department=""):
    """Build WHERE clause and params for student list queries."""
    conditions = []
    params = {}

    if search:
        conditions.append(
            "(sm.registration_id LIKE %(search)s"
            " OR sm.first_name LIKE %(search)s"
            " OR sm.last_name LIKE %(search)s"
            " OR sm.email LIKE %(search)s"
            " OR CONCAT(sm.first_name,' ',IFNULL(sm.last_name,'')) LIKE %(search)s)"
        )
        params["search"] = f"%{search}%"

    if programme:
        conditions.append("sm.programme = %(programme)s")
        params["programme"] = programme

    if department:
        conditions.append("sm.department = %(department)s")
        params["department"] = department

    if batch:
        conditions.append("sm.batch_year = %(batch)s")
        params["batch"] = batch

    if academic_year:
        conditions.append("sm.academic_year = %(academic_year)s")
        params["academic_year"] = academic_year

    if student_status:
        conditions.append("sm.academic_status = %(student_status)s")
        params["student_status"] = student_status

    if course:
        conditions.append(
            "EXISTS ("
            "  SELECT 1 FROM `tabStudent Enrollment Course` sec"
            "  JOIN `tabStudent Enrollment` se ON se.name = sec.parent"
            "  WHERE se.student = sm.name AND sec.course = %(course)s"
            ")"
        )
        params["course"] = course

    where = "WHERE 1=1"
    if conditions:
        where += " AND " + " AND ".join(conditions)

    return where, params


# ── Public API ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_students(
    search="", programme="", course="", academic_year="", batch="",
    student_status="", department="",
    page=1, page_length=50,
    sort_by="registration_id", sort_order="asc"
):
    """
    Return a paginated list of students with transcript status columns.
    Each row contains:
      student, student_name, registration_id, email, photo,
      programme, programme_name, batch_year, academic_year,
      department, department_name,
      learning_pathways,
      earned_credits, total_credits,
      cgpa,
      interim_transcript, final_transcript
    """
    page        = int(page)
    page_length = int(page_length)
    offset      = (page - 1) * page_length

    sort_map = {
        "student_name":    "CONCAT(sm.first_name,' ',IFNULL(sm.last_name,''))",
        "registration_id": "sm.registration_id",
        "cgpa":            "sm.current_cgpa",
    }
    sort_col = sort_map.get(sort_by, "sm.registration_id")
    sort_dir = "DESC" if sort_order == "desc" else "ASC"

    where, params = _build_filters(
        search=search, programme=programme, course=course,
        academic_year=academic_year, batch=batch,
        student_status=student_status, department=department,
    )
    params.update({"lim": page_length, "off": offset})

    students = frappe.db.sql(
        f"""
        SELECT
            sm.name                                              AS student,
            CONCAT(sm.first_name,' ',IFNULL(sm.last_name,''))   AS student_name,
            sm.registration_id,
            sm.email,
            sm.passport_size_photo                              AS photo,
            sm.programme,
            sm.batch_year,
            sm.current_term,
            sm.academic_year,
            sm.department,
            sm.current_cgpa                                     AS cgpa,
            sm.student_status
        FROM `tabStudent Master` sm
        {where}
        ORDER BY {sort_col} {sort_dir}
        LIMIT %(lim)s OFFSET %(off)s
        """,
        params,
        as_dict=True,
    )

    # Remove pagination params before reusing for count query
    count_params = {k: v for k, v in params.items() if k not in ("lim", "off")}
    total_row = frappe.db.sql(
        f"""
        SELECT COUNT(sm.name) AS cnt
        FROM `tabStudent Master` sm
        {where}
        """,
        count_params,
        as_dict=True,
    )

    student_names = [s["student"] for s in students]

    # ── Fetch programme display names ──────────────────────────────────────────
    prog_names = {}
    if student_names:
        prog_ids = list({s["programme"] for s in students if s.get("programme")})
        if prog_ids:
            rows = frappe.db.sql(
                "SELECT name, cohort_name FROM `tabCohort` WHERE name IN %(ids)s",
                {"ids": prog_ids},
                as_dict=True,
            )
            prog_names = {r["name"]: r["cohort_name"] for r in rows}

    # ── Fetch department display names ─────────────────────────────────────────
    dept_names = {}
    if student_names:
        dept_ids = list({s["department"] for s in students if s.get("department")})
        if dept_ids:
            rows = frappe.db.sql(
                "SELECT name, department_name FROM `tabDepartment` WHERE name IN %(ids)s",
                {"ids": dept_ids},
                as_dict=True,
            )
            dept_names = {r["name"]: r["department_name"] for r in rows}

    # ── Fetch credit totals from Student Enrollment Course ─────────────────────
    # earned = credits for courses not dropped; total = all credits in enrollment
    credit_map = {}
    if student_names:
        credit_rows = frappe.db.sql(
            """
            SELECT
                se.student,
                SUM(CASE WHEN sec.status != 'Dropped' THEN IFNULL(sec.credits, 0) ELSE 0 END) AS earned,
                SUM(IFNULL(sec.credits, 0))                                                    AS total
            FROM `tabStudent Enrollment` se
            JOIN `tabStudent Enrollment Course` sec ON sec.parent = se.name
            WHERE se.student IN %(students)s
            GROUP BY se.student
            """,
            {"students": student_names},
            as_dict=True,
        )
        credit_map = {
            r["student"]: {
                "earned": int(r["earned"] or 0),
                "total":  int(r["total"] or 0),
            }
            for r in credit_rows
        }

    # ── Fetch learning pathways (via Student Enrollment → Cohort → Program) ────
    pathway_map = {}
    if student_names:
        pw_rows = frappe.db.sql(
            """
            SELECT
                se.student,
                se.program,
                p.program_name
            FROM `tabStudent Enrollment` se
            LEFT JOIN `tabProgram` p ON p.name = se.program
            WHERE se.student IN %(students)s
            ORDER BY se.creation ASC
            """,
            {"students": student_names},
            as_dict=True,
        )
        for r in pw_rows:
            if r.get("program"):
                pathway_map.setdefault(r["student"], []).append({
                    "program":      r["program"],
                    "program_name": r.get("program_name") or r["program"],
                    "type":         "Major",
                })

    # ── Fetch transcript generation status ─────────────────────────────────────
    transcript_map = {}
    if student_names:
        try:
            tr_rows = frappe.db.sql(
                """
                SELECT student, transcript_type, status, generation_date
                FROM `tabStudent Transcript`
                WHERE student IN %(students)s
                ORDER BY creation DESC
                """,
                {"students": student_names},
                as_dict=True,
            )
            for r in tr_rows:
                # Keep most recent record per (student, type)
                key = r["transcript_type"]
                student_map = transcript_map.setdefault(r["student"], {})
                if key not in student_map:
                    student_map[key] = {
                        "status": r["status"],
                        "date":   str(r.get("generation_date") or ""),
                    }
        except Exception:
            # Table may not exist yet (before bench migrate)
            pass

    # ── Assemble final rows ────────────────────────────────────────────────────
    for s in students:
        sid = s["student"]
        s["programme_name"]  = prog_names.get(s.get("programme"), s.get("programme") or "")
        s["department_name"] = dept_names.get(s.get("department"), s.get("department") or "")
        s["learning_pathways"] = pathway_map.get(sid, [])
        credits = credit_map.get(sid, {})
        s["earned_credits"] = credits.get("earned", 0)
        s["total_credits"]  = credits.get("total", 0)
        tr = transcript_map.get(sid, {})
        s["interim_transcript"] = tr.get("Interim", {}).get("status", "")
        s["final_transcript"]   = tr.get("Final", {}).get("status", "")

    return {
        "students": students,
        "total":    total_row[0]["cnt"] if total_row else 0,
    }


@frappe.whitelist()
def get_filter_options():
    """Return filter dropdown options: programmes, departments, academic_years, batches, courses, student_statuses."""
    programmes = frappe.db.sql(
        "SELECT name, cohort_name FROM `tabCohort` ORDER BY cohort_name ASC LIMIT 500",
        as_dict=True,
    )
    departments = frappe.db.sql(
        "SELECT name, department_name FROM `tabDepartment` ORDER BY department_name ASC LIMIT 200",
        as_dict=True,
    )
    academic_years = frappe.db.sql(
        "SELECT DISTINCT academic_year FROM `tabStudent Master`"
        " WHERE academic_year IS NOT NULL AND academic_year != ''"
        " ORDER BY academic_year DESC LIMIT 50",
        as_dict=True,
    )
    batches = frappe.db.sql(
        "SELECT DISTINCT batch_year FROM `tabStudent Master`"
        " WHERE batch_year IS NOT NULL AND batch_year != ''"
        " ORDER BY batch_year DESC LIMIT 50",
        as_dict=True,
    )
    courses = frappe.db.sql(
        "SELECT name, course_name, course_code FROM `tabCourse` ORDER BY course_name ASC LIMIT 500",
        as_dict=True,
    )
    # Match actual Student Master academic_status field options (tabStudent Master → Academic Status)
    student_statuses = ["Active", "Inactive", "Graduated", "Dropped", "Alumni", "Dormant"]

    return {
        "programmes":       programmes,
        "departments":      departments,
        "academic_years":   [r["academic_year"] for r in academic_years],
        "batches":          [r["batch_year"] for r in batches],
        "courses":          courses,
        "student_statuses": student_statuses,
    }


@frappe.whitelist()
def generate_transcript(students, transcript_type="Interim"):
    """
    Create or update Student Transcript records for the given students.
    students – JSON list of student names (document IDs from tabStudent Master).
    transcript_type – "Interim" or "Final"
    """
    import json
    if isinstance(students, str):
        students = json.loads(students)

    if transcript_type not in ("Interim", "Final"):
        frappe.throw("transcript_type must be 'Interim' or 'Final'.")

    results = []
    for student in students:
        try:
            existing = frappe.db.get_value(
                "Student Transcript",
                {"student": student, "transcript_type": transcript_type},
                "name",
            )
            if existing:
                frappe.db.set_value("Student Transcript", existing, {
                    "status":          "Generated",
                    "generation_date": frappe.utils.today(),
                    "generated_by":    frappe.session.user,
                })
            else:
                doc = frappe.new_doc("Student Transcript")
                doc.student          = student
                doc.transcript_type  = transcript_type
                doc.status           = "Generated"
                doc.generation_date  = frappe.utils.today()
                doc.generated_by     = frappe.session.user
                doc.insert(ignore_permissions=True)
            results.append({"student": student, "success": True})
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Transcript generation failed for {student}")
            results.append({"student": student, "success": False, "error": str(e)})

    frappe.db.commit()
    return results


@frappe.whitelist()
def download_transcript(student, transcript_type="Final"):
    """
    Return transcript record details and a print URL for the given student.
    Uses Frappe's built-in PDF print endpoint so the browser downloads a PDF.
    """
    record = frappe.db.get_value(
        "Student Transcript",
        {"student": student, "transcript_type": transcript_type},
        ["name", "status", "generation_date"],
        as_dict=True,
    )
    if not record:
        frappe.throw(
            f"No {transcript_type} transcript found for student {student}. "
            "Please generate the transcript first."
        )

    # Build a Frappe print/PDF URL for the Student Transcript document
    print_url = (
        f"/api/method/frappe.utils.print_format.download_pdf"
        f"?doctype=Student+Transcript&name={frappe.utils.quote(record['name'])}"
        f"&format=Standard&no_letterhead=0"
    )

    return {
        "student":         student,
        "transcript_type": transcript_type,
        "transcript_name": record["name"],
        "status":          record.get("status", ""),
        "generation_date": str(record.get("generation_date") or ""),
        "print_url":       print_url,
    }


@frappe.whitelist()
def generate_and_download(students, transcript_type="Interim"):
    """
    Generate transcripts for given students then return download info for each.
    Convenience method used by the 'Generate & Download' action.
    """
    import json
    if isinstance(students, str):
        students = json.loads(students)

    gen_results = generate_transcript(students=students, transcript_type=transcript_type)

    download_info = []
    for res in gen_results:
        if res.get("success"):
            try:
                info = download_transcript(
                    student=res["student"],
                    transcript_type=transcript_type,
                )
                download_info.append(info)
            except Exception:
                pass

    return {"generated": gen_results, "downloads": download_info}
