import frappe

def inspect():
    campus = "CAMP-0002"
    cycle = "AC-AY-2026-TEST"
    
    print("--- Waitlist Rules ---")
    rules = frappe.get_all("Waitlist Rule", filters={"campus": campus, "admission_cycle": cycle}, fields="*")
    for r in rules:
        print(f"Name: {r.name}, Status: {r.status}, Frequency: {r.upgrade_frequency}, Cutoff: {r.upgrade_cutoff_date}")
        
    print("\n--- Seat Allocation ---")
    allocations = frappe.get_all("Seat Allocation", filters={"campus": campus, "admission_cycle": cycle}, fields="*")
    for a in allocations:
        print(f"Name: {a.name}, Status: {a.status}")
        
    # Check a specific applicant from the screenshot: santhosh (APP-2026-00003 likely)
    # The screenshot shows "santhosh" at No. 3 with "Offer Declined"
    # Wait, the screenshot doesn't show ID for santhosh clearly, but No. 1 is ajay (APP-2026-...)
    
    print("\n--- Recent Audit Logs ---")
    logs = frappe.get_all("Admission Audit Log", limit=10, order_by="creation desc", fields="*")
    for l in logs:
        print(f"{l.creation}: {l.applicant} - {l.action_type} - {l.new_value}")

if __name__ == "__main__":
    import sys
    # Simulating frappe environment setup if needed, but assuming it runs in bench context
    inspect()
