"""
Applicant portal web form: which application_status values are read-only on the website.
"""

import frappe

# Match post-submit outcomes on Applicant (Draft / Rejected stay editable).
PORTAL_LOCKED_APPLICATION_STATUSES = frozenset(
	{
		"Submitted",
		"Interview Excempted",
		"Entrance Test Exempted",
		"Excempted Entrance Test And Interview",
	}
)

_PATCHED = False


def applicant_portal_application_locked(application_status: str | None) -> bool:
	return (application_status or "").strip() in PORTAL_LOCKED_APPLICATION_STATUSES


def patch_web_form_get_context_once() -> None:
	"""Before WebForm.get_context auto-redirects /name → /name/edit, force read mode for locked applicants."""
	global _PATCHED
	if _PATCHED:
		return
	try:
		from frappe.website.doctype.web_form.web_form import WebForm
	except Exception:
		return

	_orig = WebForm.get_context

	def _wrapped(self, context):
		fd = frappe.form_dict
		try:
			if (
				getattr(self, "doc_type", None) == "Applicant"
				and (getattr(self, "route", None) or "") == "applicant-form"
				and fd.get("name")
				and not fd.get("is_edit")
				and not fd.get("is_read")
				and self.allow_edit
			):
				st = frappe.db.get_value("Applicant", fd.get("name"), "application_status")
				if applicant_portal_application_locked(st):
					fd["is_read"] = 1
		except Exception:
			pass
		return _orig(self, context)

	WebForm.get_context = _wrapped
	_PATCHED = True


def slcm_before_request() -> None:
	"""hooks.before_request — register Web Form patch early in the process."""
	try:
		patch_web_form_get_context_once()
	except Exception:
		pass
