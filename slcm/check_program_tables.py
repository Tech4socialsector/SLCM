
import frappe

def check_child_tables():
    frappe.connect()
    meta = frappe.get_meta("Program")
    table_fields = meta.get_table_fields()
    
    for df in table_fields:
        child_doctype = df.options
        table_name = "tab" + child_doctype
        print(f"Checking table: {table_name} for DocType: {child_doctype}")
        try:
            columns = frappe.db.get_table_columns(child_doctype)
            if "parent" not in columns:
                print(f"FAILED: 'parent' column missing in {table_name}")
            else:
                print(f"SUCCESS: 'parent' column found in {table_name}")
        except Exception as e:
            print(f"ERROR: {e}")
    frappe.destroy()

if __name__ == "__main__":
    check_child_tables()
