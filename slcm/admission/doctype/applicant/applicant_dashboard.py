def get_data():
	return {
		"fieldname": "applicant",
		"non_standard_fieldnames": {
			"Eligibility Result": "applicant_id"
		},
		"transactions": [
			{
				"label": "Communications",
				"fieldname": "applicant",
				"items": ["Applicant Communication Log"]
			},
			{
				"label": "Admission",
				"items": ["Admission Application", "Eligibility Result", "Offer Letter"]
			}
		]
	}
