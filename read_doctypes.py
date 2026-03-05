import json, os
base = '/home/bsoft/slcm-bench-v16/apps/slcm/slcm/admission/doctype/'
doctypes = [
    'portal_announcement/portal_announcement.json',
    'applicant_notification/applicant_notification.json',
    'applicant_portal_config/applicant_portal_config.json',
    'portal_slideshow_image/portal_slideshow_image.json',
    'admission_cycle_program/admission_cycle_program.json',
    'program_media/program_media.json',
    'media/media.json',
]
for dt in doctypes:
    path = base + dt
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                d = json.load(f)
            print(f"=== {dt.split('/')[0]} ===")
            for f in d.get('fields', []):
                if f.get('fieldtype') not in ('Section Break','Column Break','HTML'):
                    print(f"  {f.get('fieldname')} | {f.get('fieldtype')} | {f.get('label','')}")
        except Exception as e:
            print(f"=== {dt.split('/')[0]} === ERROR: {e}")
    else:
        print(f"=== {dt.split('/')[0]} === FILE NOT FOUND")
