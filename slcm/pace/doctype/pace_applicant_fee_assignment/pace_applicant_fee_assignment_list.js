frappe.listview_settings['PACE Applicant Fee Assignment'] = {
	onload: function(listview) {
		listview.page.add_inner_button(__("Convert to Student"), function() {
			const dialog = new frappe.ui.form.MultiSelectDialog({
				doctype: "PACE Application",
				target: listview,
				setters: {
					status: "Fee Paid",
					programme: null,
					academic_year: null
				},
				add_filters_group: 1,
				columns: ["name", "status", "programme"],
				get_query: function() {
					return {
						filters: {
							status: "Fee Paid"
						}
					};
				},
				action: function(selections) {
					if (selections.length === 0) {
						frappe.msgprint(__("Please select at least one applicant."));
						return;
					}
					
					frappe.call({
						method: "slcm.pace.api.convert_applicants_to_students",
						args: {
							applicants: selections
						},
						freeze: true,
						callback: function(r) {
							if (r.message && r.message.status === "success") {
								frappe.show_alert({
									message: __("Successfully converted {0} applicants to students.", [r.message.converted_count]),
									indicator: "green"
								});
								dialog.dialog.hide();
								listview.refresh();
							}
						}
					});
				}
			});
		});
	}
};
