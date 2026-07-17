import frappe
from frappe.database.schema import DBTable

def execute():
    # Mocking Meta
    meta = frappe.get_meta("Student Master")
    table = frappe.db.get_table_columns("Student Master")
    
    db_table = frappe.db.get_table_definition("Student Master")
    
    print("Table columns from DB:")
    for col in table:
        if col.get("fieldname") == "id_validity":
            print(col)
            
    print("Meta field:")
    df = meta.get_field("id_validity")
    print(df.as_dict() if df else None)
    
    # What query does Frappe generate?
    # Let's import the specific class
    if frappe.db.db_type == 'mariadb':
        from frappe.database.mariadb.schema import MariaDBTable
        t = MariaDBTable("Student Master", meta)
        query = t.get_alter_column_query()
        print("Generated ALTER Queries:")
        for q in query:
            if "id_validity" in q:
                print(q)
