import frappe

def create_test_data():
    # Step 1: Create Admission Year
    year_name = "2026-27"
    if not frappe.db.exists("Admission Year", year_name):
        ay = frappe.get_doc({
            "doctype": "Admission Year",
            "year": year_name,
            "is_active": 1,
            "description": "Academic Year 2026-27"
        })
        ay.insert(ignore_permissions=True)
        print(f"Created Admission Year: {ay.name}")
    else:
        frappe.db.set_value("Admission Year", year_name, "is_active", 1)
        print(f"Admission Year {year_name} already exists")

    # Step 2: Create Programs
    programs = [
        {"program_name": "BA LLB (Hons)", "program_shortcode": "BALLB"},
        {"program_name": "LLM", "program_shortcode": "LLM"},
        {"program_name": "PhD Law", "program_shortcode": "PHD"},
    ]
    created_programs = []
    for p in programs:
        if not frappe.db.exists("Program", p["program_name"]):
            prog = frappe.get_doc({"doctype": "Program", **p})
            prog.insert(ignore_permissions=True)
            print(f"Created Program: {prog.name}")
            created_programs.append(prog.name)
        else:
            print(f"Program exists: {p['program_name']}")
            created_programs.append(p["program_name"])

    # Step 3: Create Admission Cycle with programs
    cycle_name = "Cycle 2026-27 Final"
    
    if not frappe.db.exists("Admission Cycle", cycle_name):
        # Ensure Exam Type exists
        if not frappe.db.exists("Exam Type Config", "CLAT"):
            frappe.get_doc({
                "doctype": "Exam Type Config",
                "exam_name": "CLAT",
                "exam_code": "CLAT"
            }).insert(ignore_permissions=True)

        cycle = frappe.get_doc({
            "doctype": "Admission Cycle",
            "cycle_name": cycle_name,
            "admission_year": year_name,
            "status": "Active",
            "application_start": "2040-01-01 00:00:00",
            "application_end": "2040-06-30 23:59:59",
            "programs": [
                {
                    "program": created_programs[0],
                    "program_name": "BA LLB (Hons)",
                    "seats": 120,
                    "is_active": 1,
                    "exam_type": "CLAT",
                    "eligibility_hint": "10+2 with minimum 45% marks"
                },
                {
                    "program": created_programs[1],
                    "program_name": "LLM",
                    "seats": 40,
                    "is_active": 1,
                    "exam_type": "CLAT",
                    "eligibility_hint": "LLB degree with minimum 55% marks"
                },
                {
                    "program": created_programs[2],
                    "program_name": "PhD Law",
                    "seats": 20,
                    "is_active": 1,
                    "exam_type": "CLAT",
                    "eligibility_hint": "LLM with minimum 55% marks"
                }
            ]
        })
        cycle.insert(ignore_permissions=True)
        print(f"Created Admission Cycle: {cycle.name}")
    else:
        frappe.db.set_value("Admission Cycle", cycle_name, "status", "Active")
        print(f"Cycle {cycle_name} already exists")

    frappe.db.commit()
    print("\nDone. Open /applicant-portal to verify programs appear.")

if __name__ == "__main__":
    create_test_data()
