__version__ = "0.0.1"

# crm/crm/api/doc.py imports get_dynamic_linked_docs and get_linked_docs from
# frappe.model.delete_doc, but these were removed in frappe v16. Patch them in
# here so the import succeeds. This runs when frappe first imports the slcm
# package, well before crm's after_migrate hook triggers that import.
def _patch_frappe_delete_doc():
	import frappe.model.delete_doc as _m
	from frappe.model.dynamic_links import get_dynamic_link_map

	if not hasattr(_m, "get_linked_docs"):

		def get_linked_docs(doctype, name, linkinfo=None):
			from frappe.desk.form.linked_with import get_linked_docs as _fn

			return _fn(doctype=doctype, name=name, linkinfo=linkinfo)

		_m.get_linked_docs = get_linked_docs

	if not hasattr(_m, "get_dynamic_linked_docs"):

		def get_dynamic_linked_docs(doctype, name):
			import frappe

			result = {}
			for df in get_dynamic_link_map().get(doctype, []):
				meta = frappe.get_meta(df.parent)
				if meta.issingle:
					refdoc = frappe.db.get_singles_dict(df.parent)
					if refdoc.get(df.options) == doctype and refdoc.get(df.fieldname) == name:
						result.setdefault(df.parent, []).append({"name": df.parent})
				else:
					rows = frappe.db.sql(
						"select `name` from `tab{parent}` where `{options}`=%s and `{fieldname}`=%s".format(
							**df
						),
						(doctype, name),
						as_dict=True,
					)
					if rows:
						result.setdefault(df.parent, []).extend(rows)
			return result

		_m.get_dynamic_linked_docs = get_dynamic_linked_docs


_patch_frappe_delete_doc()
