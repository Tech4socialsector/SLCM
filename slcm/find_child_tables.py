import frappe

def find_child_tables_for_program():
    frappe.connect()
    tables = frappe.db.get_tables()
    for table in tables:
        try:
            columns = frappe.db.get_table_columns(table)
            if "parent" in columns and "parenttype" in columns:
                res = frappe.db.sql(f"SELECT COUNT(*) FROM `{table}` WHERE parenttype = 'Programme'")
                if res[0][0] > 0:
                    print(f"Table {table} HAS children for Program ({res[0][0]} rows)")
        except Exception:
            continue
    frappe.destroy()

if __name__ == "__main__":
    find_child_tables_for_program()
