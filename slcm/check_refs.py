import frappe

def run():
    cycles = ['test', 'AC-AY-2026-Test']
    for cycle in cycles:
        print(f"Checking references for Admission Cycle: {cycle}")
        
        # Check Applicant
        applicant_count = frappe.db.count('Applicant', {'admission_cycle': cycle})
        print(f"  Applicant count: {applicant_count}")
        
        # Check Campus Program Offering
        offering_count = frappe.db.count('Campus Program Offering', {'admission_cycle': cycle})
        print(f"  Campus Program Offering count: {offering_count}")
        
        # Check Merit Generation
        merit_count = frappe.db.count('Merit Generation', {'admission_cycle': cycle})
        print(f"  Merit Generation count: {merit_count}")

if __name__ == "__main__":
    run()
