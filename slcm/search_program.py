import frappe

def search_for_program():
    res = frappe.db.get_all("Program", filters={"name": ["like", "%Ph.D.%"]})
    print(f"Programs with Ph.D. in name: {res}")
    
    res = frappe.db.get_all("Program", filters={"program_name": ["like", "%Ph.D.%"]})
    print(f"Programs with Ph.D. in program_name: {res}")

if __name__ == "__main__":
    frappe.connect()
    search_for_program()
    frappe.destroy()
