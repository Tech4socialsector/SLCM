import frappe
from frappe import _
from frappe.utils import getdate, today


def get_current_stage(admission_cycle):
	"""
	Returns the active stage row for today's date.
	Returns None if no stage is active for today.
	"""
	if not admission_cycle:
		return None

	cycle = frappe.get_doc("Admission Cycle", admission_cycle)
	current_date = getdate(today())

	for stage in sorted(cycle.stages, key=lambda x: x.sequence_no):
		if stage.start_date and stage.end_date:
			if getdate(stage.start_date) <= current_date <= getdate(stage.end_date):
				return stage

	return None


def get_active_stages_sequence(admission_cycle):
	"""
	Returns ordered list of stage names based on which stage flags
	are enabled on the cycle. Disabled stages are excluded.
	"""
	if not admission_cycle:
		return []

	cycle = frappe.get_doc("Admission Cycle", admission_cycle)

	# Map stage flag fields to stage names
	stage_flag_map = {
		"enable_entrance_test": "Entrance Exam",
		"enable_interview": "Interview",
		"enable_document_verification": "Document Verification",
		"enable_scholarship": "Scholarship",
		"enable_group_discussion": "Group Discussion",
	}

	# Always include core stages
	always_included = [
		"Application Open",
		"Application Closed",
		"Merit List Publication",
		"Counselling",
		"Seat Allotment",
		"Fee Payment",
		"Admission Confirmation",
		"Cycle Closed",
	]

	active_optional = [
		stage_name
		for flag, stage_name in stage_flag_map.items()
		if cycle.get(flag)
	]

	# Build sequence using actual stages in cycle
	result = []
	for stage in sorted(cycle.stages, key=lambda x: x.sequence_no):
		if stage.stage_name in always_included or stage.stage_name in active_optional:
			result.append(stage.stage_name)

	return result


def get_cycle_rule(admission_cycle, rule_type):
	"""
	Returns rule_value for a given rule_type on the cycle.
	Returns None if rule does not exist or is inactive.
	"""
	if not admission_cycle or not rule_type:
		return None

	cycle = frappe.get_doc("Admission Cycle", admission_cycle)

	for rule in (cycle.rules or []):
		if rule.rule_type == rule_type and rule.is_active:
			return rule.rule_value

	return None


def assert_stage_enabled_and_active(admission_cycle, stage_flag, stage_name):
	"""
	Throws if:
	- stage_flag is OFF on the cycle
	- OR cycle is not currently in that stage window
	"""
	if not admission_cycle:
		frappe.throw(_("Admission Cycle is required."))

	cycle = frappe.get_doc("Admission Cycle", admission_cycle)

	# Check if stage is enabled
	if not cycle.get(stage_flag):
		frappe.throw(
			_("Stage '{0}' is not enabled on Admission Cycle '{1}'.").format(stage_name, admission_cycle)
		)

	# Check if currently within stage window
	current_stage = get_current_stage(admission_cycle)
	if not current_stage or current_stage.stage_name != stage_name:
		frappe.throw(
			_("Admission Cycle '{0}' is not currently in the '{1}' stage.").format(admission_cycle, stage_name)
		)


def validate_cycle_deadline(action, admission_cycle, throw=True):
	"""
	Central utility to check if an action falls within the configured deadlines.
	Supported actions: 'Application', 'Interview', 'Offer', 'Payment'
	"""
	if not admission_cycle:
		return True

	cycle = frappe.get_doc("Admission Cycle", admission_cycle)
	current_date = getdate(today())
	
	deadlines = {
		"Application": ("start_date", "end_date", _("Application window")),
		"Interview": ("interview_start_date", "interview_end_date", _("Interview window")),
		"Offer": ("offer_start_date", "offer_end_date", _("Offer window")),
		"Payment": ("payment_start_date", "payment_end_date", _("Payment/Acceptance window")),
	}

	if action not in deadlines:
		return True

	start_f, end_f, label = deadlines[action]
	start_date = cycle.get(start_f)
	end_date = cycle.get(end_f)

	# Special check for Application Cutoff Rule
	if action == "Application":
		cutoff = get_cycle_rule(admission_cycle, "Submission Cutoff")
		if cutoff:
			end_date = cutoff

	if not start_date or not end_date:
		# Fallback to stage-based check if explicit fields are empty
		# We assume the 'label' maps roughly to stage names if needed
		# but for now, we just return True if no dates are configured
		return True

	if not (getdate(start_date) <= current_date <= getdate(end_date)):
		if throw:
			frappe.throw(
				_("The {0} for Admission Cycle '{1}' is currently closed. (Open from {2} to {3})")
				.format(label, admission_cycle, start_date, end_date)
			)
		return False

	return True
