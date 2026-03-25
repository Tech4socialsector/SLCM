# Copyright (c) 2025, SLCM and contributors
# License: MIT. See LICENSE
"""
Phone number sanitization and validation for Frappe Phone fields.

Frappe Phone fieldtype (fieldtype "Phone"):
- Expects E.164 format: "+" + country code + national number, no spaces.
  Example: +919874563212 (India), +14155552671 (US).
- Validation runs on save via frappe.utils.validate_phone_number_with_country_code(),
  which uses the phonenumbers library (parse + is_valid_number).

API / JSON:
- In request body JSON, the "+" character does NOT need encoding. Send as:
  "mobile_number": "+919874563212"
- In URL query strings, "+" should be encoded as %2B to avoid being read as space.

Optional / empty:
- Do not send country-code-only (e.g. "+91") or Frappe will raise "Phone Number ... is not valid."
- Send null/omit the key or sanitize to None for empty optional phone fields.
"""

from __future__ import unicode_literals

import frappe


def sanitize_phone_for_frappe(value):
    """
    Normalize a phone value to "+country_code-number" format.
    Example: +91-6382101474
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value).strip()
    else:
        value = value.strip()
    if not value:
        return None

    # If already in +cc-num format, just clean up spaces and return
    if "-" in value:
        parts = value.split("-", 1)
        cc = parts[0].strip()
        num = parts[1].strip().replace(" ", "")
        if not cc.startswith("+"):
            cc = "+" + cc
        num = "".join(c for c in num if c.isdigit())
        if num:
            return f"{cc}-{num}"

    # No hyphen provided; try to parse and inject one
    if not value.startswith("+"):
        value = "+" + value

    try:
        from phonenumbers import NumberParseException, is_valid_number, parse
        parsed = parse(value, None)
        if is_valid_number(parsed):
            cc = str(parsed.country_code)
            num = str(parsed.national_number)
            return f"+{cc}-{num}"
    except (ImportError, NumberParseException, Exception):
        pass

    # Fallback: just digits and + prefix if parsing fails
    cleaned = "+" + "".join(c for c in value[1:] if c.isdigit())
    if len(cleaned) <= 5:
        return None
    
    # Try to guess a split if it starts with +91 (common case)
    if cleaned.startswith("+91") and len(cleaned) > 10:
        return f"+91-{cleaned[3:]}"
        
    return cleaned


def validate_phone_with_frappe(phone_number, fieldname):
    """
    Validate using Frappe's validate_phone_number_with_country_code and return True.
    Raises frappe.ValidationError (Invalid Phone Number) if invalid.

    Use this when you want to explicitly validate before setting a field, or when
    you need a clear exception message for the API client.
    """
    from frappe.utils import validate_phone_number_with_country_code

    validate_phone_number_with_country_code(phone_number, fieldname)
    return True
