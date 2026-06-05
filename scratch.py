import frappe
from frappe.website.serve import handle_exception
import inspect

print(inspect.getsource(handle_exception))
