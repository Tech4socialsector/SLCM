frappe.listview_settings['PACE Applicant Fee Assignment'] = {
	onload: function(listview) {
		listview.page.add_inner_button(__("Convert to Student"), function() {
			const dialog = new frappe.ui.form.MultiSelectDialog({
				doctype: "PACE Application",
				primary_action_label: __("Convert"),
				setters: {
					applicant_name: null,
					status: "Fee Paid",
					programme: null,
					academic_year: null,
				},
				add_filters_group: 1,
				columns: ["name", "applicant_name", "programme", "academic_year", "status"],
				fields: [
					{ label: __("ID"), fieldname: "name", fieldtype: "Data" },
					{ label: __("Applicant Name"), fieldname: "applicant_name", fieldtype: "Data" },
					{ label: __("Programme"), fieldname: "programme", fieldtype: "Link", options: "PACE Programme" },
					{ label: __("Academic Year"), fieldname: "academic_year", fieldtype: "Link", options: "Academic Year" },
					{ label: __("Status"), fieldname: "status", fieldtype: "Link", options: "PACE Application Status" }
				],
				get_query: function() {
					return {
						filters: {
							status: "Fee Paid"
						},
						fields: ["name", "applicant_name", "programme", "academic_year", "status"]
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
						freeze_message: __("Processing {0} applicants...", [selections.length]),
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

			// Re-label logic for both search area and results area
			const relabel = () => {
				const $wrapper = dialog.dialog.$wrapper;
				
				// Search area label
				$wrapper.find('.frappe-control[data-fieldname="name"] label, .frappe-control[data-fieldname="name"] .control-label').text(__("ID"));
				
				// Table headers (multiple possible selectors depending on Frappe version)
				$wrapper.find('.results_area thead th, .results_area .dt-header .dt-cell__content').each(function() {
					if ($(this).text().trim() === __("Name")) {
						$(this).text(__("ID"));
					}
				});
			};

			// Run relabel multiple times during initial load as the table renders asynchronously
			let count = 0;
			const interval = setInterval(() => {
				relabel();
				count++;
				if (count > 20) clearInterval(interval);
			}, 150);

			// Also observe for dynamic updates in the results area (filtering, paging)
			const attach_observer = () => {
				const results_area = dialog.dialog.$wrapper.find('.results_area').get(0);
				if (results_area) {
					const observer = new MutationObserver(relabel);
					observer.observe(results_area, { childList: true, subtree: true });
					dialog.dialog.on_hide = () => {
						observer.disconnect();
						clearInterval(interval);
					};
				} else if (count < 20) {
					setTimeout(attach_observer, 250);
				}
			};
			attach_observer();
		});
	},
	refresh: function(listview) {
		// Change 'Name' header to 'ID' in the main list view
		listview.$result.find('.list-row-head .list-column').each(function() {
			if ($(this).text().trim() === __("Name")) {
				$(this).text(__("ID"));
			}
		});
	}
};
