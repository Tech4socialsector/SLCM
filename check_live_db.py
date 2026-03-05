import frappe
import json

def format_doc(doc):
    return json.dumps(doc.as_dict(), indent=2, default=str)

# Portal config
cfg = frappe.get_single("Applicant Portal Config")
print("=== Applicant Portal Config ===")
print(f"primary_color: {cfg.primary_color}")
print(f"secondary_color: {cfg.secondary_color}")
print(f"portal_title: {cfg.portal_title}")
print(f"portal_active: {cfg.portal_active}")
print(f"hero_image: {cfg.hero_image}")
print(f"slideshow count: {len(cfg.slideshow_images or [])}")
for s in (cfg.slideshow_images or []):
    print(f"  idx={s.idx} image={s.image} caption={s.caption}")

# Active cycle
cycle = frappe.db.get_value("Admission Cycle", {"status": "Active"}, "name")
print(f"
=== Active Cycle: {cycle} ===")
if cycle:
    progs = frappe.get_all("Admission Cycle Program",
        filters={"parent": cycle, "is_active": 1},
        fields=["program","program_name","seats","eligibility_hint",
                "desciption","program_media","reservation_policy","brochure_url"])
    for p in progs:
        print(f"
  Program: {p.program}")
        print(f"    program_name: {p.program_name}")
        print(f"    desciption: {repr((p.desciption or '')[:80])}")
        print(f"    eligibility_hint: {repr(p.eligibility_hint)}")
        print(f"    program_media: {repr(p.program_media)}")
        print(f"    reservation_policy: {repr(p.reservation_policy)}")
        slug = frappe.db.get_value("Program", p.program, "program_slug")
        print(f"    program_slug: {repr(slug)}")
        # Check media
        if p.program_media:
            try:
                media_list = frappe.get_all("Media", filters={"parent": p.program_media}, fields=["*"])
                print(f"    media items: {len(media_list)}")
                for m in media_list:
                    print(f"      type={m.media_type} file={m.file} caption={m.caption}")
            except Exception as e:
                print(f"    media check failed: {e}")

# Portal Announcements
print("
=== Portal Announcements ===")
anns = frappe.get_all("Portal Announcement", fields=["*"], limit=5)
for a in anns:
    print(f"  {a.name}: {a.title} (Published: {a.publish_date})")

# Applicant Notifications sample
print("
=== Applicant Notification sample ===")
notifs = frappe.get_all("Applicant Notification", fields=["*"], limit=3)
for n in notifs:
    print(f"  {n.name}: applicant={n.applicant} type={n.notification_type} read={n.is_read}")

# Check Admission Application
print("
=== Admission Applications ===")
apps = frappe.get_all("Admission Application",
    fields=["name","applicant","program","status","creation"], limit=10)
for a in apps:
    print(f"  {a.name}: applicant={a.applicant} program={a.program} status={a.status}")

# Website Settings
ws = frappe.get_doc("Website Settings")
print("
=== Website Settings ===")
print(f"title: {ws.title}")
print(f"banner_image: {ws.banner_image}")

# Web Forms
print("
=== Web Forms ===")
wf = frappe.get_all("Web Form", fields=["name","route","doc_type","is_standard"], limit=10)
for w in wf:
    print(f"  {w.name}: route={w.route} doctype={w.doc_type}")
