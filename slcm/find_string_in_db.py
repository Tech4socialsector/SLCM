import frappe

def find_string_in_db():
    search_str = "%Ph.D.%Interdisciplinary%"
    tables = frappe.db.get_tables()
    for table in tables:
        try:
            columns = frappe.db.get_table_columns(table)
            for col in columns:
                try:
                    res = frappe.db.sql(f"SELECT `{col}` FROM `{table}` WHERE `{col}` LIKE %s LIMIT 1", (search_str,))
                    if res:
                        print(f"FOUND in Table: {table}, Column: {col}, Value: {res[0][0]}")
                except Exception:
                    continue
        except Exception:
            continue

if __name__ == "__main__":
    frappe.connect()
    find_string_in_db()
    frappe.destroy()
