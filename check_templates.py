import frappe, os

paths_to_check = [
    '/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/admission_base.html',
    '/home/bsoft/slcm-bench-v16/apps/slcm/slcm/templates/admission_base.html',
    '/home/bsoft/slcm-bench-v16/apps/frappe/frappe/templates/admission_base.html',
]
for p in paths_to_check:
    exists = os.path.exists(p)
    if exists:
        size = os.path.getsize(p)
        content = open(p).read()
        has_extra_css = '{% block extra_css %}' in content
        has_theme_vars = '{% block theme_vars %}' in content
        inside_style = False
        import re
        style_blocks = [(m.start(), m.end()) for m in re.finditer(r'<style[^>]*>.*?</style>', content, re.DOTALL)]
        extra_pos = content.find('{% block extra_css %}')
        if extra_pos > 0:
            inside_style = any(s < extra_pos < e for s,e in style_blocks)
        print(f"EXISTS {p}")
        print(f"  size={size} extra_css={has_extra_css} theme_vars={has_theme_vars} extra_css_inside_style={inside_style}")
    else:
        print(f"NOT FOUND {p}")
