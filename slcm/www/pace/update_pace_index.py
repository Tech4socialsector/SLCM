import re

file_path = "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/pace/index.html"
with open(file_path, "r") as f:
    content = f.read()

# 1. Fonts
content = content.replace(
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;0,6..72,700;1,6..72,400&display=swap" rel="stylesheet" />',
    '<link href="https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,400;0,700;1,300&display=swap" rel="stylesheet" />'
)

# 2. Tailwind Config
content = content.replace(
    '                    fontFamily: {\n                        "headline": ["Newsreader", "serif"],\n                        "body": ["Inter", "sans-serif"],\n                        "label": ["Inter", "sans-serif"]\n                    },',
    '                    fontFamily: {\n                        "headline": ["Merriweather", "Georgia", "serif"],\n                        "body": ["Merriweather", "Georgia", "serif"],\n                        "label": ["Merriweather", "Georgia", "serif"]\n                    },'
)

# 3. CSS Overrides
css_overrides = """
        /* Exact specifications requested by user */
        h1, h1.text-3xl, h1.md\\:text-4xl, h1.lg\\:text-4xl { font-size: 26px !important; line-height: 1.2 !important; }
        @media (max-width: 600px) { h1, h1.text-3xl, h1.md\\:text-4xl, h1.lg\\:text-4xl { font-size: 13px !important; } }
        .department-name, h2 { font-size: 21px !important; }
        @media (max-width: 600px) { .department-name, h2 { font-size: 15px !important; } }
        h3, h3.text-2xl { font-size: 20px !important; }
        .alert-notice, .lp-notify { font-size: 1rem !important; }
        label, .form-label { font-size: 13.5px !important; text-transform: none !important; }
        input { font-size: 13.5px !important; }
        .small-text, p { font-size: 12.5px !important; }
        button, .btn, a.btn { font-size: 12px !important; text-transform: uppercase !important; }
        .nav-link { font-size: 11.5px !important; text-transform: none !important; }
        @media (max-width: 600px) { .nav-link { font-size: 9.5px !important; } }

"""

content = content.replace(
    "    <style>\n        html {",
    "    <style>\n" + css_overrides + "        html {"
)

with open(file_path, "w") as f:
    f.write(content)

print("Done")
