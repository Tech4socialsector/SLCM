frappe.listview_settings['PACE Admission'] = {
	add_fields: ["status", "docstatus"],
	get_indicator: function (doc) {
		if (doc.status === "Active") {
			return [__("Active"), "green", "status,=,Active"];
		} else if (doc.status === "Closed") {
			return [__("Closed"), "orange", "status,=,Closed"];
		} else if (doc.status === "Draft") {
			return [__("Draft"), "blue", "status,=,Draft"];
		} else {
			// Fallback to standard docstatus if status is somehow missing
			if (doc.docstatus === 1) {
				return [__("Submitted"), "blue", "docstatus,=,1"];
			} else if (doc.docstatus === 2) {
				return [__("Cancelled"), "red", "docstatus,=,2"];
			} else {
				return [__("Draft"), "grey", "docstatus,=,0"];
			}
		}
	}
};
