frappe.ui.form.on("Convocation Registration", {
	convocation_type(frm) {
		_set_amount_preview(frm);
	},

	refresh(frm) {
		if (frm.doc.convocation_fee_demand) {
			frm.add_custom_button(__("View Fee Demand"), () => {
				frappe.set_route("Form", "Fee Demand", frm.doc.convocation_fee_demand);
			});
		}
		if (frm.doc.docstatus === 0 && frm.doc.convocation_type) {
			_set_amount_preview(frm);
		}
	},
});

function _set_amount_preview(frm) {
	const fees = { "In-Person": 1500, "In-Absentia": 2000 };
	const type = frm.doc.convocation_type;
	if (!type) return;

	frappe.db.get_value("Fee Component", { component_type: "Convocation Fee" }, "amount", (r) => {
		let amount;
		if (r && r.amount > 0) {
			amount = r.amount + (type === "In-Absentia" ? 500 : 0);
		} else {
			amount = fees[type] || 1500;
		}
		frm.set_value("amount", amount);
		frm.dashboard.set_headline(
			`<b>Convocation Type:</b> ${type} &nbsp;|&nbsp; <b>Fee:</b> ₹${frappe.format(amount, { fieldtype: "Currency" })}`
		);
	});
}
