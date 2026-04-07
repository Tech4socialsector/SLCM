"""
Applicant portal web form: portal editing is allowed only while application_status is Draft.

Non-standard Web Forms skip Frappe's add_custom_context_and_script (no file-based JS/CSS).
We patch that method so route applicant-form / DocType Applicant always loads the same
module as a standard form: applicant_form.get_context + applicant_form.js (+ hooks).
"""

import os

import frappe
from frappe import scrub

_PATCHED = False
_ASSETS_PATCHED = False


def applicant_portal_application_locked(application_status: str | None) -> bool:
	"""True when the portal must not allow edits (any settled status, including Withdrawn)."""
	s = (application_status or "").strip()
	if not s:
		return False
	return s.casefold() != "draft"


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


def patch_applicant_web_form_module_assets_once() -> None:
	"""Load admission/web_form/applicant_form assets when the Web Form is non-standard."""
	global _ASSETS_PATCHED
	if _ASSETS_PATCHED:
		return
	try:
		from frappe.desk.form.meta import get_code_files_via_hooks
		from frappe.website.doctype.web_form.web_form import WebForm
	except Exception:
		return

	_orig = WebForm.add_custom_context_and_script

	def _wrapped(self, context):
		_orig(self, context)
		if getattr(self, "doc_type", None) != "Applicant":
			return
		if (getattr(self, "route", None) or "") != "applicant-form":
			return
		if self.is_standard:
			return

		try:
			web_form_module = frappe.get_module(
				"slcm.admission.web_form.applicant_form.applicant_form"
			)
		except Exception:
			return

		new_context = web_form_module.get_context(context)
		if new_context:
			context.update(new_context)

		mod_dir = os.path.dirname(web_form_module.__file__)
		js_path = os.path.join(mod_dir, scrub(self.name) + ".js")
		if os.path.isfile(js_path):
			with open(js_path, encoding="utf-8") as f:
				script = frappe.render_template(f.read(), context)
			for path in get_code_files_via_hooks(
				"webform_include_js", self.doc_type
			) + get_code_files_via_hooks("webform_include_js", "*"):
				try:
					with open(path, encoding="utf-8") as cf:
						custom_js = frappe.render_template(cf.read(), context)
					script = "\n\n".join([script, custom_js])
				except Exception:
					pass
			prev = context.get("script")
			if prev:
				script = str(prev) + "\n\n" + script
			context.script = script

		css_path = os.path.join(mod_dir, scrub(self.name) + ".css")
		if os.path.isfile(css_path):
			with open(css_path, encoding="utf-8") as f:
				style = f.read()
			for path in get_code_files_via_hooks("webform_include_css", self.doc_type):
				try:
					with open(path, encoding="utf-8") as cf:
						style = "\n\n".join([style, cf.read()])
				except Exception:
					pass
			prev_st = context.get("style")
			if prev_st:
				style = str(prev_st) + "\n\n" + style
			context.style = style

	WebForm.add_custom_context_and_script = _wrapped
	_ASSETS_PATCHED = True


def slcm_before_request() -> None:
	"""hooks.before_request — register Web Form patch early in the process."""
	try:
		patch_web_form_get_context_once()
		patch_applicant_web_form_module_assets_once()
	except Exception:
		pass
