import frappe
cfg = frappe.get_single("Applicant Portal Config")
print("=== RAW DB VALUES ===")
print("primary_color   :", repr(cfg.primary_color))
print("secondary_color :", repr(cfg.secondary_color))
print("portal_title    :", repr(cfg.portal_title))
print("portal_active   :", repr(cfg.portal_active))
print("show_announce   :", repr(cfg.show_announcement))
print("header_announce :", repr(cfg.header_announcement))
print("slideshow count :", len(cfg.slideshow_images or []))
for i, s in enumerate(cfg.slideshow_images or []):
    print(f"  slide[{i}] image={repr(s.image)} caption={repr(s.caption)} seq={repr(s.sequence)}")
