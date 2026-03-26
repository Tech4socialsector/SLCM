import frappe

def execute():
    wf = frappe.get_doc("Web Form", "foundations-for-a-legal-education")
    
    current_script = wf.client_script
    
    # We will just replace the exact block in the string.
    old_html = """<div class="brand-text">\\n\\t\\t\\t\\t<h5 class="university-name">National Law School of India University, Bengaluru</h5>\\n\\t\\t\\t\\t<h1 class="department-name">Foundations for a Legal Education Certificate Course</h1>\\n\\t\\t\\t</div>\\n\\t\\t\\t<div class="header-spacer"></div>\\n\\t\\t</div>"""
    
    new_html = """<div class="brand-text">\\n\\t\\t\\t\\t<h5 class="university-name">National Law School of India University, Bengaluru</h5>\\n\\t\\t\\t\\t<h1 class="department-name">Foundations for a Legal Education Certificate Course</h1>\\n\\t\\t\\t</div>\\n\\t\\t\\t<div class="header-logout-area">\\n\\t\\t\\t\\t<button class="fle-logout-btn" id="fle-logout-btn" type="button" onclick="window.location.href='/login.html'">\\n\\t\\t\\t\\t\\t<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">\\n\\t\\t\\t\\t\\t\\t<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>\\n\\t\\t\\t\\t\\t\\t<polyline points="16 17 21 12 16 7"></polyline>\\n\\t\\t\\t\\t\\t\\t<line x1="21" y1="12" x2="9" y2="12"></line>\\n\\t\\t\\t\\t\\t</svg>\\n\\t\\t\\t\\t\\tLogout\\n\\t\\t\\t\\t</button>\\n\\t\\t\\t</div>\\n\\t\\t</div>"""

    if old_html in current_script:
        wf.client_script = current_script.replace(old_html, new_html)
        wf.save(ignore_permissions=True)
        frappe.db.commit()
        print("Web Form updated successfully using Python replace.")
    else:
        print("Could not find the target string in client_script.")
        # Alternatively, let's just find <div class="header-spacer"></div> element and replace it
        if '<div class="header-spacer"></div>' in current_script:
            wf.client_script = current_script.replace('<div class="header-spacer"></div>', """<div class="header-logout-area">\\n\\t\\t\\t\\t<button class="fle-logout-btn" id="fle-logout-btn" type="button" onclick="window.location.href='/login.html'">\\n\\t\\t\\t\\t\\t<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">\\n\\t\\t\\t\\t\\t\\t<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>\\n\\t\\t\\t\\t\\t\\t<polyline points="16 17 21 12 16 7"></polyline>\\n\\t\\t\\t\\t\\t\\t<line x1="21" y1="12" x2="9" y2="12"></line>\\n\\t\\t\\t\\t\\t</svg>\\n\\t\\t\\t\\t\\tLogout\\n\\t\\t\\t\\t</button>\\n\\t\\t\\t</div>""")
            wf.save(ignore_permissions=True)
            frappe.db.commit()
            print("Web Form updated successfully using fallback replace.")
        else:
            print("Fallback also failed.")

