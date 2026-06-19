app_name = "slcm"
app_title = "SLCM"
page_js = {"dashboard-view": ["public/js/pace_dashboard_filters.js", "public/js/document_verifier_filters.js"]}


required_apps = ["payments"]

app_publisher = "TFSS"
app_description = "Student Life Cycle Management"
app_email = "tech4socialsector@azimpremjifoundation.org"
app_license = "mit"

after_install = "slcm.install.after_install"
after_migrate = "slcm.install.after_migrate"
# Apps
# ------------------

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
app_include_js = [
    "/assets/slcm/js/student_workspace_redirect.js",
    "/assets/slcm/js/file_uploader_globals.js",
]
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
		"slcm.admission.utils.portal.get_typography_style_block",
	],
}

# Fixtures – exported to JSON and committed to git so every developer/server gets them
fixtures = [
    {
        "doctype": "PACE University",
    },
    {
        "doctype": "City",
    },
    {
        "doctype": "State",
    },
    {
        "doctype":"Admission Category"
    },
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
                "slcm_parent",
                # Additional roles
                "PACE Admission Manager", "PACE Applicant"
            ]]
        ]
    },
    {
        "doctype": "Module Profile",
        "filters": [
            ["name", "in", ["Eligibility Admin", "Entrance Test Admin", "Entrance Test Provider", "PACE"]]
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
                "Applicant", "Interview Staff Member", "Interview Admin", "Campus Admin",
                "PACE Admission Manager"
            ]]
        ]
    },
    # --- Master data ---
    {"doctype": "Workflow State"},
    {"doctype": "Applicant Status"},
    {"doctype": "Stages"},

    {"doctype": "PACE Application Status"},
    # --- Email Templates ---
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
                "PACE Document Verification Rejected",
                "Pace Course Fee Payment Remainder",
                "Admission Offer Letter",
                "Pace Application Completed but Payment Pending"
            ]]
        ]
    },
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
            # Faculty
            "Faculty My Course Offerings", "Faculty My Student Groups",
            "Faculty Active Attendance Sessions", "Faculty Pending Condonation Requests",
            "Faculty Open Course Offerings", "Faculty Office Hours Groups",
            # Fees Management
            "Total Fee Demands", "Pending Fee Demands", "Overdue Fee Demands",
            "Fee Receipts This Month",
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
            # Faculty
            "Faculty Attendance Trend", "Faculty Course Offerings by Status",
            # Fees Management
            "Demand Status Distribution", "Demands by Fee Component",
            "Monthly Fee Collection",
        ]]]
    },
    # --- Kanban Board ---
    {
        "doctype": "Kanban Board",
        "filters": [
            ["name", "=", "Scholarship View"]
        ]
    },
    # --- Workspaces ---
    {
        "doctype": "Workspace",
        "filters": [["module", "in", ["SLCM", "Admission", "PACE"]]]
    },
    # --- Workspace Sidebars ---
    {
        "doctype": "Workspace Sidebar",
        "filters": [["name", "in", ["Faculty", "Fees Management", "Admission Fee"]]]
    },
    # --- Desktop Icons ---
    {
        "doctype": "Desktop Icon",
        "filters": [["name", "in", ["Faculty"]]]
    },
    # --- Web Forms / Custom Fields / Property Setters ---
    # NOTE: "Custom Field" with no filter exports ALL custom fields (including those
    # owned by other apps like helpdesk), causing `bench migrate` to fail with:
    # "A field with the name X already exists in Y" — because Frappe's delete-and-
    # reinsert sequence for fixture import doesn't always clear the meta cache before
    # validate() runs. Fix: exclude "HD Ticket Type" fields from here; they are owned
    # by the helpdesk app and exported via helpdesk/fixtures/custom_field.json instead.
    "Web Form",
    {
        "doctype": "Custom Field",
        "filters": [["dt", "not in", ["HD Ticket Type"]]]
    },
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
    "HD Ticket": {
        "before_validate": "slcm.api.helpdesk_assignment.auto_assign_team_by_student"
    },
    "User": {
        "before_insert": "slcm.api.user_events.user_before_insert",
        "after_insert": "slcm.api.user_events.send_signup_email"
    },
    "Hostel Allocation": {
        "after_insert": "slcm.slcm.fee.event_hooks.on_hostel_allocation_insert",
        "on_trash": "slcm.slcm.fee.event_hooks.on_hostel_allocation_trash"
    },
    "Hostel Fine": {
        "after_insert": "slcm.slcm.fee.event_hooks.on_hostel_fine_insert"
    },
    "Re Exam Registration": {
        "after_insert": "slcm.slcm.fee.event_hooks.on_reexam_registration_insert"
    },
    "Convocation Registration": {
        "on_submit": "slcm.slcm.fee.event_hooks.on_convocation_registration_submit",
        "on_cancel": "slcm.slcm.fee.event_hooks.on_convocation_registration_cancel"
    },
    "Merit List": {
        "on_submit": "slcm.admission.events.on_merit_list_publish"
    },
    "Campus Seat Matrix": {
        "on_submit": "slcm.admission.events.on_seat_matrix_lock"
    },
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

ignore_links_on_delete = ["Admission Audit Log", "Merit Audit Log", "Seat Allocation Audit Log", "Communication", "ToDo", "Admission Cancellation", "Refund Request", "Attendance Log"]

# Request Events
# ----------------
before_request = [
    "slcm.admission.portal_application_web_form.slcm_before_request",
    "slcm.utils.auth_routing.intercept_login"
]
on_logout = "slcm.utils.auth_routing.handle_logout"
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
		# Pull new RFID swipes from SQL Server into Attendance Log every 5 minutes
		"*/5 * * * *": [
			"slcm.slcm.utils.rfid_sql_poller.poll_rfid_swipes",
		],
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
		    "slcm.pace.doctype.pace_application.pace_application.send_payment_reminders",
		    "slcm.pace.doctype.pace_application.pace_application.send_document_reminders",
		    "slcm.pace.doctype.pace_application.pace_application.send_correction_reminders",
		    "slcm.pace.doctype.pace_applicant_fee_assignment.pace_applicant_fee_assignment.send_course_fee_reminders",
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
		"slcm.admission.doctype.important_dates.important_dates.update_important_dates_status",
		"slcm.admission.doctype.waitlist_rule.waitlist_promotion.run_scheduled_waitlist",
		"slcm.admission.doctype.waitlist_rule.waitlist_promotion.expire_waitlists_past_cutoff",
		"slcm.admission.events.send_deadline_reminders",
		"slcm.admission.utils.stage_scheduler.auto_advance_applicant_stages",
		"slcm.slcm.doctype.student_master.student_master.auto_sync_all_student_fee_structures",
		"slcm.pace.doctype.pace_admission.pace_admission.auto_close_outdated_admissions",
		# Fee Management — daily automation
		"slcm.slcm.fee.scheduler.mark_overdue_demands",
		"slcm.slcm.fee.scheduler.send_due_reminders",
		"slcm.slcm.fee.scheduler.check_phd_year_transition"
	]
}

# Role-based home page — portal users must not land on /desk (no desk_access)
role_home_page = {
    "slcm_Faculty": "/faculty-portal",
    "slcm_parent": "/parent-portal",
}

# Website
website_route_rules = [
    {"from_route": "/admission/login", "to_route": "admission/login"},
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
    {"from_route": "/student-portal/venue-booking", "to_route": "student-portal/venue-booking"},
    # Parent Portal
    {"from_route": "/parent-portal", "to_route": "parent-portal/index"},
    {"from_route": "/parent-portal/attendance", "to_route": "parent-portal/attendance"},
    {"from_route": "/parent-portal/fees", "to_route": "parent-portal/fees"},
    {"from_route": "/parent-portal/results", "to_route": "parent-portal/results"},
    # Faculty Portal
    {"from_route": "/faculty-portal", "to_route": "faculty-portal/index"},
    {"from_route": "/faculty-portal/my-classes", "to_route": "faculty-portal/my-classes"},
    {"from_route": "/faculty-portal/attendance", "to_route": "faculty-portal/attendance"},
    {"from_route": "/faculty-portal/marks", "to_route": "faculty-portal/marks"},
    {"from_route": "/faculty-portal/communication", "to_route": "faculty-portal/communication"},
    {"from_route": "/faculty-portal/profile", "to_route": "faculty-portal/profile"},
    {"from_route": "/faculty-portal/venue-booking", "to_route": "faculty-portal/venue-booking"},
    {"from_route": "/pace/admission", "to_route": "pace/index"},
    {"from_route": "/pace/admission/<name>", "to_route": "pace/pace_programme_details"},
    {"from_route": "/pace/progress-tracker", "to_route": "pace_progress_tracker"},
    {"from_route": "/pace/login", "to_route": "pace/login"},
    {"from_route": "/pace/forgot_password", "to_route": "pace/forgot_password"},
    {"from_route": "/paceadmissions/forgot_password", "to_route": "paceadmissions/forgot_password"},
]

update_website_context = "slcm.admission.utils.portal.update_website_context"
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

    # Student Master - role-based row-level filtering (faculty sees only their assigned students)
    "Student Master": "slcm.permissions.student_master_query_conditions",

    # Class Schedule - faculty sees only their assigned groups' schedules
    "Class Schedule":                  "slcm.permissions.class_schedule_query_conditions",

    # Attendance - faculty sees only records for their assigned student groups
    "Attendance Session":              "slcm.permissions.attendance_session_query_conditions",
    "Student Attendance":              "slcm.permissions.student_attendance_query_conditions",
    "Attendance Log":                  "slcm.permissions.attendance_log_query_conditions",
    "Attendance Summary":              "slcm.permissions.attendance_summary_query_conditions",
    "Student Attendance Condonation":  "slcm.permissions.attendance_condonation_query_conditions",
    "FA MFA Application":              "slcm.permissions.fa_mfa_application_query_conditions",

    # Venue Booking – Faculty/Staff/Student see only their own bookings; Admin/Registrar see all
    "Venue Booking": "slcm.permissions.venue_booking_query_conditions",
}

has_permission = {
    "PACE Document Verification": "slcm.pace.doctype.pace_document_verification.pace_document_verification.has_permission",
}
