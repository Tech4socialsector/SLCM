import frappe
def run():
    html = frappe.get_print("Offer Letter", "OL-2026-01254", "Offer Letter", as_pdf=False)
    import re
    styles = re.findall(r'<style>(.*?)</style>', html, re.DOTALL)
    for i, s in enumerate(styles):
        print(f"--- STYLE {i} ---")
        if "letter-page" in s:
            print("FOUND LETTER-PAGE CSS!")
            print(s[:300])
