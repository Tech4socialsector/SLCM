import frappe

def execute():
    meta = frappe.get_meta("Student Master")

    print("DB column info (DESCRIBE):")
    desc = frappe.db.sql("DESCRIBE `tabStudent Master`", as_dict=1)
    for col in desc:
        if col.get("Field") == "id_validity":
            print(col)

    print("Meta field:")
    df = meta.get_field("id_validity")
    print(df.as_dict() if df else None)

    print("Custom fields / property setters for id_validity:")
    cf = frappe.db.get_all("Custom Field", filters={"dt": "Student Master", "fieldname": "id_validity"}, fields=["*"])
    print(cf)
    ps = frappe.db.get_all("Property Setter", filters={"doc_type": "Student Master", "field_name": "id_validity"}, fields=["*"])
    print(ps)

    if frappe.db.db_type == 'mariadb':
        from frappe.database.mariadb.schema import MariaDBTable
        t = MariaDBTable("Student Master", meta)
        t.sync()
