# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import nowdate, flt
from frappe.utils.file_manager import save_file

def _map_pace_to_student(student, pace_app):
    """
    Central mapping function: PACE Application fields -> Student Master fields.
    """
    
    # application_number tracks back to the PACE Application record.
    student.application_number = pace_app.name
    
    # Programme & Academic Year
    student.programme = pace_app.programme
    student.academic_year = pace_app.academic_year
    student.admission_type = "PACE"
    
    # Department (derived from programme/PACE Programme)
    # PACE Programme doesn't seem to have a department field in its JSON, 
    # but Student Master expects one. Let's try to fetch it if it exists or leave blank.
    
    # Personal Details
    student.first_name = pace_app.first_name
    student.middle_name = pace_app.middle_name
    student.last_name = pace_app.last_name
    student.dob = pace_app.date_of_birth
    student.email = pace_app.email_address
    student.personal_email = pace_app.email_address
    student.phone = pace_app.mobile_number
    student.nationality = pace_app.nationality
    
    # Gender mapping
    raw_gender = pace_app.gender
    if raw_gender:
        if frappe.db.exists("Genders", raw_gender):
            student.gender = raw_gender
        elif raw_gender == "Others" and frappe.db.exists("Genders", "Other"):
            student.gender = "Other"
            
    # Quota mapping
    raw_category = pace_app.category
    category_map = {
        "General": "General",
        "SC": "SC",
        "ST": "ST",
        "OBC": "OBC"
    }
    student.quota = category_map.get(raw_category, "General")
    
    # Address details (Correspondence)
    student.present_address = f"{pace_app.address_line_1}\n{pace_app.address_line_2 or ''}".strip()
    student.city = pace_app.city
    student.district = pace_app.district
    student.state = pace_app.state
    student.pincode = pace_app.pincode
    student.country = pace_app.country
    
    # Permanent Address
    if pace_app.is_permanent_address_same:
        student.permanent_address = student.present_address
    else:
        student.permanent_address = f"{pace_app.p_address_line_1}\n{pace_app.p_address_line_2 or ''}".strip()
        # Student Master doesn't have p_city, etc. as separate fields from main address fields usually,
        # but it does have city, pincode, country. Let's see if there are separate perm fields.
        # Student Master JSON showed only state, district, city, pincode, country (assumed for present).
        # Actually, Student Master has present_address and permanent_address (Text).
    
    # Documents
    student.passport_size_photo = pace_app.upload_student_photo
    student.aadhaar_card = pace_app.govt_id
    student.ug_certificate = pace_app.ug_degree_certificate
    student.signature_ppkg = pace_app.student_signature
    
    # UG Education Details (child table)
    if pace_app.get("ug_degree"):
        for row in pace_app.ug_degree:
            student.append("ug_degree_details", {
                "ug_program": row.programme_studied,
                "college": row.institution_name,
                "university": row.university,
                "year_of_completion": row.year_of_passing,
                "ug_cgpa": flt(row.obtained_percentagecgpa) if row.marking_scheme == "CGPA" else None,
                "ug_percentage": flt(row.obtained_percentagecgpa) if row.marking_scheme == "Percentage" else None,
                "ug_max_cgpa": 10.0 if row.marking_scheme == "CGPA" else None
            })
            
    # Parent Details
    if pace_app.father_name:
        student.append("parents", {
            "relation": "Father",
            "first_name": pace_app.father_name
        })
    if pace_app.mother_name:
        student.append("parents", {
            "relation": "Mother",
            "first_name": pace_app.mother_name
        })
        
    # Status
    student.student_status = "Active"
    student.account_status = "Active"
    student.registration_status = "Active"
    student.date_of_registration = nowdate()
    
    # User
    student.user = pace_app.email_address
    
    return student

def _update_user_roles(email):
    """
    Swap PACE Applicant/Applicant roles for Student role.
    """
    if not email:
        return
    try:
        user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            return
            
        user = frappe.get_doc("User", user_name)
        roles_updated = False
        
        existing_roles = [d.role for d in user.get("roles", [])]
        
        if "slcm_Student" not in existing_roles:
            user.append("roles", {"role": "slcm_Student"})
            roles_updated = True
                
        if roles_updated:
            user.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PACE User role update failed for: {email}")

@frappe.whitelist()
def convert_pace_to_student(pace_app_name):
    """
    Whitelist API to convert PACE Application to Student Master.
    """
    if not frappe.db.exists("PACE Application", pace_app_name):
        frappe.throw(_("PACE Application {0} not found.").format(pace_app_name))
        
    pace_app = frappe.get_doc("PACE Application", pace_app_name)
    
    # 1. Deduplication guard
    existing = frappe.db.get_value("Student Master", {"application_number": pace_app_name}, "name")
    if existing:
        return {"student_name": existing, "created": False}
        
    # 2. Email guard
    if pace_app.email_address:
        existing_by_email = frappe.db.get_value(
            "Student Master", 
            {"email": pace_app.email_address, "student_status": "Active"}, 
            "name"
        )
        if existing_by_email:
            frappe.throw(_("An active Student Master record ({0}) with this email already exists.").format(existing_by_email))
            
    # 3. Create Student Master
    try:
        student = frappe.new_doc("Student Master")
        student = _map_pace_to_student(student, pace_app)
        student.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
        student_name = student.name
        
        # 4. Update PACE Application status
        pace_app.status = "Enrolled"
        
        # Generate and attach Admission Letter
        try:
            pdf_content = frappe.get_print(
                "PACE Application",
                pace_app_name,
                "PACE Admission Letter",
                as_pdf=True
            )
            file_name = f"Admission_Letter_{pace_app_name}.pdf"
            saved_file = save_file(
                file_name,
                pdf_content,
                "PACE Application",
                pace_app_name,
                is_private=0
            )
            pace_app.admission_letter = saved_file.file_url
        except Exception as e:
            frappe.log_error(f"Failed to generate admission letter for {pace_app_name}: {str(e)}", "Admission Letter Generation Error")

        pace_app.save(ignore_permissions=True)
        
        # 4b. Update active Course Fee assignment status
        assignments = frappe.get_all("PACE Applicant Fee Assignment", filters={
            "applicant": pace_app_name,
            "fee_type": "Course Fee",
            "academic_year": pace_app.academic_year
        }, pluck="name")
        for assignment_name in assignments:
            assignment_doc = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
            if assignment_doc.status != "Enrolled":
                assignment_doc.status = "Enrolled"
                assignment_doc.save(ignore_permissions=True)
        
        # 5. Update user roles
        _update_user_roles(pace_app.email_address)
        
        return {"student_name": student_name, "created": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"PACE Application to Student conversion failed for {pace_app_name}")
        frappe.throw(_("Conversion failed: {0}").format(str(e)))
@frappe.whitelist()
def bulk_convert_pace_to_student(pace_apps):
    """
    Bulk convert PACE Applications to Student Master.
    Expects a list of application names.
    Returns a report dict with success, errors, and skipped.
    """
    if isinstance(pace_apps, str):
        pace_apps = frappe.parse_json(pace_apps)
        
    report = {
        "success": [],
        "errors": [],
        "skipped": []
    }
    
    for name in pace_apps:
        try:
            res = convert_pace_to_student(name)
            if res.get("created"):
                report["success"].append({"applicant": name, "student": res["student_name"]})
            else:
                report["skipped"].append({"applicant": name, "reason": _("Already converted to Student {0}").format(res["student_name"])})
        except Exception as e:
            report["errors"].append({"applicant": name, "error": str(e)})
            
    return report
@frappe.whitelist()
def bulk_convert_pace_fee_assignments_to_student(assignments):
    """
    Bulk convert PACE Applications associated with Fee Assignments to Student Master.
    Expects a list of Fee Assignment names.
    Returns a report dict.
    """
    if isinstance(assignments, str):
        assignments = frappe.parse_json(assignments)
        
    report = {
        "success": [],
        "errors": [],
        "skipped": []
    }
    
    for assignment_name in assignments:
        try:
            assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
            app_name = assignment.applicant
            
            if not app_name:
                report["errors"].append({"applicant": assignment_name, "error": _("No associated application found.")})
                continue
                
            if assignment.fee_type != "Course Fee":
                report["skipped"].append({"applicant": app_name, "reason": _("Fee type is not Course Fee"), "assignment": assignment_name})
                continue
                
            pace_app_doc = frappe.get_doc("PACE Application", app_name)
            if assignment.academic_year != pace_app_doc.academic_year:
                report["skipped"].append({"applicant": app_name, "reason": _("Assignment academic year does not match active application academic year"), "assignment": assignment_name})
                continue
                
            res = convert_pace_to_student(app_name)
            if res.get("created"):
                # Reload to get updated status from convert_pace_to_student call
                assignment.reload()
                if assignment.status != "Enrolled":
                    assignment.status = "Enrolled"
                    assignment.save(ignore_permissions=True)
                
                report["success"].append({"applicant": app_name, "student": res["student_name"], "assignment": assignment_name})
            else:
                report["skipped"].append({"applicant": app_name, "reason": _("Already converted to Student {0}").format(res["student_name"]), "assignment": assignment_name})
        except Exception as e:
            report["errors"].append({"applicant": assignment_name, "error": str(e)})
            
    return report
