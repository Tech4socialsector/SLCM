import frappe


@frappe.whitelist()
def get_scale():
    from slcm.slcm.doctype.cgpa_percentage_scale.cgpa_percentage_scale import get_scale as _get
    return _get()


@frappe.whitelist()
def save_scale(data):
    from slcm.slcm.doctype.cgpa_percentage_scale.cgpa_percentage_scale import save_scale as _save
    return _save(data)


@frappe.whitelist()
def populate_scale():
    from slcm.slcm.doctype.cgpa_percentage_scale.cgpa_percentage_scale import populate_scale as _pop
    return _pop()
