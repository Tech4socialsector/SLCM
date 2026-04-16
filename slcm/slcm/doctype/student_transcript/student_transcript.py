# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from collections import defaultdict


class StudentTranscript(Document):
    pass


# ── Superscript helper ────────────────────────────────────────────────────────

def _grade_with_superscript(grade):
    """
    Convert trailing numeric digits and +/- in a grade to HTML <sup> tags.
    e.g.  "A+"  →  "A<sup>+</sup>"
          "B1"  →  "B<sup>1</sup>"
          "O"   →  "O"
    """
    if not grade:
        return grade or ""
    grade = str(grade).strip()
    SUFFIX_CHARS = set("0123456789+-")
    i = len(grade) - 1
    while i >= 0 and grade[i] in SUFFIX_CHARS:
        i -= 1
    prefix = grade[: i + 1]
    suffix = grade[i + 1 :]
    if suffix:
        return f"{frappe.utils.escape_html(prefix)}<sup>{frappe.utils.escape_html(suffix)}</sup>"
    return frappe.utils.escape_html(prefix)


# ── Data fetcher ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_transcript_context(student_id):
    """
    Return all data needed to render a student transcript.

    Called from the 'Student Transcript' Jinja print format via:
        frappe.get_attr('slcm.slcm.doctype.student_transcript.student_transcript.get_transcript_context')(doc.student)
    """

    # ── 1. Template settings ──────────────────────────────────────────────────
    tmpl_name = frappe.db.get_value("Transcript Template", {"is_default": 1}, "name")
    if tmpl_name:
        tmpl = frappe.db.get_value(
            "Transcript Template", tmpl_name,
            [
                "template_name", "page_size", "orientation",
                "institute_logo", "show_institute_logo", "logo_width", "logo_alignment",
                "institute_name", "header_title",
                "institute_address", "show_institute_address",
                "institute_city", "institute_country", "pincode",
                "show_student_photo", "show_registration_id",
                "show_cgpa", "show_credits", "show_semester_wise",
                "sig_label_1", "sig_image_1",
                "sig_label_2", "sig_image_2",
                "sig_label_3", "sig_image_3",
                "show_watermark", "watermark_logo", "watermark_text", "watermark_opacity",
            ],
            as_dict=True,
        ) or {}
    else:
        tmpl = {}

    # Defaults for template fields
    tmpl.setdefault("show_institute_logo", 1)
    tmpl.setdefault("logo_width", 120)
    tmpl.setdefault("logo_alignment", "Center")
    tmpl.setdefault("show_institute_address", 1)
    tmpl.setdefault("header_title", "OFFICIAL TRANSCRIPT OF ACADEMIC RECORDS")
    tmpl.setdefault("show_student_photo", 1)
    tmpl.setdefault("show_registration_id", 1)
    tmpl.setdefault("show_cgpa", 1)
    tmpl.setdefault("show_credits", 1)
    tmpl.setdefault("show_semester_wise", 1)
    tmpl.setdefault("show_watermark", 0)
    tmpl.setdefault("watermark_opacity", 20)

    # Build institute address string
    addr_parts = [
        tmpl.get("institute_address") or "",
        tmpl.get("institute_city") or "",
        tmpl.get("institute_country") or "",
        tmpl.get("pincode") or "",
    ]
    tmpl["institute_address_full"] = ", ".join(p.strip() for p in addr_parts if p.strip())

    # ── 2. Student info ───────────────────────────────────────────────────────
    sm = frappe.db.get_value(
        "Student Master", student_id,
        [
            "first_name", "middle_name", "last_name",
            "registration_id", "passport_size_photo",
            "programme", "batch_year", "academic_year",
            "current_cgpa", "cumulative_percentage",
            "email", "department", "specialisation",
        ],
        as_dict=True,
    ) or {}

    name_parts = [sm.get("first_name") or "", sm.get("middle_name") or "", sm.get("last_name") or ""]
    sm["full_name"] = " ".join(p.strip() for p in name_parts if p.strip())

    # Programme display name
    prog_id = sm.get("programme")
    if prog_id:
        cohort_name = frappe.db.get_value("Cohort", prog_id, "cohort_name")
        sm["programme_name"] = cohort_name or prog_id
    else:
        sm["programme_name"] = ""

    # ── 3. Fetch all course marks for the student ─────────────────────────────
    rows = frappe.db.sql(
        """
        SELECT
            scm.exam_plan,
            ep.exam_name,
            ep.term,
            scm.course,
            c.course_name,
            c.course_code,
            COALESCE(c.credit_value, 0)                                         AS credit_value,
            COALESCE(NULLIF(scm.updated_grade, ''), NULLIF(scm.grade, ''))      AS final_grade,
            CASE
                WHEN scm.updated_grade IS NOT NULL AND scm.updated_grade != ''
                     THEN COALESCE(scm.updated_final_marks, 0)
                ELSE COALESCE(scm.total_marks, 0)
            END                                                                  AS final_marks,
            COALESCE(gsc.grade_point, 0)                                        AS grade_point,
            COALESCE(gsc.failed, 0)                                             AS is_failed,
            COALESCE(scm.consider_for_sgpa, 0)                                  AS consider_for_sgpa,
            COALESCE(scm.mfa, 'No')                                             AS mfa,
            EXISTS (
                SELECT 1
                FROM `tabFA MFA Application` fma
                WHERE fma.student = scm.student
                  AND fma.course = scm.course
                  AND fma.docstatus = 1
                  AND fma.status = 'Approved'
                  AND fma.application_type = 'Medical First Attempt (MFA)'
            )                                                                   AS has_approved_mfa,
            scm.enrollment_status
        FROM `tabStudent Course Marks` scm
        INNER JOIN `tabExam Plan` ep ON ep.name = scm.exam_plan
        LEFT JOIN `tabCourse` c ON c.name = scm.course
        LEFT JOIN `tabCourse Schema Assignment` csa
            ON csa.exam_plan = scm.exam_plan AND csa.course = scm.course
        LEFT JOIN `tabGrading Schema Component` gsc
            ON gsc.parent = csa.grade_schema
            AND gsc.grade = COALESCE(NULLIF(scm.updated_grade, ''), NULLIF(scm.grade, ''))
        WHERE scm.student = %(student)s
          AND COALESCE(scm.enrollment_status, '') NOT IN ('Dropped', 'Detained', 'Migrated')
        ORDER BY ep.name ASC, c.course_code ASC, c.course_name ASC
        """,
        {"student": student_id},
        as_dict=True,
    )

    # ── 4. Fetch published SGPA values per exam plan ──────────────────────────
    sgpa_rows = frappe.db.sql(
        """
        SELECT exam_plan, term_gpa
        FROM `tabStudent Result Publish`
        WHERE student = %(student)s AND term_gpa IS NOT NULL AND term_gpa > 0
        """,
        {"student": student_id},
        as_dict=True,
    )
    published_sgpa = {r["exam_plan"]: r["term_gpa"] for r in sgpa_rows}

    # ── 5. Group by exam plan / semester ─────────────────────────────────────
    plan_order = []
    plan_courses = defaultdict(list)
    plan_meta = {}

    for row in rows:
        ep = row["exam_plan"]
        if ep not in plan_meta:
            plan_order.append(ep)
            plan_meta[ep] = {
                "exam_plan": ep,
                "exam_name": row.get("exam_name") or ep,
                "term":      row.get("term") or "",
            }
        plan_courses[ep].append(row)

    # ── 6. Build semester list with SGPA ──────────────────────────────────────
    ordinals = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                "XI", "XII", "XIII", "XIV", "XV", "XVI"]

    semesters = []
    total_earned_credits = 0

    for sem_idx, ep in enumerate(plan_order):
        meta    = plan_meta[ep]
        courses = plan_courses[ep]

        # Compute SGPA for this term
        sgpa = published_sgpa.get(ep)
        if sgpa is None:
            wgp   = 0.0
            tc    = 0.0
            for c in courses:
                if c["consider_for_sgpa"] and c["final_grade"] and c["credit_value"]:
                    wgp += float(c["grade_point"]) * float(c["credit_value"])
                    tc  += float(c["credit_value"])
            sgpa = round(wgp / tc, 2) if tc > 0 else None

        # Semester label: prefer "Semester I", fallback to exam_name
        label_roman = ordinals[sem_idx] if sem_idx < len(ordinals) else str(sem_idx + 1)
        label = f"SEMESTER {label_roman}"

        # Build course rows with HTML grade
        course_rows = []
        sem_credits = 0
        for c in courses:
            grade_html = _grade_with_superscript(c["final_grade"])
            has_mfa = (c.get("mfa") == "Yes") or bool(c.get("has_approved_mfa"))
            if has_mfa:
                grade_html = f"{grade_html} <sup class=\"mfa-sup\">MFA</sup>" if grade_html else "<sup class=\"mfa-sup\">MFA</sup>"
            credit_val = int(c["credit_value"]) if float(c["credit_value"]) == int(c["credit_value"]) else float(c["credit_value"])
            gp_val     = float(c["grade_point"])
            course_rows.append({
                "course_name":   c.get("course_name") or c.get("course_code") or "",
                "course_code":   c.get("course_code") or "",
                "credit_value":  credit_val,
                "final_grade":   c.get("final_grade") or "",
                "grade_html":    grade_html,
                "grade_point":   f"{gp_val:.1f}",
                "is_failed":     bool(c["is_failed"]),
                "mfa":           "Yes" if has_mfa else "No",
                "final_marks":   float(c.get("final_marks") or 0),
            })
            sem_credits += float(c["credit_value"])

        total_earned_credits += sem_credits

        semesters.append({
            "label":        label,
            "exam_name":    meta["exam_name"],
            "term":         meta["term"],
            "courses":      course_rows,
            "sgpa":         f"{sgpa:.2f}" if sgpa is not None else "",
            "total_credits": int(sem_credits) if sem_credits == int(sem_credits) else sem_credits,
        })

    # ── 7. CGPA ───────────────────────────────────────────────────────────────
    cgpa_raw = sm.get("current_cgpa")
    cgpa_display = f"{float(cgpa_raw):.2f}" if cgpa_raw else ""

    return {
        "template":              tmpl,
        "student":               sm,
        "semesters":             semesters,
        "cgpa":                  cgpa_display,
        "total_earned_credits":  int(total_earned_credits) if total_earned_credits == int(total_earned_credits) else total_earned_credits,
        "generation_date":       frappe.utils.formatdate(frappe.utils.today(), "dd-MM-yyyy"),
    }
