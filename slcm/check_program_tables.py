import frappe

def check_child_tables():
    child_tables = [
        "tabProgram Enrollment Course",
        "tabProgram Media",
        "tabProgram Curriculum Item",
        "tabProgram Career Item",
        "tabProgram Faculty Item"
    ]
    
    for table in child_tables:
        print(f"Checking table: {table}")
        try:
            columns = frappe.db.get_table_columns(table)
            print(f"Columns: {columns}")
            if "parent" not in columns:
                print(f"!!! MISSING 'parent' in {table}")
        except Exception as e:
            print(f"Error checking {table}: {e}")

if __name__ == "__main__":
    frappe.connect()
    check_child_tables()
    frappe.destroy()
