import requests, re

try:
    resp = requests.get('http://127.0.0.1:8005/admission', timeout=10)
    html = resp.text

    print("=== HTTP STATUS:", resp.status_code, "===")
    print("=== PAGE SIZE:", len(html), "bytes ===")
    print()

    # Check <style> blocks
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
    print("Number of <style> blocks in rendered HTML:", len(style_blocks))
    for i, s in enumerate(style_blocks):
        print(f"  style[{i}] first 80 chars: {repr(s.strip()[:80])}")

    print()
    # Check if .adm-nav appears OUTSIDE style tags (i.e. as raw text)
    body_match = re.search(r'<body[^>]*>(.*)', html, re.DOTALL)
    body_text = body_match.group(1) if body_match else ''
    raw_css_in_body = '.adm-nav' in body_text[:10000]
    print("CSS leaking as raw text in body:", raw_css_in_body)

    print()
    # Check if Jinja blocks are rendering as literal text (template not processed)
    print("Literal Jinja block in output:", '{%' in html or '{{' in html)
    if '{%' in html:
        idx = html.find('{%')
        print("  Context:", repr(html[max(0,idx-30):idx+60]))

    print()
    # Check if admission_base.html is even being used
    print("adm-nav class in HTML:", 'adm-nav' in html)
    print("adm-container in HTML:", 'adm-container' in html)

    print()
    # Show first 500 chars of <body>
    print("=== BODY START ===")
    print(body_text[:500])
except Exception as e:
    print("Error during request:", e)
