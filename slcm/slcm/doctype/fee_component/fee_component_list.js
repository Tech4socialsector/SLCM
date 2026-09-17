frappe.listview_settings["Fee Component"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Fetch Default Components"), () => {
			frappe.confirm(
				__("This will create the standard Fee Components (with their ledger names) that don't already exist. Continue?"),
				() => {
					frappe.dom.freeze(__("Creating default Fee Components…"));
					frappe.call({
						method: "slcm.slcm.doctype.fee_component.fee_component.create_default_fee_components",
						callback(r) {
							frappe.dom.unfreeze();
							const res = r.message || {};
							const created = res.created || [];
							const skipped = res.skipped || [];
							frappe.msgprint({
								title: __("Default Fee Components"),
								message: __("Created: {0}<br>Already existed (skipped): {1}", [
									created.length ? created.join(", ") : __("None"),
									skipped.length ? skipped.join(", ") : __("None"),
								]),
							});
							listview.refresh();
						},
						error() {
							frappe.dom.unfreeze();
						},
					});
				}
			);
		});
	},
};
