import re
import sys

file_path = "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/www/pace/login.html"
try:
    with open(file_path, "r") as f:
        content = f.read()
except FileNotFoundError:
    print(f"File not found: {file_path}")
    sys.exit(1)

# 1. Fonts
content = content.replace(
    '<link rel="stylesheet"\n    href="https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700;800;900&display=swap">',
    '<link rel="stylesheet"\n    href="https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,400;0,700;1,300&display=swap">'
)
content = content.replace(
    "html, body { height: 100%; font-family: 'Lexend', sans-serif; background: #f1f3f5; overflow-x: hidden; }",
    "html, body { height: 100%; font-family: 'Merriweather', Georgia, serif; background: #f1f3f5; overflow-x: hidden; }"
)

# 2 & 3. Heading Sizes & Subheading Sizes
content = content.replace(
    ".lp-notify {\n      display: none; align-items: center; gap: 10px;\n      padding: 10px 14px; border-radius: 8px; margin-bottom: 20px;\n      font-size: 13px; font-weight: 600; animation: fadeIn .2s ease;\n    }",
    ".lp-notify {\n      display: none; align-items: center; gap: 10px;\n      padding: 10px 14px; border-radius: 8px; margin-bottom: 20px;\n      font-size: 1rem; font-weight: 600; animation: fadeIn .2s ease;\n    }"
)

content = content.replace(
    ".lp-brand-name { font-size: 18px; font-weight: 800; color: var(--primary); line-height: 1.2; }",
    ".lp-brand-name { font-size: 26px; font-weight: 800; color: var(--primary); line-height: 1.2; }"
)

content = content.replace(
    ".lp-heading { font-size: 28px; font-weight: 900; color: #111827; margin-bottom: 6px; }",
    ".lp-heading { font-size: 20px; font-weight: 900; color: #111827; margin-bottom: 6px; }"
)

content = content.replace(
    ".lp-sub     { font-size: 13px; color: #6b7280; margin-bottom: 30px; line-height: 1.5; }",
    ".lp-sub     { font-size: 12.5px; color: #6b7280; margin-bottom: 30px; line-height: 1.5; }"
)

content = content.replace(
    ".lp-tab {\n      padding: 9px 22px; font-size: 13px; font-weight: 600;",
    ".lp-tab {\n      padding: 9px 22px; font-size: 11.5px; font-weight: 600;"
)

content = content.replace(
    ".lp-label { display: block; font-size: 12px; font-weight: 700;",
    ".lp-label { display: block; font-size: 13.5px; font-weight: 700;"
)

content = content.replace(
    ".lp-input {\n      width: 100%; padding: 11px 14px; border: 1.5px solid #d1d5db;\n      border-radius: 8px; font-size: 13px; color: #111827;",
    ".lp-input {\n      width: 100%; padding: 11px 14px; border: 1.5px solid #d1d5db;\n      border-radius: 8px; font-size: 13.5px; color: #111827;"
)

content = content.replace(
    ".lp-forgot { font-size: 12px; color: var(--primary); font-weight: 600; text-decoration: none; }",
    ".lp-forgot { font-size: 12.5px; color: var(--primary); font-weight: 600; text-decoration: none; }"
)

content = content.replace(
    ".lp-btn {\n      width: 100%; padding: 13px; background: var(--primary); color: #fff;\n      border: none; border-radius: 8px; font-size: 13px; font-weight: 700;\n      cursor: pointer; font-family: inherit; letter-spacing: .03em;\n      transition: opacity .2s, transform .1s;\n      display: flex; align-items: center; justify-content: center; gap: 8px;\n    }",
    ".lp-btn {\n      width: 100%; padding: 13px; background: var(--primary); color: #fff;\n      border: none; border-radius: 8px; font-size: 12px; font-weight: 700;\n      cursor: pointer; font-family: inherit; letter-spacing: .03em;\n      text-transform: uppercase;\n      transition: opacity .2s, transform .1s;\n      display: flex; align-items: center; justify-content: center; gap: 8px;\n    }"
)

content = content.replace(
    ".lp-support-link {\n      display: flex; align-items: center; gap: 7px;\n      font-size: 12px; color: #6b7280; text-decoration: none; transition: color .2s;\n    }",
    ".lp-support-link {\n      display: flex; align-items: center; gap: 7px;\n      font-size: 12.5px; color: #6b7280; text-decoration: none; transition: color .2s;\n    }"
)

content = content.replace(
    ".lp-tagline { font-size: 26px; font-weight: 900; line-height: 1.2;",
    ".lp-tagline { font-size: 21px; font-weight: 900; line-height: 1.2;"
)

# Overrides
content = content.replace(
    "    @media (max-width: 600px) {\n      .lp-left { padding: 36px 24px; max-width: 100%; }\n      .lp-heading { font-size: 24px; }\n      .lp-sub { font-size: 12px; margin-bottom: 24px; }\n      .lp-brand { margin-bottom: 32px; }\n    }",
    "    @media (max-width: 600px) {\n      .lp-left { padding: 36px 24px; max-width: 100%; }\n      .lp-heading { font-size: 20px; }\n      .lp-sub { font-size: 12.5px; margin-bottom: 24px; }\n      .lp-brand { margin-bottom: 32px; }\n      .lp-brand-name { font-size: 13px; }\n      .lp-tagline { font-size: 15px; }\n    }"
)

content = content.replace(
    "    /* Small mobile (≤480px) */\n    @media (max-width: 480px) {\n      .lp-left { padding: 28px 16px; }\n      .lp-heading { font-size: 22px; }\n      .lp-tabs { margin-bottom: 20px; }\n      .lp-tab { padding: 8px 16px; font-size: 12px; }",
    "    /* Small mobile (≤480px) */\n    @media (max-width: 480px) {\n      .lp-left { padding: 28px 16px; }\n      .lp-heading { font-size: 20px; }\n      .lp-tabs { margin-bottom: 20px; }\n      .lp-tab { padding: 8px 16px; font-size: 9.5px; }"
)

content = content.replace(
    ".lp-heading { font-size: 36px; }",
    ".lp-heading { font-size: 20px; }"
)
content = content.replace(
    ".lp-sub { font-size: 15px; }",
    ".lp-sub { font-size: 12.5px; }"
)
content = content.replace(
    ".lp-input { font-size: 15px; padding: 14px 16px; }",
    ".lp-input { font-size: 13.5px; padding: 14px 16px; }"
)
content = content.replace(
    ".lp-btn { font-size: 15px; padding: 16px; }",
    ".lp-btn { font-size: 12px; padding: 16px; }"
)
content = content.replace(
    ".lp-brand-name { font-size: 22px; }",
    ".lp-brand-name { font-size: 26px; }"
)
content = content.replace(
    ".lp-tagline { font-size: 38px; max-width: 560px; }",
    ".lp-tagline { font-size: 21px; max-width: 560px; }"
)
content = content.replace(
    ".lp-tagline { font-size: 32px; max-width: 500px; }",
    ".lp-tagline { font-size: 21px; max-width: 500px; }"
)
content = content.replace(
    ".lp-tagline { font-size: 20px; max-width: 340px; }",
    ".lp-tagline { font-size: 21px; max-width: 340px; }"
)

with open(file_path, "w") as f:
    f.write(content)

print("Done")
