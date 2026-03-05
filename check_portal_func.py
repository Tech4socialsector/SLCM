import frappe
from slcm.admission.utils.portal import get_portal_config
cfg = get_portal_config()
print("=== get_portal_config() RETURN ===")
print("type:", type(cfg))
print("primary_color   :", repr(cfg.get('primary_color')))
print("secondary_color :", repr(cfg.get('secondary_color')))
print("portal_title    :", repr(cfg.get('portal_title')))
print("portal_active   :", repr(cfg.get('portal_active')))
print("slideshow count :", len(cfg.get('slideshow_images', [])))
for i, s in enumerate(cfg.get('slideshow_images', [])):
    print(f"  slide[{i}] type={type(s)} keys={list(s.keys()) if hasattr(s,'keys') else 'NOT DICT'}")
    print(f"           image={repr(s.get('image') if hasattr(s,'get') else s.image)}")
