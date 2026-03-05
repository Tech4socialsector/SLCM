import os, re

base = '/home/bsoft/slcm-bench-v16/apps/slcm/slcm/'
ok = True

def chk(label, cond):
    global ok
    if not cond: ok = False
    print(f"{'PASS' if cond else 'FAIL'}  {label}")

# portal.py fixes
portal = open(base + 'admission/utils/portal.py').read()
chk('portal.py: desciption (typo field)', 'desciption' in portal)
chk('portal.py: media_gallery parentfield', 'media_gallery' in portal)
chk('portal.py: brochure_pdf from Program Media', 'brochure_pdf' in portal)

# web.py
web = open(base + 'admission/utils/web.py').read()
chk('web.py: get_portal_notifications', 'get_portal_notifications' in web)
chk('web.py: check_existing_application', 'check_existing_application' in web)

# base template
base_html = open(base + 'www/admission_base.html').read()
chk('base: suppress Frappe navbar CSS', 'web-header' in base_html or 'web-navbar' in base_html or 'header.navbar' in base_html)
chk('base: {% block theme_vars %}', 'theme_vars' in base_html)
chk('base: toast-container', 'toast-container' in base_html)
chk('base: showToast function', 'showToast' in base_html)
chk('base: showConfirm function', 'showConfirm' in base_html)
chk('base: bell notifications', 'bellBtn' in base_html)
chk('base: logout with confirm', 'logout-btn' in base_html)
chk('base: confirm-overlay', 'confirm-overlay' in base_html)

# index.html
idx_html = open(base + 'www/admission/index.html').read()
chk('index.html: theme_vars block', 'theme_vars' in idx_html)
chk('index.html: hero_prev/next buttons', 'heroPrev' in idx_html)
chk('index.html: desc-toggle', 'toggleDesc' in idx_html)
chk('index.html: announcement cards', "window.location='/announcement/" in idx_html)
chk('index.html: applicant-form/new URL', 'applicant-form/new' in idx_html)

# announcement pages
chk('announcement/{name}.py exists', os.path.exists(base + 'www/announcement/{name}.py'))
chk('announcement/{name}.html exists', os.path.exists(base + 'www/announcement/{name}.html'))

# my-applications.py
my_py = open(base + 'www/my-applications.py').read()
chk('my-apps.py: candidate_name', 'candidate_name' in my_py)

# login.html
login_html = open(base + 'www/login.html').read()
chk('login.html: signup form updated', 'doRegister' in login_html)
chk('login.html: sign_up API call', 'sign_up' in login_html)

print()
print('ALL PASS' if ok else 'FIX FAILURES BEFORE TESTING')
