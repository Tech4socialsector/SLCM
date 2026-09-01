// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["Admission Marketing Source Analysis"] = {
	"filters": [
		{
			"fieldname": "source_of_information",
			"label": __("Marketing Source"),
			"fieldtype": "Select",
			"options": "\nNLSIU Website\nNLSIU Students, Faculty or Alumni\nYoutube\nFacebook / Meta\nLinkedin\nX (Twitter)\nInstagram\nEmail\nNewspaper Advertisement\nOthers",
			"reqd": 0
		}
	]
};
