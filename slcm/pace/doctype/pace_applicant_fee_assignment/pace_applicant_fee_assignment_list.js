frappe.listview_settings['PACE Applicant Fee Assignment'] = {
	onload: function(listview) {
		listview.page.add_inner_button(__("Enroll Student"), function() {
			open_enroll_dialog(listview);
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

function open_enroll_dialog(listview) {
	let applicants = [];
	let selected_applicants = [];

	const dialog = new frappe.ui.Dialog({
		title: __("Select PACE Application for Enrollment"),
		size: "extra-large",
		fields: [
			{
				label: __("ID"),
				fieldname: "name_filter",
				fieldtype: "Link",
				options: "PACE Application",
				on_change: () => refresh_table()
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Applicant Name"),
				fieldname: "applicant_name_filter",
				fieldtype: "Data",
				on_change: () => refresh_table()
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Programme"),
				fieldname: "programme_filter",
				fieldtype: "Link",
				options: "PACE Programme",
				on_change: () => refresh_table()
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Academic Year"),
				fieldname: "academic_year_filter",
				fieldtype: "Link",
				options: "Academic Year",
				on_change: () => refresh_table()
			},
			{
				fieldtype: "Section Break"
			},
			{
				fieldtype: "HTML",
				fieldname: "applicant_table_html",
			}
		],
		primary_action_label: __("Enroll"),
		primary_action: function() {
			const selected = dialog.$wrapper.find(".applicant-checkbox:checked").map(function() {
				return $(this).data("name");
			}).get();

			if (selected.length === 0) {
				frappe.msgprint(__("Please select at least one applicant."));
				return;
			}

			frappe.call({
				method: "slcm.pace.api.convert_applicants_to_students",
				args: {
					applicants: selected
				},
				freeze: true,
				freeze_message: __("Enrolling {0} applicants...", [selected.length]),
				callback: function(r) {
					if (r.message && r.message.status === "success") {
						frappe.show_alert({
							message: __("Successfully enrolled {0} applicants.", [r.message.converted_count]),
							indicator: "green"
						});
						dialog.hide();
						listview.refresh();
					}
				}
			});
		}
	});

	function refresh_table() {
		const values = dialog.get_values();
		frappe.call({
			method: "slcm.pace.api.get_applicants_for_conversion",
			args: {
				name: values.name_filter,
				applicant_name: values.applicant_name_filter,
				programme: values.programme_filter,
				academic_year: values.academic_year_filter
			},
			callback: function(r) {
				applicants = r.message || [];
				render_table();
			}
		});
	}

	function render_table() {
		let rows_html = "";
		if (applicants.length === 0) {
			rows_html = `<tr><td colspan="5" class="text-center text-muted">${__("No matching applicants found who have paid their 'Admission Fee'.")}</td></tr>`;
		} else {
			rows_html = applicants.map((row, idx) => `
				<tr>
					<td style="width: 40px; text-align: center;">
						<input type="checkbox" class="applicant-checkbox" data-name="${row.name}" data-idx="${idx}">
					</td>
					<td>
						<a class="text-primary font-weight-bold" href="/app/pace-application/${row.name}" target="_blank" data-doctype="PACE Application" data-name="${row.name}">
							${row.name}
						</a>
					</td>
					<td><b>${row.applicant_name || "-"}</b></td>
					<td>${row.programme || "-"}</td>
					<td>${row.academic_year || "-"}</td>
				</tr>
			`).join("");
		}

		const table_html = `
			<div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
				<label style="font-weight: 600; cursor: pointer; margin: 0;">
					<input type="checkbox" id="select-all-applicants"> &nbsp; ${__("Select All")}
				</label>
				<span id="applicant-sel-count" style="color: var(--text-muted); font-size: 12px;">
					0 ${__("selected")}
				</span>
			</div>
			<div style="max-height: 400px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 4px;">
				<table class="table table-bordered table-hover" style="margin: 0; background: white;">
					<thead style="position: sticky; top: 0; background: var(--bg-light); z-index: 1;">
						<tr>
							<th style="width: 40px;"></th>
							<th>${__("Applicant ID")}</th>
							<th>${__("Applicant Name")}</th>
							<th>${__("Programme")}</th>
							<th>${__("Academic Year")}</th>
						</tr>
					</thead>
					<tbody>
						${rows_html}
					</tbody>
				</table>
			</div>
		`;

		dialog.get_field("applicant_table_html").$wrapper.html(table_html);

		// Event listeners
		dialog.$wrapper.find("#select-all-applicants").on("change", function() {
			const checked = $(this).is(":checked");
			dialog.$wrapper.find(".applicant-checkbox").prop("checked", checked);
			update_selection_count();
		});

		dialog.$wrapper.on("change", ".applicant-checkbox", function() {
			const total = dialog.$wrapper.find(".applicant-checkbox").length;
			const checked = dialog.$wrapper.find(".applicant-checkbox:checked").length;
			dialog.$wrapper.find("#select-all-applicants").prop("checked", total === checked && total > 0);
			update_selection_count();
		});
	}

	function update_selection_count() {
		const count = dialog.$wrapper.find(".applicant-checkbox:checked").length;
		dialog.$wrapper.find("#applicant-sel-count").text(`${count} ${__("selected")}`);
	}

	dialog.show();
	refresh_table();
}
