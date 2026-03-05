import frappe
test_slug = 'ba-llb-hons'
print(f"Direct name match: {frappe.db.exists('Program', test_slug)}")
print(f"program_slug field match: {frappe.db.get_value('Program', {'program_slug': test_slug}, 'name')}")
all_progs = frappe.get_all('Program', fields=['name','program_slug'])
print(f"All programs: {[(p.name, p.program_slug) for p in all_progs]}")
