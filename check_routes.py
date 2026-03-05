import frappe
print(f"Frappe version: {frappe.__version__}")

from frappe.website.router import resolve_route
try:
    route = resolve_route("/admission/ba-llb-hons")
    print(f"resolve_route result: {route}")
except Exception as e:
    print(f"resolve_route error: {e}")

from frappe.website.router import get_pages
pages = get_pages()
for p in pages:
    if "admission" in p:
        print(f"Page found: {p}")
