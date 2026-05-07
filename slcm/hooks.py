app_name = "slcm"
app_title = "SLCM"
page_js = {"dashboard-view": ["public/js/pace_dashboard_filters.js", "public/js/document_verifier_filters.js"]}


doc_events = {
	"Student Master": {"before_save": "slcm.slcm.doctype.student_master.attach_file.set_document_links"}
}

required_apps = ["payments"]

app_publisher = "TFSS"
app_description = "Student Life Cycle Management"
app_email = "tech4socialsector@azimpremjifoundation.org"
app_license = "mit"

fixtures = [
    {
        "doctype": "PACE University",
        "doctype": "City",
        "doctype": "State",
        "doctype":"Email Templates"
    },
    {
        "doctype": "Role",
        "filters": [
            ["name", "in", ["Eligibility Admin", "Entrance Test Admin","Entrance Test Provider","Applicant","Interview Staff Member","Merit Admin","Scholarship Admin","PACE Admission Manager", "PACE Applicant"]]
        ]
    },
    {
        "doctype": "Module Profile",
        "filters": [
            ["name", "in", ["Eligibility Admin", "Entrance Test Admin","Entrance Test Provider","PACE"]]
        ]
    },
    {
        "doctype": "Role Profile",
        "filters": [
            ["name", "in", ["Eligibility Admin", "Entrance Test Admin","Entrance Test Provider","Applicant","Interview Staff Member","Interview Admin","Campus Admin","PACE Admission Manager"]]
        ]
    },
    {
        "doctype": "Workflow State",
    },
    {
        "doctype": "Applicant Status",
    },
    {
        "doctype": "Stages",
    },
    {
        "doctype": "Merit Component",
    },
    {
        "doctype": "Email Template",
        "filters": [
            ["name", "in", [
                "Scholarship Updates",
                "Merit List Template",
                "Seat Allocation Result Notification",
                "Eligibility Result",
                "Interview Result",
                "Interview Reschedule",
                "Interview Allocation",
                "Entrance Test Result",
                "Entrance Test Reschedule",
                "Entrance Test Allocation",
                "Application Submitted Email",
                "PACE Application Submitted",
                "PACE Document Verification Final Update",
                "PACE Payment Confirmation",
                "PACE Verifier Assignment",
                "PACE Document Re-uploaded for Verification",
                "PACE Student Enrollment Confirmation",
                "Docuement Remainder Email",
                "PACE Application Rejected - Missing Documents",
                "PACE Pending Verification Reminder",
                "PACE Final Verification Due Expired",
                "Interviewer Allocation",
                "Automated Entrance Test Allocation"
            ]]
        ]
    },
    {
        "doctype": "Kanban Board",
        "filters": [
            ["name", "=", "Scholarship View"]
        ]
    },
    {
        "doctype": "PACE Application Status",
    },
]

after_install = "slcm.install.after_install"
# Apps  
# ------------------

app_include_js = ["/assets/slcm/js/student_workspace_redirect.js"]

required_apps = ["payments"]

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "slcm",
		"logo": "/assets/slcm/logo.png",
		"title": "SLCM",
		"route": "/slcm"
	}
]

# Includes in <head>
web_include_js = ["/assets/slcm/js/fle_theme.js"]
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/slcm/css/slcm.css"
# app_include_js = "/assets/slcm/js/slcm.js"
app_include_js = ["/assets/slcm/js/file_uploader_globals.js"]
app_include_css = ["/assets/slcm/css/file_uploader_globals.css"]

# include js, css files in header of web template
# web_include_css = "/assets/slcm/css/slcm.css"
web_include_js = ["/assets/slcm/js/fle_theme.js", "/assets/slcm/js/file_uploader_globals.js"]
web_include_css = ["/assets/slcm/css/file_uploader_globals.css"]

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "slcm/public/scss/website"

# include js, css files in header of web form
webform_include_js = {"Foundations for a Legal Education": "public/js/fle_theme.js"}

# Jinja
jinja = {
	"methods": [
		"slcm.admission.utils.jinja.get_file_b64",
		"slcm.slcm.doctype.student_transcript.student_transcript.get_transcript_context",
		"slcm.slcm.doctype.student_transcript.student_transcript.get_year_based_transcript_context",
		"slcm.slcm.doctype.student_portal_settings.student_portal_settings.get_student_portal_settings",
		"slcm.slcm.doctype.parent_portal_settings.parent_portal_settings.get_parent_portal_settings",
		"slcm.admission.utils.portal.get_portal_website_branding",
	],
}

# Fixtures – exported to JSON and committed to git so every developer/server gets them
fixtures = [
    # --- SLCM module roles (slcm_ prefix) ---
    {
        "doctype": "Role",
        "filters": [
            ["name", "in", [
                # SLCM student-lifecycle roles
                "slcm_Student", "slcm_Faculty", "slcm_Registrar",
                "slcm_Programme Chair", "slcm_Hostel Warden", "slcm_Hostel Admin",
                "slcm_Placement Officer",
                # Student Registration workflow roles
                "slcm_REGO Officer", "slcm_FINO Officer", "slcm_Registration Officer",
                "slcm_Documentation Officer", "slcm_IT Admin", "slcm_Registration User",
                # Admission module roles (unchanged)
                "Eligibility Admin", "Entrance Test Admin", "Entrance Test Provider",
                "Applicant", "Interview Staff Member", "Merit Admin", "Scholarship Admin",
                # --- Parent Portal ---
                "slcm_parent"
            ]]
        ]
    },
    {
        "doctype": "Module Profile",
        "filters": [
            ["name", "in", ["Eligibility Admin", "Entrance Test Admin", "Entrance Test Provider"]]
        ]
    },
    {
        "doctype": "Role Profile",
        "filters": [
            ["name", "in", [
                # SLCM student-lifecycle profiles
                "slcm_Student", "slcm_Faculty", "slcm_Registrar",
                "slcm_Programme Chair", "slcm_Hostel Warden", "slcm_Hostel Admin",
                "slcm_Placement Officer", "slcm_Registration Team",
                "slcm_REGO Officer", "slcm_FINO Officer", "slcm_Registration Officer",
                "slcm_Documentation Officer", "slcm_IT Admin", "slcm_Registration User",
                # Admission module profiles (unchanged)
                "Eligibility Admin", "Entrance Test Admin", "Entrance Test Provider",
                "Applicant", "Interview Staff Member", "Interview Admin", "Campus Admin"
            ]]
        ]
    },
    # --- Master data ---
    {"doctype": "Applicant Status"},
    {"doctype": "Stages"},
    {"doctype": "Merit Component"},
    # --- Student Portal Settings (single doctype — ships with defaults) ---
    {
        "doctype": "Student Portal Settings",
        "filters": [["name", "=", "Student Portal Settings"]]
    },
    # --- Student Registration Workflow ---
    {
        "doctype": "Workflow",
        "filters": [["name", "=", "Student Registration Workflow"]]
    },
    # --- Dashboard: Number Cards ---
    {
        "doctype": "Number Card",
        "filters": [["name", "in", [
            # Programme Management / Registration
            "Total Students", "Active Enrollments", "Active Programs", "Active Courses",
            "Active Cohorts", "Open Course Offerings",
            "Draft", "Selected", "Pending REGO", "Pending FINO", "Pending Registration",
            "Pending Print & Scan", "Pending Residences", "Pending IT",
            "Final Verification REGO", "Completed", "Re-Open",
            # IT Team (ID Card)
            "Active Students", "Total ID Cards", "Active ID Cards",
            "Pending (Draft) Cards", "Cancelled Cards", "Print Log Entries",
            # Attendance
            "Total Attendance Records", "Present Count", "Absent Count", "OD Count",
            "Total Sessions", "Active Sessions", "Pending Condonations", "Pending FA / MFA",
        ]]]
    },
    # --- Dashboard: Charts ---
    {
        "doctype": "Dashboard Chart",
        "filters": [["name", "in", [
            # Programme Management / Registration
            "Student Registration Status", "Student Enrollment by Program",
            "Cohort Status Distribution", "Course Offerings by Status",
            # IT Team (ID Card)
            "ID Card Status Distribution", "ID Cards Generated Over Time",
            # Attendance
            "Attendance Status Distribution", "Attendance Trend Over Time",
            "Session Type Breakdown", "FA MFA Application Status",
        ]]]
    },
    # Workspaces, Desktop Icons, and Workspace Sidebars are loaded by Frappe's
    # model sync (import_file_by_path with force=False), which respects the DB
    # modified timestamp.  This means cloud-side UI edits are preserved on
    # re-deploy unless we explicitly bump the file's modified timestamp.
    # They are therefore intentionally excluded from fixtures (which use
    # force=True and would wipe cloud customisations on every bench migrate).
    # --- Web Forms / Custom Fields / Property Setters ---
    "Web Form",
    "Custom Field",
    "Property Setter",
    # --- Transcript Print Format ---
    {
        "doctype": "Print Format",
        "filters": [["name", "=", "Student Transcript"]]
    },
]

# Document Events
doc_events = {
    "Student Master": {
        "before_save": "slcm.slcm.doctype.student_master.student_master.before_save_hook"
    },
    "Fee Structure": {
        "on_update": "slcm.slcm.doctype.student_master.student_master.on_fee_structure_update"
    },
    "Payment Request": {
        "before_save": "slcm.admission.notification.utils.set_payment_request_receiver"
    },
    "Foundations for a Legal Education": {
        "before_save": "slcm.lms_automation.handle_payment_paid"
    },
    "Applicant": {
        "on_update": "slcm.admission.api.profile.sync_applicant_to_user",
        "on_submit": "slcm.admission.events.on_applicant_submit",
        "on_cancel": "slcm.admission.events.on_applicant_cancel"
    },
    "Applicant Document": {
        "on_submit": "slcm.admission.events.on_document_submit"
    },
    "Merit List": {
        "on_submit": "slcm.admission.events.on_merit_list_publish"
    },
    "Campus Seat Matrix": {
        "on_submit": "slcm.admission.events.on_seat_matrix_lock"
    }
}

# Permission query conditions
permission_query_conditions = {
    # SLCM student-lifecycle
    "Student Master": "slcm.permissions.student_master_query_conditions",
    # Admission module
    "Applicant": "slcm.permissions.applicant_query_conditions",
    "Entrance Test Provider": "slcm.permissions.entrance_test_provider_query_conditions",
    "Entrance Test Seat Allocation": "slcm.permissions.seat_allocation_query_conditions",
    "Interview Staff Member": "slcm.permissions.interview_staff_member_query_conditions",
    "Interview Seat Allocation": "slcm.permissions.interview_seat_allocation_query_conditions",
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"slcm.tasks.all"
# 	],
# 	"daily": [
# 		"slcm.tasks.daily"
# 	],
# 	"hourly": [
# 		"slcm.tasks.hourly"
# 	],
# 	"weekly": [
# 		"slcm.tasks.weekly"
# 	],
# 	"monthly": [
# 		"slcm.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "slcm.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.core.doctype.user.user.update_password": "slcm.api.user.custom_update_password"
}

# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "slcm.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

ignore_links_on_delete = ["Admission Audit Log", "Merit Audit Log", "Seat Allocation Audit Log", "Communication", "ToDo", "Admission Cancellation", "Refund Request"]

# Request Events
# ----------------
before_request = ["slcm.admission.portal_application_web_form.slcm_before_request"]
# after_request = ["slcm.utils.after_request"]

# Job Events
# ----------
# before_job = ["slcm.utils.before_job"]
# after_job = ["slcm.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"slcm.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []



# RFID Attendance Processing
scheduler_events = {
	"cron": {
		"*/10 * * * *": [
			"slcm.slcm.doctype.attendance_log.process_attendance_logs.process_pending_logs",
			"slcm.admission.doctype.waitlist_rule.waitlist_promotion.run_scheduled_waitlist"
		],
        "*/15 * * * *": [
            "slcm.admission.utils.scheduler.auto_manage_announcements"
        ],
		# Once per day: expire Issued/Accepted offers past payment_deadline (updates Offer + Applicant via OfferLetter hooks)
		"15 2 * * *": [
			"slcm.api.service.offer_service.expire_offers",
		],
		"0 10 * * *": [
		    "slcm.pace.doctype.pace_application.pace_application.send_document_reminders",
		    "slcm.pace.doctype.pace_application.pace_application.send_correction_reminders",
		    "slcm.pace.assignment_logic.check_overdue_verifications"
		],
		"daily": [
		]
		},
    "all": [],
	"hourly": [
		"slcm.admission.events.auto_update_cycle_status",
        "slcm.admission.utils.notifications.check_and_send_offer_reminders",
        # "slcm.admission.utils.auto_draft.auto_save_all_drafts"
	],
	"daily": [
		"slcm.admission.doctype.waitlist_rule.waitlist_promotion.run_scheduled_waitlist",
		"slcm.admission.doctype.waitlist_rule.waitlist_promotion.expire_waitlists_past_cutoff",
		"slcm.admission.events.send_deadline_reminders",
		"slcm.admission.utils.stage_scheduler.auto_advance_applicant_stages",
		"slcm.slcm.doctype.student_master.student_master.auto_sync_all_student_fee_structures",
		"slcm.pace.doctype.pace_admission.pace_admission.auto_close_outdated_admissions"
	]
}

# Website
website_route_rules = [
    {"from_route": "/applicant-dashboard", "to_route": "applicant_dashboard"},
    {"from_route": "/admission/<name>", "to_route": "admission/program_detail"},
    {"from_route": "/announcement/<name>", "to_route": "announcement/announcement_detail"},
    {"from_route": "/admission-dashboard", "to_route": "merit-and-scholarship/admission_dashboard"},
    {"from_route": "/apply", "to_route": "merit-and-scholarship/apply"},
    {"from_route": "/application-form", "to_route": "application_form"},
    # Student Portal
    {"from_route": "/student-portal", "to_route": "student-portal/index"},
    {"from_route": "/student-portal/courses", "to_route": "student-portal/courses"},
    {"from_route": "/student-portal/attendance", "to_route": "student-portal/attendance"},
    {"from_route": "/student-portal/fees", "to_route": "student-portal/fees"},
    {"from_route": "/student-portal/profile", "to_route": "student-portal/profile"},
    {"from_route": "/student-portal/support", "to_route": "student-portal/support"},
    {"from_route": "/student-portal/results", "to_route": "student-portal/results"},
    {"from_route": "/pace/admission", "to_route": "pace/index"},
    {"from_route": "/pace/admission/<name>", "to_route": "pace/pace_programme_details"},
    {"from_route": "/pace/progress-tracker", "to_route": "pace_progress_tracker"},
    {"from_route": "/pace/login", "to_route": "pace/login"},
    {"from_route": "/pace/forgot_password", "to_route": "pace/forgot_password"},
    {"from_route": "/pace/update_password", "to_route": "pace/update_password"}
]

update_website_context = "slcm.admission.utils.portal.update_website_context"

# Ignore links to specified DocTypes when deleting documents
ignore_links_on_delete = ["Communication", "ToDo", "Admission Cancellation", "Refund Request"]
doc_events = {
    "Student Master": {
        "before_save": "slcm.slcm.doctype.student_master.attach_file.set_document_links"
    },
    "Payment Request": {
        "before_save": "slcm.admission.notification.utils.set_payment_request_receiver"
    },
    "Applicant": {
        "on_submit": "slcm.admission.events.on_applicant_submit",
        "on_cancel": "slcm.admission.events.on_applicant_cancel"
    },
    "Applicant Document": {
        "on_submit": "slcm.admission.events.on_document_submit"
    },
    "Merit List": {
        "on_submit": "slcm.admission.events.on_merit_list_publish"
    },
    "Campus Seat Matrix": {
        "on_submit": "slcm.admission.events.on_seat_matrix_lock"
    },
    "User": {
        "before_insert": "slcm.api.user_events.user_before_insert",
        "after_insert": "slcm.api.user_events.send_signup_email"
    }
}
# permission_query_conditions = {
#     "Applicant": "slcm.permissions.applicant_query_conditions",
#     "Entrance Test Seat Allocation": "slcm.permissions.seat_allocation_query_conditions",
# }
permission_query_conditions = {

    # Applicant - see only their own Applicant document
    "Applicant": "slcm.permissions.applicant_query_conditions",

    # Entrance Test Provider - see only their own Provider record
    "Entrance Test Provider": "slcm.permissions.entrance_test_provider_query_conditions",

    # Seat Allocation - filtered based on role
    "Entrance Test Seat Allocation": "slcm.permissions.seat_allocation_query_conditions",

    # New
    "Interview Staff Member": "slcm.permissions.interview_staff_member_query_conditions",
    "Interview Seat Allocation": "slcm.permissions.interview_seat_allocation_query_conditions", 
    "PACE Document Verification": "slcm.pace.doctype.pace_document_verification.pace_document_verification.get_permission_query_conditions",
}

has_permission = {
    "PACE Document Verification": "slcm.pace.doctype.pace_document_verification.pace_document_verification.has_permission",
}
