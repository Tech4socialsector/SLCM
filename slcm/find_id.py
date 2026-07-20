import frappe

def execute():
    res = frappe.db.sql("""
        SELECT TABLE_NAME, DATA_TYPE, COLUMN_TYPE 
        FROM information_schema.COLUMNS 
        WHERE COLUMN_NAME = 'id_validity' 
        AND TABLE_SCHEMA = DATABASE()
    """, as_dict=1)
    print("Tables with id_validity:")
    for row in res:
        print(row)
