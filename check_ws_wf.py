import frappe
ws = frappe.get_doc("Website Settings")
print(f"title: {ws.title}")
print(f"banner_image: {ws.banner_image}")
print(f"top_bar_items: {len(ws.top_bar_items)}")
print(f"navbar_template: {getattr(ws, 'navbar_template', 'NOT SET')}")
print(f"hide_navbar: {getattr(ws, 'hide_navbar', 'NOT SET')}")

print("
=== Web Forms ===")
wf = frappe.get_all("Web Form", fields=["name","route","doc_type","is_standard"], limit=10)
for w in wf:
    print(f"  {w.name}: route={w.route} doctype={w.doc_type}")
