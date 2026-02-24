import frappe

def print_last_error():
    frappe.connect()
    last_log = frappe.get_all("Error Log", fields=["method", "traceback"], order_by="creation desc", limit=1)
    if last_log:
        print(f"Method: {last_log[0].method}")
        print(f"Traceback:\n{last_log[0].traceback}")
    else:
        print("No error logs found.")

if __name__ == "__main__":
    import sys
    site = sys.argv[1] if len(sys.argv) > 1 else None
    if site:
        frappe.init(site=site)
        print_last_error()
    else:
        print("Please provide a site name.")
