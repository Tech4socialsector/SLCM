import os
base = '/home/bsoft/slcm-bench-v16/apps/slcm/slcm/'
ok = True

def chk(label, cond):
    global ok
    if not cond: ok = False
    print(f"{'PASS' if cond else 'FAIL'}  {label}")

# index.py
idx = open(base + 'www/admission/index.py').read()
chk('index.py: fill_badge', 'fill_badge' in idx)
chk('index.py: fill_pct', 'fill_pct' in idx)
chk('index.py: desc_short', 'desc_short' in idx)
chk('index.py: desc_has_more', 'desc_has_more' in idx)
chk('index.py: desciption typo field', 'desciption' in idx)

# index.html
html = open(base + 'www/admission/index.html').read()
chk('index.html: fill_badge', 'fill_badge' in html)
chk('index.html: fill-bar-inner', 'fill-bar-inner' in html)
chk('index.html: toggleCardDesc', 'toggleCardDesc' in html)
chk('index.html: desc-short-', 'desc-short-' in html)
chk('index.html: See more', 'See more' in html)

# program_detail.py
det_py = base + 'www/admission/program_detail.py'
name_py = base + 'www/admission/{name}.py'
d = open(det_py if os.path.exists(det_py) else name_py).read()
chk('program_detail.py: Program Reservation Category', 'Program Reservation Category' in d)
chk('program_detail.py: fill_badge', 'fill_badge' in d)
chk('program_detail.py: fill_pct', 'fill_pct' in d)

# program_detail.html
det_html = base + 'www/admission/program_detail.html'
name_html = base + 'www/admission/{name}.html'
h = open(det_html if os.path.exists(det_html) else name_html).read()
chk('program_detail.html: img.file', 'img.file' in h)
chk('program_detail.html: video-link-btn', 'video-link-btn' in h)
chk('program_detail.html: fill_badge', 'fill_badge' in h)

# web.py
web = open(base + 'admission/utils/web.py').read()
chk('web.py: get_user_type', 'get_user_type' in web)
chk('web.py: owner_fullname', 'owner_fullname' in web)
chk('web.py: image in announcement fields', '"image"' in web or "'image'" in web)

# login.html
lh = open(base + 'www/login.html').read()
chk('login.html: get_user_type API call', 'get_user_type' in lh)
chk('login.html: /desk redirect', '/desk' in lh)
chk('login.html: System User', 'System User' in lh)

# base
bh = open(base + 'www/admission_base.html').read()
chk('base: white badge background', 'background:#fff' in bh and 'bellBadge' in bh)
chk('base: avatarHtml', 'avatarHtml' in bh)
chk('base: owner_fullname', 'owner_fullname' in bh)

print()
print('ALL PASS' if ok else 'FIX FAILURES BEFORE TESTING')
