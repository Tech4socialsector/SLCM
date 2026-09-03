import frappe
from frappe.utils import now
import json
import io
import openpyxl
import traceback

@frappe.whitelist()
def parse_import_file(file_url, exam_plan, evaluation_schema, exam_component=None, assessment_type=None, re_exam_component=None, re_exam_assessment_type=None):
    if not exam_plan or not evaluation_schema:
        frappe.throw("Exam Plan and Evaluation Schema are mandatory.")
        
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    content = file_doc.get_content()
    
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    sheet = wb.active
    
    headers = []
    log = None
    
    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(c).strip() if c is not None else "" for c in row]
            
            # Create log as soon as we have headers
            log = frappe.get_doc({
                "doctype": "Marks Import Log",
                "import_file": file_url,
                "exam_plan": exam_plan,
                "evaluation_schema": evaluation_schema,
                "exam_component": exam_component,
                "assessment_type": assessment_type,
                "re_exam_component": re_exam_component,
                "re_exam_assessment_type": re_exam_assessment_type,
                "status": "Queued",
                "total_rows": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "missing_offerings_count": 0
            })
            log.insert(ignore_permissions=True)
            continue
            
        row_dict = {}
        empty = True
        for j, cell in enumerate(row):
            if j < len(headers):
                val = cell if cell is not None else ""
                row_dict[headers[j]] = val
                if str(val).strip():
                    empty = False
                    
        if not empty:
            reg_id = row_dict.get("Registration ID")
            course_code = row_dict.get("Course Code")
            term_name = row_dict.get("Term Name")
            
            detail = frappe.new_doc("Marks Import Log Detail")
            detail.import_log = log.name
            detail.row_number = i + 1
            detail.registration_id = str(reg_id)[:255] if reg_id else ""
            detail.course_code = str(course_code)[:255] if course_code else ""
            detail.term_name = str(term_name)[:255] if term_name else ""
            detail.status = "Pending"
            detail.raw_row_json = json.dumps(row_dict)
            detail.flags.ignore_permissions = True
            detail.insert()
            log.total_rows += 1

    if log:
        log.db_update()
        return {"import_log": log.name}
    return None

@frappe.whitelist()
def delete_import_log(import_log):
    if not import_log: return
    frappe.db.delete("Marks Import Log Detail", {"import_log": import_log})
    frappe.delete_doc("Marks Import Log", import_log, ignore_permissions=True)

@frappe.whitelist()
def get_preview_page(import_log, page=1, page_size=50):
    page = int(page)
    page_size = int(page_size)
    details = frappe.get_all("Marks Import Log Detail", 
        filters={"import_log": import_log},
        fields=["name", "row_number", "status", "registration_id", "course_code", "term_name", "raw_row_json"],
        order_by="row_number asc",
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size
    )
    
    for d in details:
        if d.raw_row_json:
            d.raw_data = json.loads(d.raw_row_json)
        else:
            d.raw_data = {}
            
    total = frappe.db.count("Marks Import Log Detail", {"import_log": import_log})
    return {
        "rows": details,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@frappe.whitelist()
def get_errors_page(import_log, page=1, page_size=20, status_filter=None):
    page = int(page)
    page_size = int(page_size)
    
    filters = {"import_log": import_log}
    if status_filter:
        filters["status"] = status_filter
    else:
        filters["status"] = ["!=", "Valid"]
        
    details = frappe.get_all("Marks Import Log Detail", 
        filters=filters,
        fields=["name", "row_number", "status", "error_reason"],
        order_by="row_number asc",
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size
    )
    total = frappe.db.count("Marks Import Log Detail", filters=filters)
    return {
        "rows": details,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@frappe.whitelist()
def validate_staged_rows(import_log):
    return _validate_import_log(import_log, retry_mode=False)

def _validate_import_log(import_log, retry_mode=False):
    filters = {"import_log": import_log}
    if retry_mode:
        filters["status"] = ["in", ["Failed", "Missing Student", "Missing Course", "Missing Course Offering", "Duplicate (Skip)"]]
    else:
        filters["status"] = "Pending"
        
    details = frappe.get_all("Marks Import Log Detail", filters=filters, pluck="name")
    missing_offering_groups = {}
    
    for docname in details:
        doc = frappe.get_doc("Marks Import Log Detail", docname)
        row = json.loads(doc.raw_row_json)
        
        reg_id = row.get("Registration ID")
        course_code = row.get("Course Code")
        term_name = row.get("Term Name")
        batch = row.get("Batch Year")
        
        status = "Valid"
        error_reason = ""
        
        try:
            student = resolve_student(reg_id)
            if not student:
                status = "Missing Student"
                raise Exception(f"Student not found for Registration ID {reg_id}")
                
            course_name = frappe.db.get_value("Course", {"course_code": course_code}, "name")
            if not course_name:
                course_name = frappe.db.get_value("Course", {"name": course_code}, "name")
                
            if not course_name:
                status = "Missing Course"
                raise Exception(f"Course Code {course_code} does not exist in Course master")
                
            course_offering = resolve_course_offering(course_code, batch, term_name)
            if not course_offering:
                group_key = (course_code, batch, term_name)
                if group_key not in missing_offering_groups:
                    missing_offering_groups[group_key] = 0
                missing_offering_groups[group_key] += 1
                status = "Missing Course Offering"
                raise Exception(f"No Course Offering for Course Code {course_code}, Batch {batch}, Term {term_name}")
                
            existing = frappe.db.exists("Student Course Marks", {
                "student": student,
                "course_offering": course_offering
            })
            
            if existing:
                status = "Duplicate (Skip)"
                raise Exception("Student Course Marks already exists")
                
        except Exception as e:
            error_reason = str(e)
            
        doc.db_set("status", status)
        doc.db_set("error_reason", error_reason)
        
    # Aggregate counts
    valid_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log, "status": "Valid"})
    error_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log, "status": "Failed"})
    skip_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log, "status": "Duplicate (Skip)"})
    missing_student_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log, "status": "Missing Student"})
    missing_course_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log, "status": "Missing Course"})
    missing_off_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log, "status": "Missing Course Offering"})
    
    if not missing_offering_groups:
        missing_offs = frappe.get_all("Marks Import Log Detail", {"import_log": import_log, "status": "Missing Course Offering"}, ["course_code", "term_name", "raw_row_json"])
        for m in missing_offs:
            r = json.loads(m.raw_row_json) if m.raw_row_json else {}
            b = r.get("Batch Year", "")
            k = (m.course_code, b, m.term_name)
            if k not in missing_offering_groups:
                missing_offering_groups[k] = 0
            missing_offering_groups[k] += 1

    missing_groups_list = [
        {"course_code": k[0], "batch": k[1], "term_name": k[2], "affected_row_count": v}
        for k, v in missing_offering_groups.items()
    ]

    return {
        "valid_count": valid_count,
        "error_count": error_count,
        "skip_count": skip_count,
        "missing_student_count": missing_student_count,
        "missing_course_count": missing_course_count,
        "missing_offering_count": missing_off_count,
        "missing_offering_groups": missing_groups_list
    }

@frappe.whitelist()
def start_bulk_import(import_log, skip_blocked=True):
    log = frappe.get_doc("Marks Import Log", import_log)
    log.db_set("status", "Queued")
    
    frappe.enqueue(
        method="slcm.slcm.doctype.student_course_marks.marks_bulk_import.process_import",
        queue="long",
        timeout=3600,
        import_log_name=import_log,
        triggering_user=frappe.session.user
    )
    
    return {"import_log": log.name}

@frappe.whitelist()
def retry_failed_rows(import_log):
    retry_statuses = ["Failed", "Missing Student", "Missing Course", "Missing Course Offering", "Duplicate (Skip)"]
    detail_names = frappe.get_all("Marks Import Log Detail",
        filters={"import_log": import_log, "status": ["in", retry_statuses]},
        pluck="name")
    
    if not detail_names:
        frappe.msgprint("No failed/pending rows to retry.")
        return

    _validate_import_log(import_log, retry_mode=True)
    
    log = frappe.get_doc("Marks Import Log", import_log)
    log.db_set("status", "Queued")
    
    frappe.enqueue(
        method="slcm.slcm.doctype.student_course_marks.marks_bulk_import.process_import",
        queue="long",
        timeout=3600,
        import_log_name=import_log,
        retry_scope=detail_names,
        triggering_user=frappe.session.user
    )
    return {"status": "Queued"}

def process_import(import_log_name, retry_scope=None, triggering_user=None):
    log = frappe.get_doc("Marks Import Log", import_log_name)
    log.db_set("status", "In Progress")
    if not triggering_user:
        triggering_user = log.imported_by
        
    filters = {"import_log": import_log_name, "status": "Valid"}
    if retry_scope:
        filters["name"] = ["in", retry_scope]
        
    valid_details = frappe.get_all("Marks Import Log Detail", 
        filters=filters,
        pluck="name"
    )
    
    total = len(valid_details)
    success_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log_name, "status": "Success"})
    
    if total == 0:
        frappe.publish_realtime("marks_import_progress", {
            "import_log": import_log_name,
            "progress": 0,
            "total": 0
        }, user=triggering_user)
        
    for i, docname in enumerate(valid_details):
        if i % 25 == 0:
            frappe.publish_realtime("marks_import_progress", {
                "import_log": import_log_name,
                "progress": i,
                "total": total
            }, user=triggering_user)
            
        detail = frappe.get_doc("Marks Import Log Detail", docname)
        row = json.loads(detail.raw_row_json)
        
        reg_id = row.get("Registration ID")
        course_code = row.get("Course Code")
        term_name = row.get("Term Name")
        batch = row.get("Batch Year")
        
        try:
            student = resolve_student(reg_id)
            course_offering = resolve_course_offering(course_code, batch, term_name)
            
            course_name = frappe.db.get_value("Course", {"course_code": course_code}, "name")
            if not course_name:
                course_name = frappe.db.get_value("Course", {"name": course_code}, "name")
                
            doc = frappe.new_doc("Student Course Marks")
            doc.student = student
            doc.student_id = reg_id
            doc.course_offering = course_offering
            doc.course = course_name or course_code
            doc.exam_plan = log.exam_plan
            doc.evaluation_schema = log.evaluation_schema
            doc.status = "Submitted"
            
            grade_point = row.get("Grade Point")
            try:
                gp_val = float(grade_point)
            except:
                gp_val = 0.0
            doc.consider_for_sgpa = 0 if gp_val == 0.0 else 1
            
            doc.total_marks = row.get("Total Marks")
            doc.grade = row.get("Grade")
            doc.re_exam_grade = row.get("Re-Exam Grade")
            
            computed = compute_updated_final(row)
            doc.updated_final_marks = computed["updated_final_marks"]
            doc.updated_grade = computed["updated_grade"]
            doc.improvement_marks = computed["improvement_marks"]
            doc.improvement_grade = computed["improvement_grade"]
            doc.improvement_applied = computed["improvement_applied"]
            
            if log.exam_component and log.assessment_type:
                doc.append("marks_entries", {
                    "component": log.exam_component,
                    "assessment_type": log.assessment_type,
                    "marks": doc.total_marks
                })
            
            if row.get("Re-Exam Total Marks") and log.re_exam_component and log.re_exam_assessment_type:
                doc.append("marks_entries", {
                    "component": log.re_exam_component,
                    "assessment_type": log.re_exam_assessment_type,
                    "marks": row.get("Re-Exam Total Marks"),
                    "is_reexam": 1
                })
            
            doc.flags.ignore_permissions = True
            doc.insert()
            
            detail.db_set("status", "Success")
            detail.db_set("student_course_marks", doc.name)
            detail.db_set("error_reason", "")
            success_count += 1
            
        except Exception as e:
            err_msg = traceback.format_exc()
            detail.db_set("status", "Failed")
            detail.db_set("error_reason", str(e) + "\n" + err_msg)
            
    if total > 0:
        frappe.publish_realtime("marks_import_progress", {
            "import_log": import_log_name,
            "progress": total,
            "total": total
        }, user=triggering_user)
    
    # Final counts for Log
    failed_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log_name, "status": "Failed"})
    missing_student = frappe.db.count("Marks Import Log Detail", {"import_log": import_log_name, "status": "Missing Student"})
    missing_course = frappe.db.count("Marks Import Log Detail", {"import_log": import_log_name, "status": "Missing Course"})
    missing_off_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log_name, "status": "Missing Course Offering"})
    skipped_count = frappe.db.count("Marks Import Log Detail", {"import_log": import_log_name, "status": "Duplicate (Skip)"})
    
    total_failed = failed_count + missing_student + missing_course + missing_off_count
    
    log.db_set({
        "success_count": success_count,
        "failed_count": total_failed,
        "skipped_count": skipped_count,
        "missing_offerings_count": missing_off_count,
        "status": "Completed with Errors" if total_failed > 0 else "Completed"
    })
    
def compute_updated_final(row):
    original_grade = row.get("Grade") or ""
    try:
        total_marks = float(row.get("Total Marks") or 0)
    except:
        total_marks = 0.0
        
    reexam_grade = row.get("Re-Exam Grade")
    try:
        reexam_total_marks = float(row.get("Re-Exam Total Marks") or 0) if row.get("Re-Exam Total Marks") else None
    except:
        reexam_total_marks = None
        
    if reexam_total_marks is None:
        return {
            "updated_final_marks": total_marks,
            "updated_grade": original_grade,
            "improvement_marks": 0,
            "improvement_grade": "",
            "improvement_applied": 0
        }
        
    if original_grade == 'F' and reexam_grade != 'F':
        return {
            "updated_final_marks": reexam_total_marks,
            "updated_grade": reexam_grade,
            "improvement_marks": reexam_total_marks,
            "improvement_grade": reexam_grade,
            "improvement_applied": 0
        }
        
    if original_grade != 'F' and reexam_total_marks > total_marks:
        return {
            "updated_final_marks": total_marks,
            "updated_grade": original_grade,
            "improvement_marks": reexam_total_marks,
            "improvement_grade": reexam_grade,
            "improvement_applied": 1
        }
        
    return {
        "updated_final_marks": total_marks,
        "updated_grade": original_grade,
        "improvement_marks": reexam_total_marks,
        "improvement_grade": reexam_grade,
        "improvement_applied": 0
    }

def resolve_student(registration_id):
    if not registration_id: return None
    return frappe.db.get_value("Student Master", {"registration_id": registration_id}, "name")

def resolve_course_offering(course_code, batch, term_name):
    if not (course_code and batch and term_name): return None
    course_name = frappe.db.get_value("Course", {"course_code": course_code}, "name")
    if not course_name:
        course_name = frappe.db.get_value("Course", {"name": course_code}, "name")
    
    if not course_name: return None
    
    return frappe.db.get_value("Course Offering", {
        "course_title": course_name,
        "cohort": batch,
        "term_name": term_name
    }, "name")

@frappe.whitelist()
def download_sample_template():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sample Template"
    
    headers = [
        "Term Name", "Registration ID", "Student Name", "Programme Name", 
        "Batch Year", "Department Name", "Course Code", "Course Name", 
        "Total Marks", "Grade", "Grade Point", "Re-Exam Total Marks", 
        "Re-Exam Grade", "Re-Exam Grade Point", "SGPA", "CGPA"
    ]
    ws.append(headers)
    
    ws.append([
        "T1-2025-2026", "REG001", "John Doe", "B.A., LL.B.", 
        "B-AY 2025-2026", "Law", "LAW101", "Legal Methods", 
        85, "A", 4.0, "", "", "", 4.0, 4.0
    ])
    
    ws.append([
        "T1-2025-2026", "REG002", "Jane Smith", "B.A., LL.B.", 
        "B-AY 2025-2026", "Law", "LAW102", "Contracts", 
        45, "F", 0.0, 75, "B", 3.0, 2.5, 3.0
    ])
    
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    
    frappe.response['filename'] = "Student_Marks_Import_Template.xlsx"
    frappe.response['filecontent'] = stream.read()
    frappe.response['type'] = 'download'

def _download_csv(headers, data, filename):
    import csv
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(data)
    frappe.response['result'] = stream.getvalue()
    frappe.response['type'] = 'csv'
    frappe.response['doctype'] = filename

@frappe.whitelist()
def download_missing_course_offerings(import_log):
    rows = frappe.db.sql("""
        SELECT course_code, term_name, count(*) as affected_row_count
        FROM `tabMarks Import Log Detail`
        WHERE import_log = %s AND status = 'Missing Course Offering'
        GROUP BY course_code, term_name
    """, (import_log,))
    _download_csv(["Course Code", "Term Name", "Affected Row Count"], rows, "Missing_Course_Offerings.csv")

@frappe.whitelist()
def download_missing_courses(import_log):
    rows = frappe.db.sql("""
        SELECT course_code, count(*) as affected_row_count
        FROM `tabMarks Import Log Detail`
        WHERE import_log = %s AND status = 'Missing Course'
        GROUP BY course_code
    """, (import_log,))
    _download_csv(["Course Code", "Affected Row Count"], rows, "Missing_Courses.csv")

@frappe.whitelist()
def download_missing_students(import_log):
    rows = frappe.db.sql("""
        SELECT registration_id, count(*) as affected_row_count
        FROM `tabMarks Import Log Detail`
        WHERE import_log = %s AND status = 'Missing Student'
        GROUP BY registration_id
    """, (import_log,))
    _download_csv(["Registration ID", "Affected Row Count"], rows, "Missing_Students.csv")
