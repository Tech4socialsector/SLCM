#!/usr/bin/env python3
"""
Setup script to create the Year Based Transcript Print Format in Frappe.
Run this: bench execute slcm.slcm.setup_transcript.setup_print_format
"""

import frappe
from frappe import _
import os

def setup_print_format():
    """Create the Year Based Transcript Print Format doctype entry."""

    # Read the HTML template file
    html_template_path = frappe.get_app_path("slcm", "slcm", "print_format", "year_based_transcript", "year_based_transcript.html")

    try:
        with open(html_template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"ERROR: HTML template file not found at {html_template_path}")
        return None

    # Check if Print Format already exists
    if frappe.db.exists("Print Format", "Year Based Transcript"):
        print("Print Format 'Year Based Transcript' already exists. Updating...")
        pf = frappe.get_doc("Print Format", "Year Based Transcript")
        pf.html = html_content
        pf.save()
        print("✓ Print Format 'Year Based Transcript' updated successfully!")
    else:
        # Create new Print Format
        pf = frappe.get_doc({
            "doctype": "Print Format",
            "name": "Year Based Transcript",
            "doc_type": "Student Transcript",
            "module": "SLCM",
            "standard": "Yes",
            "html": html_content,
            "print_format_type": "Jinja",
            "disabled": 0,
            "custom_format": 1,
            "default_print_language": "en",
            "print_format_builder": 0,
            "show_section_headings": 0,
            "line_breaks": 0,
            "absolute_value": 0,
            "align_labels_right": 0
        })
        pf.insert(ignore_permissions=True)
        print("✓ Print Format 'Year Based Transcript' created successfully!")

    frappe.db.commit()

    print("\n" + "="*60)
    print("SETUP COMPLETE!")
    print("="*60)
    print("\nThe Year Based Transcript print format has been set up.")
    print("\nNext steps:")
    print("1. Configure Transcript Settings (Settings > Transcript Settings)")
    print("2. Add Year Mappings (e.g., Semester 1,2 → I Year)")
    print("3. Go to any Student Transcript document")
    print("4. Click Print > Select 'Year Based Transcript' format")
    print("5. Download PDF\n")

    return pf
