import frappe

def run():
    max_id = frappe.db.sql("select max(name) from tabApplicant where name like 'APP-2026-%%'")[0][0]
    print(f'Max ID: {max_id}')
    if max_id:
        last_val = int(max_id.split('-')[-1])
        print(f'Last Value: {last_val}')
        
        # Ensure the series exists and is updated
        frappe.db.sql("delete from tabSeries where name='APP-2026-'")
        frappe.db.sql("insert into tabSeries (name, current) values ('APP-2026-', %s)", (last_val,))
        
        # Also, check if there's an empty series that might be causing confusion
        frappe.db.sql("delete from tabSeries where name=''")
        
        frappe.db.commit()
        print('Series updated and empty series cleaned up.')
    else:
        print('No applicants found for 2026.')

if __name__ == "__main__":
    run()
