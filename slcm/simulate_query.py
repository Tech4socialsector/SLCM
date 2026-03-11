import frappe

def simulate_load_children():
    child_tables = [
        "tabProgram Enrollment Course",
        "tabProgram Media",
        "tabProgram Curriculum Item",
        "tabProgram Career Item",
        "tabProgram Faculty Item"
    ]
    
    parent_name = "Ph.D. in Interdisciplinary Legal Studies"
    parent_type = "Program"
    
    for table in child_tables:
        print(f"Simulating query for {table}...")
        try:
            # We don't care about parentfield for now just checking if query fails
            frappe.db.sql(f"SELECT * FROM `{table}` WHERE parent=%s AND parenttype=%s", (parent_name, parent_type))
            print(f"Query for {table} SUCCEEDED")
        except Exception as e:
            print(f"Query for {table} FAILED: {e}")

if __name__ == "__main__":
    frappe.connect()
    simulate_load_children()
    frappe.destroy()
