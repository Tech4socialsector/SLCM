import frappe
ws = frappe.get_doc("Website Settings")
print(f"app_name: {getattr(ws, 'app_name', 'MISSING')}")
print(f"banner_image: {ws.banner_image}")
print(f"top_bar_items: {len(ws.top_bar_items)}")
wf = frappe.get_all("Web Form", fields=["name","route","doc_type","is_standard"], limit=10)
print(f"Web Forms: {[dict(w) for w in wf]}")
