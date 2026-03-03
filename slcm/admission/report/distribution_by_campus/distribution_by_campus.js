// Copyright(c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["Distribution by Campus"] = {
	"filters": [
		{
			"fieldname": "admission_year",
			"label": __("Admission Year"),
			"fieldtype": "Link",
			"options": "Admission Year",
			"default": ""
		},
		{
			"fieldname": "admission_cycle",
			"label": __("Admission Cycle"),
			"fieldtype": "Link",
			"options": "Admission Cycle",
			"get_query": function () {
				let year = frappe.query_report.get_filter_value('admission_year');
				if (year) {
					return {
						filters: { 'admission_year': year }
					};
				}
			}
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "status",
			"label": __("Application Status"),
			"fieldtype": "Select",
			"options": "\nSubmitted\nSelected\nWaitlisted\nRejected\nOffer Accepted\nOffer Issued\nOffer Declined\nOffer Expired\nFee Paid"
		}
	],
	"onload": function (report) {
		report.page.add_inner_button(__("Refresh"), function () {
			report.refresh();
		});
		// Set chart height
		report.chart_options = { height: 350 };
		report.refresh();
	},
	"get_chart_data": function (columns, result) {
		if (!result || result.length === 0) return null;

		return {
			data: {
				labels: result.map(d => d.campus),
				datasets: [{
					name: __("Distribution"),
					values: result.map(d => d.count)
				}]
			},
			type: 'donut',
			height: 350,
			colors: ['#42a5f5', '#66bb6a', '#ffa726', '#ef5350', '#ab47bc', '#8d6e63', '#78909c']
		};
	}
};
