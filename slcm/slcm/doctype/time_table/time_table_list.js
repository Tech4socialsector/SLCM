frappe.listview_settings["Time Table"] = {
	onload(listview) {
		const btn = listview.page.add_inner_button(__("Update Venue / Time"), function () {
			const selected = listview.get_checked_items();

			if (!selected.length) {
				frappe.msgprint({
					title: __("No Selection"),
					message: __("Please select at least one Time Table row to update."),
					indicator: "orange",
				});
				return;
			}

			show_bulk_venue_time_dialog(listview, selected);
		});

		// Stand-alone toolbar button (not buried in the Actions dropdown) so it's
		// easy to spot at a glance when rows are checked.
		btn.css({
			"background-color": "#000",
			color: "#fff",
			"border-color": "#000",
			"box-shadow": "none",
		});
	},
};

function show_bulk_venue_time_dialog(listview, selected) {
	const names = selected.map((d) => d.name);

	const dialog = new frappe.ui.Dialog({
		title: __("Update Venue / Time for {0} Selected Occurrence(s)", [names.length]),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p>${__(
					"This updates exactly the {0} row(s) you selected in the list. Any row that conflicts with an existing booking will block the whole update - nothing is saved until every selected row is conflict-free."
				).replace("{0}", `<b>${names.length}</b>`)}</p>`,
			},
			{
				fieldname: "venue",
				fieldtype: "Link",
				options: "Venue Master",
				label: __("New Venue"),
			},
			{
				fieldname: "from_time",
				fieldtype: "Time",
				label: __("New From Time"),
			},
			{
				fieldname: "to_time",
				fieldtype: "Time",
				label: __("New To Time"),
			},
		],
		primary_action_label: __("Apply"),
		primary_action: function (values) {
			const updates = {};
			if (values.venue) updates.venue = values.venue;
			if (values.from_time) updates.from_time = values.from_time;
			if (values.to_time) updates.to_time = values.to_time;

			if (!Object.keys(updates).length) {
				frappe.msgprint(__("Please provide at least one field to update."));
				return;
			}

			frappe.call({
				method: "slcm.slcm.doctype.time_table.time_table.bulk_update_selected_occurrences",
				args: {
					names: names,
					updates: updates,
				},
				freeze: true,
				freeze_message: __("Checking for conflicts and updating..."),
				callback: function (res) {
					if (res.message) {
						dialog.hide();
						let message = __("Updated {0} occurrence(s)", [res.message.updated_count]);
						if (res.message.skipped_count) {
							message += " " + __("({0} selected row(s) were skipped - cancelled or no longer exist)", [
								res.message.skipped_count,
							]);
						}
						frappe.show_alert(
							{
								message: message,
								indicator: res.message.skipped_count ? "orange" : "green",
							},
							7
						);
						listview.refresh();
					}
				},
			});
		},
	});

	dialog.show();
}
