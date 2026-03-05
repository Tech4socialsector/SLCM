import frappe
def run():
    cycle = frappe.db.get_value('Admission Cycle', {'status': 'Active'}, 'name')
    progs = frappe.get_all('Admission Cycle Program', 
                          filters={'parent': cycle, 'is_active': 1}, 
                          fields=['program','program_name','seats','eligibility_hint','desciption','program_media','reservation_policy','brochure_url'])
    result = []
    for p in progs:
        result.append({
            'program': p.program,
            'name': p.program_name,
            'media': p.program_media,
            'slug': frappe.db.get_value('Program', p.program, 'program_slug')
        })
    print(result)

run()
