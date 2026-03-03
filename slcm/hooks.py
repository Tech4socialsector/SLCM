app_name = "slcm"
app_title = "SLCM"

app_publisher = "Nishanth"
app_description = "Student Life Cycle Management"
app_email = "nishanth.a@azimpremjifoundation.org"
app_license = "mit"

app_include_js = ["/assets/slcm/js/student_workspace_redirect.js"]


doc_events = {
	"Student Master": {"before_save": "slcm.slcm.doctype.student_master.attach_file.set_document_links"}
}



app_publisher = "TFSS"
app_description = "Student Life Cycle Management"
app_email = "tech4socialsector@azimpremjifoundation.org"
app_license = "mit"

fixtures = [
    {
        "doctype": "Role",
        "filters": [
            ["name", "in", ["Eligibility Admin", "Entrance Test Admin","Entrance Test Provider","Applicant"]]
        ]
    },
    {
        "doctype": "Module Profile",
        "filters": [
            ["name", "in", ["Eligibility Admin", "Entrance Test Admin","Entrance Test Provider"]]
        ]
    },
    {
        "doctype": "Role Profile",
        "filters": [
            ["name", "in", ["Eligibility Admin", "Entrance Test Admin","Entrance Test Provider","Applicant"]]
        ]
    }
]
# Apps  
# ------------------

# required_apps = []

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
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/slcm/css/slcm.css"
# app_include_js = "/assets/slcm/js/slcm.js"

# include js, css files in header of web template
# web_include_css = "/assets/slcm/css/slcm.css"
# web_include_js = "/assets/slcm/js/slcm.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "slcm/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "slcm/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "slcm.utils.jinja_methods",
# 	"filters": "slcm.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "slcm.install.before_install"
# after_install = "slcm.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "slcm.uninstall.before_uninstall"
# after_uninstall = "slcm.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "slcm.utils.before_app_install"
# after_app_install = "slcm.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "slcm.utils.before_app_uninstall"
# after_app_uninstall = "slcm.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "slcm.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

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
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "slcm.event.get_events"
# }
#
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

ignore_links_on_delete = ["Admission Audit Log", "Merit Audit Log", "Seat Allocation Audit Log", "Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["slcm.utils.before_request"]
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
		"*/10 * * * *": [  # Every 10 minutes
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
		"slcm.admission.events.send_deadline_reminders"
	]
}

website_route_rules = [
    {"from_route": "/applicant-dashboard", "to_route": "applicant_dashboard"}
]

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
}