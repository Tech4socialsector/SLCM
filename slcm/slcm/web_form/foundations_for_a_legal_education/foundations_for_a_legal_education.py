import frappe

def get_context(context):
	# Disable the default header and footer
	context.no_header = 1
	context.no_footer = 1
