"""
Applicant + PACE portal web forms.

Frappe only auto-loads ``<module>/<web_form>.js`` from the app when ``Web Form.is_standard``
is set. Standard forms cannot be edited in Desk. We keep these forms **non-standard**
(``is_standard = 0`` in JSON) so fields can be changed on live sites, and patch
``WebForm.add_custom_context_and_script`` so the portal still receives the same
``get_context``, bundled JS/CSS, and ``webform_include_*`` hooks as a standard form.

Applicant: ``get_context`` also forces read-only portal URLs when the application is
no longer in Draft.
"""

import os

import frappe
from frappe import scrub

_PATCHED = False
_ASSETS_PATCHED = False
_LINK_OPTIONS_PATCHED = False

# Portal web forms where Program link options must not be scoped to doc.owner
# (child-table ug_program / pg_program are converted to Autocomplete via process_link_field).
_APPLICANT_PORTAL_WEB_FORM_ROUTES = frozenset({"applicant-form"})


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


# (doc_type, route, dotted path to web_form module next to <scrub(name)>.js)
_SLCM_NON_STANDARD_WEB_FORM_MODULES: tuple[tuple[str, str, str], ...] = (
	("Applicant", "applicant-form", "slcm.admission.web_form.applicant_form.applicant_form"),
	(
		"PACE Application",
		"pace-application-form",
		"slcm.pace.web_form.pace_application_form.pace_application_form",
	),
)


def _slcm_inject_web_form_module_assets(web_form, context: dict, web_form_module_qualname: str) -> None:
	"""Append module get_context + JS/CSS + hook files (mirrors standard Web Form loading)."""
	try:
		from frappe.desk.form.meta import get_code_files_via_hooks
	except Exception:
		return

	try:
		web_form_module = frappe.get_module(web_form_module_qualname)
	except Exception:
		return

	get_ctx = getattr(web_form_module, "get_context", None)
	if callable(get_ctx):
		new_context = get_ctx(context)
		if new_context:
			context.update(new_context)

	mod_dir = os.path.dirname(web_form_module.__file__)
	js_path = os.path.join(mod_dir, scrub(web_form.name) + ".js")
	if os.path.isfile(js_path):
		with open(js_path, encoding="utf-8") as f:
			script = frappe.render_template(f.read(), context)
		for path in get_code_files_via_hooks(
			"webform_include_js", web_form.doc_type
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
		context["script"] = script

	css_path = os.path.join(mod_dir, scrub(web_form.name) + ".css")
	if os.path.isfile(css_path):
		with open(css_path, encoding="utf-8") as f:
			style = f.read()
		for path in get_code_files_via_hooks("webform_include_css", web_form.doc_type):
			try:
				with open(path, encoding="utf-8") as cf:
					style = "\n\n".join([style, cf.read()])
			except Exception:
				pass
		prev_st = context.get("style")
		if prev_st:
			style = str(prev_st) + "\n\n" + style
		context["style"] = style


def patch_applicant_web_form_module_assets_once() -> None:
	"""Load module JS/CSS for SLCM portal web forms when ``is_standard`` is unset (Desk-editable)."""
	global _ASSETS_PATCHED
	if _ASSETS_PATCHED:
		return
	try:
		from frappe.website.doctype.web_form.web_form import WebForm
	except Exception:
		return

	_orig = WebForm.add_custom_context_and_script

	def _wrapped(self, context):
		_orig(self, context)
		if getattr(self, "is_standard", None):
			return
		route = (getattr(self, "route", None) or "").strip()
		dt = getattr(self, "doc_type", None)
		for doc_type, r, module in _SLCM_NON_STANDARD_WEB_FORM_MODULES:
			if dt == doc_type and route == r:
				_slcm_inject_web_form_module_assets(self, context, module)
				break

	WebForm.add_custom_context_and_script = _wrapped
	_ASSETS_PATCHED = True


def patch_web_form_program_link_options_once() -> None:
	"""
	Frappe web forms with login_required filter link autocomplete by owner=session.user.
	Program rows are not owned by applicants, so ug_program/pg_program in child tables list
	nothing unless allow_read_on_all_link_options is set before get_link_options runs.
	"""
	global _LINK_OPTIONS_PATCHED
	if _LINK_OPTIONS_PATCHED:
		return
	try:
		from frappe.website.doctype.web_form import web_form as wf_mod
	except Exception:
		return

	_orig = wf_mod.process_link_field

	def _process_link_field(field, web_form_name):
		try:
			route = (frappe.db.get_value("Web Form", web_form_name, "route") or "").strip()
		except Exception:
			route = ""
		if route in _APPLICANT_PORTAL_WEB_FORM_ROUTES and field.get("options") == "Program":
			field["allow_read_on_all_link_options"] = 1
		return _orig(field, web_form_name)

	wf_mod.process_link_field = _process_link_field
	_LINK_OPTIONS_PATCHED = True


def slcm_before_request() -> None:
	"""hooks.before_request — register Web Form patch early in the process."""
	try:
		patch_web_form_get_context_once()
		patch_applicant_web_form_module_assets_once()
		patch_web_form_program_link_options_once()
	except Exception:
		pass

	# Route Guarding for Applicant and PACE Applicant
	try:
		if frappe.session.user != "Guest" and hasattr(frappe.local, "request") and frappe.local.request:
			path = frappe.local.request.path or ""
			if not (path.startswith("/api") or path.startswith("/assets") or path.startswith("/app")):
				normalized_path = path.strip("/").lower()
				roles = frappe.get_roles()
				is_applicant = "Applicant" in roles
				is_pace_applicant = "PACE Applicant" in roles

				# 1. Applicant cannot access PACE routes
				if is_applicant and not is_pace_applicant:
					if normalized_path.startswith("pace") or "pace-application" in normalized_path:
						frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

				# 2. PACE Applicant cannot access Admission routes
				elif is_pace_applicant and not is_applicant:
					if (
						normalized_path.startswith("admission")
						or "applicant-form" in normalized_path
						or normalized_path == "admission-dashboard"
					):
						frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	except frappe.PermissionError:
		raise
	except Exception:
		pass

