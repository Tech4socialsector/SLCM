import frappe
def run():
    html = frappe.get_print("Offer Letter", "OL-2026-01254", "Offer Letter", as_pdf=False)
    print("--- HEAD ---")
    print(html[:1000])
    print("--- STYLE ---")
    import re
    m = re.search(r'<style>.*?</style>', html, re.DOTALL)
    if m:
        print(m.group(0)[:500])
    else:
        print("NO STYLE TAG FOUND!")
