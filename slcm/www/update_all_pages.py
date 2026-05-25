import re
import os

files = [
    "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/admission/index.html",
    "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/admission/program_detail.html",
    "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/pace/index.html",
    "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/pace/pace_programme_details.html",
    "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/pace_application_card/index.html",
    "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/pace_progress_tracker/index.html",
    "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/admission_base.html"
]

css_block = """
<style>
/* Exact specifications requested by user */
h1, h1.text-3xl, h1.md\\:text-4xl, h1.lg\\:text-4xl, .lp-brand-name { font-size: 26px !important; line-height: 1.2 !important; }
@media (max-width: 600px) { h1, h1.text-3xl, h1.md\\:text-4xl, h1.lg\\:text-4xl, .lp-brand-name { font-size: 13px !important; } }

.department-name, h2, h2.text-4xl, h2.md\\:text-5xl, .lp-tagline { font-size: 21px !important; }
@media (max-width: 600px) { .department-name, h2, h2.text-4xl, h2.md\\:text-5xl, .lp-tagline { font-size: 15px !important; } }

h3, h3.text-2xl, .lp-heading { font-size: 20px !important; }

.alert-notice, .lp-notify { font-size: 1rem !important; }

label, .form-label, .lp-label { font-size: 13.5px !important; text-transform: none !important; }

input, .lp-input { font-size: 13.5px !important; }

.small-text, p, .lp-sub, .lp-forgot, .lp-support-link { font-size: 12.5px !important; }

button, .btn, a.btn, .lp-btn { font-size: 12px !important; text-transform: uppercase !important; }

.nav-link, .lp-tab { font-size: 11.5px !important; text-transform: none !important; }
@media (max-width: 600px) { .nav-link, .lp-tab { font-size: 9.5px !important; } }
</style>
"""

merriweather_link = '<link href="https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,400;0,700;1,300&display=swap" rel="stylesheet">'

for file_path in files:
    if not os.path.exists(file_path):
        print(f"Skipping missing file: {file_path}")
        continue
        
    with open(file_path, "r") as f:
        content = f.read()

    # 1. Replace all google fonts API links with Merriweather
    content = re.sub(
        r'<link[^>]+href="https://fonts\.googleapis\.com/css2\?family=[^"]+"[^>]*>',
        merriweather_link,
        content
    )
    
    # 2. Update font-family inline css properties
    content = re.sub(
        r"font-family:\s*['\"A-Za-z\-, \.]+;", 
        "font-family: 'Merriweather', Georgia, serif !important;", 
        content
    )
    
    # 3. Update tailwind config fontFamily if present
    content = re.sub(
        r'"headline":\s*\[[^\]]+\]',
        '"headline": ["Merriweather", "Georgia", "serif"]',
        content
    )
    content = re.sub(
        r'"body":\s*\[[^\]]+\]',
        '"body": ["Merriweather", "Georgia", "serif"]',
        content
    )
    content = re.sub(
        r'"label":\s*\[[^\]]+\]',
        '"label": ["Merriweather", "Georgia", "serif"]',
        content
    )
    
    # 4. Inject CSS block
    if "{% block page_css %}" in content:
        content = content.replace("{% block page_css %}", "{% block page_css %}\n" + css_block)
    elif "</head>" in content:
        content = content.replace("</head>", css_block + "\n</head>")
    else:
        # Just put it at the top
        content = css_block + "\n" + content
        
    with open(file_path, "w") as f:
        f.write(content)

print("Updates applied to all pages.")
