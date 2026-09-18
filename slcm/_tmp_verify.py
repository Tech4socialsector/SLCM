import frappe

def execute():
    frappe.set_user("Administrator")
    from frappe.desk.doctype.desktop_icon.desktop_icon import get_desktop_icons
    from frappe.boot import get_desktop_icon_urls
    frappe.cache.hdel("desktop_icons", frappe.session.user)
    icons = {i["label"]: i for i in get_desktop_icons(bootinfo=True)}
    urls = get_desktop_icon_urls()
    for label in ["Attendance","Hostel Management","IT Team","Placement","Venue Bookings",
                  "Promotions","REGO","SLCM Master","Student Portal","Fees Management","Programme Management"]:
        icon = icons.get(label)
        app = icon.get("app") if icon else None
        scrubbed = label.replace(" ", "_").lower()
        url = f"assets/{app}/icons/desktop_icons/solid/{scrubbed}.svg"
        exists = bool(app) and url in urls.get(app, {}).get("solid", [])
        print(label, "| app=", app, "| resolves=", exists)
