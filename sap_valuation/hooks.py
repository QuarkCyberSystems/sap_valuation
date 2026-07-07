app_name = "sap_valuation"
app_title = "SAP Inspired Valuation"
app_publisher = "Quark Cyber Systems"
app_description = "SAP-inspired Moving Average and Standard Cost valuation kernels for ERPNext"
app_email = "vivek@quarkcs.com"
app_license = "gpl-3.0"

required_apps = ["erpnext"]

# Valuation-method -> posting-kernel registry, consulted by the erpnext fork's
# routing dispatch before SLE creation. "SAP Standard Cost" registers here in
# Phase 3 without further core edits.
sap_valuation_kernels = {
	"SAP Moving Average": "sap_valuation.sap_moving_average.kernel.post_via_sap_ma_kernel",
}

# Incoming-rate resolver for kernel-valued items (consulted by the fork's
# erpnext.stock.utils.get_incoming_rate instead of SLE-based resolution).
sap_valuation_incoming_rate = "sap_valuation.shared.routing.get_incoming_rate"

# Landed Cost Voucher handler: stock-ratio split events instead of in-place
# SLE revaluation (consulted by the fork's update_landed_cost).
sap_valuation_landed_cost = "sap_valuation.sap_moving_average.landed_cost.handle_landed_cost"

after_migrate = ["sap_valuation.setup.custom_fields.after_migrate"]
after_install = ["sap_valuation.setup.custom_fields.apply_custom_fields"]

app_include_js = "/assets/sap_valuation/js/cancellation_button.js"

# Universal cancellation rule: docstatus 1 -> 2 is never allowed for documents
# containing SAP-valuation items; a dated Cancellation document is used instead.
_cancel_guard = {"before_cancel": "sap_valuation.overrides.cancel_guard.block_direct_cancel"}
doc_events = {
	"Purchase Receipt": _cancel_guard,
	"Delivery Note": _cancel_guard,
	"Stock Entry": _cancel_guard,
	"Purchase Invoice": {
		**_cancel_guard,
		"on_submit": "sap_valuation.sap_moving_average.invoice_diff.on_purchase_invoice_submit",
	},
	"Sales Invoice": _cancel_guard,
	"Subcontracting Receipt": _cancel_guard,
	"Landed Cost Voucher": _cancel_guard,
}

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "sap_valuation",
# 		"logo": "/assets/sap_valuation/logo.png",
# 		"title": "SAP Valuation",
# 		"route": "/sap_valuation",
# 		"has_permission": "sap_valuation.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/sap_valuation/css/sap_valuation.css"
# app_include_js = "/assets/sap_valuation/js/sap_valuation.js"

# include js, css files in header of web template
# web_include_css = "/assets/sap_valuation/css/sap_valuation.css"
# web_include_js = "/assets/sap_valuation/js/sap_valuation.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "sap_valuation/public/scss/website"

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
# app_include_icons = "sap_valuation/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "sap_valuation.utils.jinja_methods",
# 	"filters": "sap_valuation.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "sap_valuation.install.before_install"
# after_install = "sap_valuation.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "sap_valuation.uninstall.before_uninstall"
# after_uninstall = "sap_valuation.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "sap_valuation.utils.before_app_install"
# after_app_install = "sap_valuation.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "sap_valuation.utils.before_app_uninstall"
# after_app_uninstall = "sap_valuation.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "sap_valuation.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "sap_valuation.notifications.get_notification_config"

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
# 		"sap_valuation.tasks.all"
# 	],
# 	"daily": [
# 		"sap_valuation.tasks.daily"
# 	],
# 	"hourly": [
# 		"sap_valuation.tasks.hourly"
# 	],
# 	"weekly": [
# 		"sap_valuation.tasks.weekly"
# 	],
# 	"monthly": [
# 		"sap_valuation.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "sap_valuation.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "sap_valuation.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "sap_valuation.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "sap_valuation.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["sap_valuation.utils.before_request"]
# after_request = ["sap_valuation.utils.after_request"]

# Job Events
# ----------
# before_job = ["sap_valuation.utils.before_job"]
# after_job = ["sap_valuation.utils.after_job"]

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
# 	"sap_valuation.auth.validate"
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

