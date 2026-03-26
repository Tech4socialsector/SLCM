app_name = "slcm"
app_title = "SLCM"
app_publisher = "TFSS"
app_description = "Student Life Cycle Management"
app_email = "tech4socialsector@azimpremjifoundation.org"
app_license = "mit"

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
webform_include_js = {"Foundations for a Legal Education": "public/js/fle_theme.js"}

# Jinja
jinja = {
	"methods": [
		"slcm.admission.utils.jinja.get_file_b64"
	],
}

# Fixtures – exported to JSON and committed to git so every developer/server gets them
fixtures = [
    # --- Admission roles ---
    {
        "doctype": "Role",
        "filters": [
            ["name", "in", [
                "Eligibility Admin", "Entrance Test Admin", "Entrance Test Provider",
                "Applicant", "Interview Staff Member", "Merit Admin", "Scholarship Admin",
                # --- Student Registration workflow roles ---
                "REGO Officer", "FINO Officer", "Registration Officer",
                "Documentation Officer", "Residence / Hostel Admin", "IT Admin",
                "Registration User", "Student"
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
                "Eligibility Admin", "Entrance Test Admin", "Entrance Test Provider",
                "Applicant", "Interview Staff Member", "Interview Admin", "Campus Admin"
            ]]
        ]
    },
    # --- Master data ---
    {"doctype": "Applicant Status"},
    {"doctype": "Stages"},
    {"doctype": "Merit Component"},
    # --- Workspaces (public=1 only) – so sidebar shows for all users after bench migrate ---
    {
        "doctype": "Workspace",
        "filters": [["public", "=", 1], ["app", "=", "slcm"]]
    },
    # --- Student Registration Workflow ---
    {
        "doctype": "Workflow",
        "filters": [["name", "=", "Student Registration Workflow"]]
    },
    # --- Dashboard: Number Cards on Student Registration workspace ---
    {
        "doctype": "Number Card",
        "filters": [["name", "in", [
            "Total Students", "Active Enrollments", "Active Programs", "Active Courses"
        ]]]
    },
    # --- Dashboard: Charts on Student Registration workspace ---
    {
        "doctype": "Dashboard Chart",
        "filters": [["name", "in", [
            "Student Registration Status", "Student Enrollment by Program"
        ]]]
    },
    # --- Desktop Icons (app launcher tiles) ---
    {
        "doctype": "Desktop Icon",
        "filters": [["app", "=", "slcm"], ["standard", "=", 1]]
    },
    # --- Workspace Sidebars (left-panel navigation for each workspace) ---
    {
        "doctype": "Workspace Sidebar",
        "filters": [["app", "=", "slcm"]]
    },
    # --- Web Forms / Custom Fields / Property Setters ---
    "Web Form",
    "Custom Field",
    "Property Setter",
]

# Document Events
doc_events = {
    "Student Master": {
        "before_save": "slcm.slcm.doctype.student_master.student_master.before_save_hook"
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
    "Applicant": "slcm.permissions.applicant_query_conditions",
    "Entrance Test Provider": "slcm.permissions.entrance_test_provider_query_conditions",
    "Entrance Test Seat Allocation": "slcm.permissions.seat_allocation_query_conditions",
    "Interview Staff Member": "slcm.permissions.interview_staff_member_query_conditions",
    "Interview Seat Allocation": "slcm.permissions.interview_seat_allocation_query_conditions",
}

# Scheduled Tasks
scheduler_events = {
	"cron": {
		"*/10 * * * *": [
			"slcm.slcm.doctype.attendance_log.process_attendance_logs.process_pending_logs",
			"slcm.admission.doctype.waitlist_rule.waitlist_promotion.run_scheduled_waitlist"
		],
        "*/15 * * * *": [
            "slcm.admission.utils.scheduler.auto_manage_announcements"
        ]
	},
    "all": [],
	"hourly": [
		"slcm.admission.events.auto_update_cycle_status",
        "slcm.admission.utils.notifications.check_and_send_offer_reminders",
        "slcm.admission.utils.auto_draft.auto_save_all_drafts"
	],
	"daily": [
		"slcm.api.service.offer_service.expire_offers",
		"slcm.admission.doctype.waitlist_rule.waitlist_promotion.run_scheduled_waitlist",
		"slcm.admission.events.send_deadline_reminders",
		"slcm.admission.utils.stage_scheduler.auto_advance_applicant_stages"
	]
}

# Website
website_route_rules = [
    {"from_route": "/applicant-dashboard", "to_route": "applicant_dashboard"},
    {"from_route": "/admission/<name>", "to_route": "admission/program_detail"},
    {"from_route": "/announcement/<name>", "to_route": "announcement/announcement_detail"},
    {"from_route": "/admission-dashboard", "to_route": "merit-and-scholarship/admission_dashboard"},
    {"from_route": "/apply", "to_route": "merit-and-scholarship/apply"},
    {"from_route": "/application-form", "to_route": "application_form"}
]

update_website_context = "slcm.admission.utils.portal.update_website_context"

# Ignore links to specified DocTypes when deleting documents
ignore_links_on_delete = ["Communication", "ToDo", "Admission Cancellation", "Refund Request"]
