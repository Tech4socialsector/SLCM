import frappe
import re

def make_slug(name):
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\-]', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug

def run():
    programs = frappe.get_all("Program", fields=["name", "program_slug"])
    for p in programs:
        if not p.program_slug:
            slug = make_slug(p.name)
            frappe.db.set_value("Program", p.name, "program_slug", slug)
            print(f"Set slug: {p.name} -> {slug}")
        else:
            print(f"Already has slug: {p.name} -> {p.program_slug}")
    frappe.db.commit()
    print("Done")

if __name__ == "__main__":
    run()
