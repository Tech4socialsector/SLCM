# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import io
import csv
from frappe import _
from frappe.utils import flt, cstr
from frappe.utils.file_manager import get_file_path, save_file
import xlsxwriter


# Standard Columns required for Entrance Test Marks Template
TEMPLATE_COLUMNS = [
    "Application Number",
    "Applicant Name",
    "Program",
    "Entrance Test Status",
    "Shortlisted",
    "Part A Marks",
    "Part B Marks",
    "Status"
]


@frappe.whitelist()
def export_entrance_test_marks_template(
    academic_year=None,
    admission_cycle=None,
    campus=None,
    program_level=None,
    program=None,
    entrance_test=None,
    entrance_test_list=None,
    shortlisted_only=False,
    file_format="xlsx"
):
    """
    Exports a custom Entrance Test Marks template (CSV or Excel).

    Parameters:
    - academic_year: Link to Academic Year
    - admission_cycle: Link to Admission Cycle
    - campus: Link to Campus
    - program_level: UG / PG / Research Course
    - program: Link to Programme (optional)
    - entrance_test: Link to Entrance Test (optional)
    - entrance_test_list: Link to Entrance Test List (optional)
    - shortlisted_only: Boolean or string ("1"/"true") to filter shortlisted applicants only
    - file_format: "xlsx" or "csv"

    Workflow support:
    - Stage 1: Export all applicants for Part A marks entry.
    - Stage 2: Export shortlisted applicants (shortlisted_only=True) with pre-filled Part A marks for Part B entry.
    """
    # Permission Check
    if not (frappe.has_permission("Entrance Test Seat Allocation", "read") or
            "Entrance Test Admin" in frappe.get_roles() or
            "System Manager" in frappe.get_roles()):
        frappe.throw(_("You are not authorized to export entrance test marks."), frappe.PermissionError)

    # Cast shortlisted_only flag
    if isinstance(shortlisted_only, str):
        shortlisted_only = shortlisted_only.lower() in ["true", "1", "yes"]

    # Build DB Filters
    filters = {}
    if academic_year:
        filters["academic_year"] = academic_year
    if admission_cycle:
        filters["admission_cycle"] = admission_cycle
    if campus:
        filters["campus"] = campus
    if program_level:
        filters["program_level"] = program_level
    if program:
        filters["program"] = program
    if entrance_test:
        filters["entrance_test_name"] = entrance_test
    if entrance_test_list:
        filters["entrance_test_list"] = entrance_test_list
    if shortlisted_only:
        filters["shortlisted_status"] = "Shortlisted"

    # Fetch records
    allocations = frappe.get_all(
        "Entrance Test Seat Allocation",
        filters=filters,
        fields=[
            "name", "applicant", "candidate_name", "program",
            "gender", "entrance_test_status", "shortlisted_status",
            "part_a_total_marks_scored", "part_b_total_marks_scored", "result_status"
        ],
        order_by="applicant asc"
    )

    if not allocations:
        frappe.throw(_("No matching applicant records found for the selected criteria."))

    # Prefetch applicant details for performance
    applicant_ids = [a.applicant for a in allocations if a.applicant]
    applicant_data = {}
    if applicant_ids:
        app_records = frappe.get_all(
            "Applicant",
            filters={"name": ["in", applicant_ids]},
            fields=["name", "program", "gender"]
        )
        applicant_data = {r.name: r for r in app_records}

    rows = []
    for alloc in allocations:
        app_id = alloc.applicant or alloc.name
        app_info = applicant_data.get(app_id, frappe._dict())

        # 1. Application Number
        col_app_no = app_id

        # 2. Applicant Name
        col_name = alloc.candidate_name or ""

        # 3. Program
        col_program = alloc.program or app_info.get("program") or ""

        # 4. Entrance Test Status
        et_status = alloc.entrance_test_status or ""

        # 5. Shortlisted
        is_shortlisted = "Yes" if alloc.shortlisted_status == "Shortlisted" else "No"

        # 6. Part A Marks
        part_a_marks = alloc.part_a_total_marks_scored if alloc.part_a_total_marks_scored is not None else ""

        # 7. Part B Marks
        part_b_marks = alloc.part_b_total_marks_scored if alloc.part_b_total_marks_scored is not None else ""

        # 8. Status
        res_status = alloc.result_status or ""

        rows.append([
            col_app_no,
            col_name,
            col_program,
            et_status,
            is_shortlisted,
            part_a_marks,
            part_b_marks,
            res_status
        ])

    file_format = file_format.lower()
    filename = f"Entrance_Test_Marks_Template_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.{file_format}"

    if file_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(TEMPLATE_COLUMNS)
        writer.writerows(rows)

        saved_file = save_file(
            filename,
            output.getvalue().encode("utf-8"),
            "Entrance Test Seat Allocation",
            allocations[0].name,
            is_private=1
        )
        return {"file_url": saved_file.file_url, "filename": filename}

    else:
        # Generate Excel (.xlsx) using xlsxwriter
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"constant_memory": True})
        worksheet = workbook.add_worksheet("Marks Template")

        # Formats
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#1E3A8A",
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })
        cell_format = workbook.add_format({"border": 1, "valign": "vcenter"})
        number_format = workbook.add_format({"border": 1, "num_format": "0.00", "valign": "vcenter"})

        # Write Header
        for col_idx, header_text in enumerate(TEMPLATE_COLUMNS):
            worksheet.write(0, col_idx, header_text, header_format)
            worksheet.set_column(col_idx, col_idx, 18)

        # Write Rows
        for row_idx, row_data in enumerate(rows, start=1):
            for col_idx, val in enumerate(row_data):
                if col_idx in [5, 6] and val != "":
                    worksheet.write(row_idx, col_idx, flt(val), number_format)
                else:
                    worksheet.write(row_idx, col_idx, cstr(val), cell_format)

        workbook.close()

        saved_file = save_file(
            filename,
            output.getvalue(),
            "Entrance Test Seat Allocation",
            allocations[0].name,
            is_private=1
        )
        return {"file_url": saved_file.file_url, "filename": filename}


@frappe.whitelist()
def import_entrance_test_marks_file(file_url=None):
    """
    Imports Part A and/or Part B marks from uploaded CSV/Excel template into Entrance Test Seat Allocation.

    Rules & Guarantees:
    1. Matches records using 'Application Number'.
    2. Non-destructive update: ignores empty/blank mark cells, leaving pre-existing DB marks untouched.
    3. Updates Part A Marks if provided.
    4. Updates Part B Marks if provided.
    5. Recalculates total score (`total_marks_secured_in_part_a_b`) and percentage (`percentage`).
    6. Logs invalid application numbers and detailed row errors.
    """
    # Permission Check
    if not (frappe.has_permission("Entrance Test Seat Allocation", "write") or
            "Entrance Test Admin" in frappe.get_roles() or
            "System Manager" in frappe.get_roles()):
        frappe.throw(_("You are not authorized to import entrance test marks."), frappe.PermissionError)

    if not file_url:
        frappe.throw(_("Please attach or select a file to import."))

    # Get file content
    file_path = get_file_path(file_url.split('/')[-1])
    if not file_path or not frappe.os.path.exists(file_path):
        # Try fetching file record content
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_content = file_doc.get_content()
    else:
        with open(file_path, "rb") as f:
            file_content = f.read()

    # Parse rows depending on file format
    ext = file_url.split('.')[-1].lower()
    raw_rows = []

    if ext == "csv":
        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8-sig", errors="ignore")
        reader = csv.reader(io.StringIO(file_content))
        raw_rows = list(reader)
    elif ext in ["xlsx", "xls"]:
        from frappe.utils.xlsxutils import read_xlsx
        raw_rows = read_xlsx(file_content)
    else:
        frappe.throw(_("Unsupported file extension '.{0}'. Please upload a CSV or Excel (.xlsx) file.").format(ext))

    if not raw_rows or len(raw_rows) < 2:
        frappe.throw(_("The uploaded file is empty or missing data rows."))

    # Header analysis & column mapping
    header = [cstr(h).strip() for h in raw_rows[0]]

    def find_col_index(possible_headers):
        for idx, h in enumerate(header):
            norm_h = h.lower().replace(" ", "").replace("_", "").replace("-", "")
            for p in possible_headers:
                norm_p = p.lower().replace(" ", "").replace("_", "").replace("-", "")
                if norm_h == norm_p or norm_p in norm_h:
                    return idx
        return None

    app_col_idx = find_col_index(["Application Number", "Applicant", "Application ID", "App No"])
    part_a_col_idx = find_col_index(["Part A Marks", "Part A", "Part-A Total Mark Scored"])
    part_b_col_idx = find_col_index(["Part B Marks", "Part B", "Part-B Total Marks Scored"])
    status_col_idx = find_col_index(["Status", "Result Status", "Result"])

    if app_col_idx is None:
        frappe.throw(_("Column 'Application Number' not found in file headers. File headers found: {0}").format(", ".join(header)))

    if part_a_col_idx is None and part_b_col_idx is None and status_col_idx is None:
        frappe.throw(_("Neither 'Part A Marks', 'Part B Marks', nor 'Status' column was found in the uploaded file."))

    # Collect statistics and log errors
    success_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []

    data_rows = raw_rows[1:]
    total_rows = len(data_rows)

    # Process in chunks/transactions
    for row_num, row in enumerate(data_rows, start=2):
        if not row or not any(cstr(c).strip() for c in row):
            skipped_count += 1
            continue

        app_no = cstr(row[app_col_idx]).strip() if app_col_idx < len(row) else ""
        if not app_no:
            skipped_count += 1
            continue

        # Find Entrance Test Seat Allocation record by applicant or name
        alloc_name = frappe.db.get_value("Entrance Test Seat Allocation", {"applicant": app_no}, "name")
        if not alloc_name:
            # Fallback: check if row contains seat allocation docname directly
            alloc_name = frappe.db.get_value("Entrance Test Seat Allocation", {"name": app_no}, "name")

        if not alloc_name:
            errors.append({
                "row": row_num,
                "application_number": app_no,
                "error": f"Application Number '{app_no}' not found in seat allocations."
            })
            continue

        # Extract values
        part_a_raw = cstr(row[part_a_col_idx]).strip() if (part_a_col_idx is not None and part_a_col_idx < len(row)) else ""
        part_b_raw = cstr(row[part_b_col_idx]).strip() if (part_b_col_idx is not None and part_b_col_idx < len(row)) else ""
        status_raw = cstr(row[status_col_idx]).strip() if (status_col_idx is not None and status_col_idx < len(row)) else ""

        has_part_a = part_a_raw != ""
        has_part_b = part_b_raw != ""
        has_status = status_raw != ""

        if not has_part_a and not has_part_b and not has_status:
            skipped_count += 1
            continue

        # Fetch current record values
        current_doc = frappe.db.get_value(
            "Entrance Test Seat Allocation",
            alloc_name,
            ["part_a_total_marks_scored", "part_b_total_marks_scored", "total_marks", "result_status", "applicant"],
            as_dict=True
        )

        update_dict = {}

        if has_part_a:
            try:
                new_part_a = flt(part_a_raw)
                if current_doc.part_a_total_marks_scored != new_part_a:
                    update_dict["part_a_total_marks_scored"] = new_part_a
            except Exception as e:
                errors.append({
                    "row": row_num,
                    "application_number": app_no,
                    "error": f"Invalid Part A Marks '{part_a_raw}': {str(e)}"
                })
                continue

        if has_part_b:
            try:
                new_part_b = flt(part_b_raw)
                if current_doc.part_b_total_marks_scored != new_part_b:
                    update_dict["part_b_total_marks_scored"] = new_part_b
            except Exception as e:
                errors.append({
                    "row": row_num,
                    "application_number": app_no,
                    "error": f"Invalid Part B Marks '{part_b_raw}': {str(e)}"
                })
                continue

        if has_status:
            if current_doc.result_status != status_raw:
                update_dict["result_status"] = status_raw

        if update_dict:
            # Calculate final cumulative total & percentage
            part_a = update_dict.get("part_a_total_marks_scored", current_doc.part_a_total_marks_scored or 0)
            part_b = update_dict.get("part_b_total_marks_scored", current_doc.part_b_total_marks_scored or 0)
            total_sec = part_a + part_b
            max_marks = current_doc.total_marks or 200

            percentage = flt((total_sec / float(max_marks)) * 100.0, 2) if max_marks > 0 else 0.0

            if has_part_a or has_part_b:
                update_dict["total_marks_secured_in_part_a_b"] = total_sec
                update_dict["percentage"] = percentage

            # Load the full document to ensure all validations run
            doc = frappe.get_doc("Entrance Test Seat Allocation", alloc_name)
            doc.update(update_dict)
            if hasattr(doc, "recalculate_result_status"):
                doc.recalculate_result_status()
            doc.flags.ignore_permissions = True
            doc.save()

            updated_count += 1
        
        success_count += 1

        if row_num % 100 == 0:
            frappe.db.commit()

    frappe.db.commit()

    return {
        "total_rows": total_rows,
        "success_count": success_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "error_count": len(errors),
        "errors": errors
    }
