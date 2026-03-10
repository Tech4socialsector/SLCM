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
    Normalize and optionally validate a phone value for Frappe Phone field (E.164).

    - Returns None for empty, None, or country-code-only (e.g. "+91").
    - If phonenumbers is available: parses, validates, and returns E.164 formatted string.
    - If phonenumbers is not available or parse fails: falls back to stripping and
      ensuring + prefix and digits only; returns None if result is too short.

    Returns:
        str: E.164 string (e.g. "+919874563212"), or None if empty/invalid.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value).strip()
    else:
        value = value.strip()
    if not value:
        return None
    # Accept "country code - number" format (e.g. +91-7418656522); normalize to E.164 for Frappe
    value = value.replace("-", "").replace(" ", "").strip()
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) <= 4:
        return None
    try:
        from phonenumbers import NumberParseException, format_number, is_valid_number, parse
        from phonenumbers import PhoneNumberFormat

        parsed = parse(value, None)
        if not is_valid_number(parsed):
            return None
        return format_number(parsed, PhoneNumberFormat.E164)
    except (ImportError, NumberParseException, Exception):
        pass
    if not value.startswith("+"):
        value = "+" + value
    cleaned = "+" + "".join(c for c in value[1:] if c.isdigit())
    return cleaned if len(cleaned) > 5 else None


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
