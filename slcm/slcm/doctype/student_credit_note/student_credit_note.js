frappe.ui.form.on("Student Credit Note", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
			frm.add_custom_button(__("Apply Credit to Demand"), () => {
				_apply_credit_dialog(frm);
			}, __("Actions"));
		}
	},

	student(frm) {
		if (frm.doc.student) {
			frm.set_query("source_receipt", () => ({
				filters: { student: frm.doc.student, docstatus: 1 },
			}));
		}
	},

	credit_amount(frm) {
		if (flt(frm.doc.credit_amount) <= 0) {
			frappe.msgprint({
				title: "Invalid Amount",
				message: "Credit Amount must be greater than zero.",
				indicator: "orange",
			});
		}
	},
});

function _apply_credit_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: "Apply Credit to Fee Demand",
		fields: [
			{
				fieldname: "fee_demand",
				label: "Fee Demand",
				fieldtype: "Link",
				options: "Fee Demand",
				reqd: 1,
				get_query: () => ({
					filters: {
						student: frm.doc.student,
						status: ["in", ["Pending", "Partially Paid", "Overdue"]],
					},
				}),
			},
			{
				fieldname: "amount",
				label: "Amount to Apply (₹)",
				fieldtype: "Currency",
				reqd: 1,
				description: `Available credit: ₹${frappe.format(frm.doc.available_credit, { fieldtype: "Currency" })}`,
			},
		],
		primary_action_label: "Apply",
		primary_action(values) {
			frappe.call({
				method: "apply_credit_to_demand",
				doc: frm.doc,
				args: { fee_demand: values.fee_demand, amount: values.amount },
				callback(r) {
					if (!r.exc) {
						d.hide();
						frm.reload_doc();
						frappe.msgprint({
							title: "Credit Applied",
							message: `₹${frappe.format(values.amount, { fieldtype: "Currency" })} applied to ${values.fee_demand}.`,
							indicator: "green",
						});
					}
				},
			});
		},
	});
	d.show();
}
