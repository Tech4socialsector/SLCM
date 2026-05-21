import frappe
import os

no_cache = 1

@frappe.whitelist()
def get_wiki_content():
	wiki_path = os.path.join(os.path.dirname(__file__), '../../../../..', 'docs', 'SLCM_WIKI.md')
	wiki_path = os.path.abspath(wiki_path)
	if os.path.exists(wiki_path):
		with open(wiki_path, 'r') as f:
			return f.read()
	return None
