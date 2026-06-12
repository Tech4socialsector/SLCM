frappe.ui.form.on("Fee Demand", {
	refresh(frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("render_action_buttons");
	},

	set_status_indicator(frm) {
		const colors = {
			"Pending": "orange",
			"Partially Paid": "blue",
			"Paid": "green",
			"Overdue": "red",
			"Waived": "purple",
			"Cancelled": "grey",
		};
		if (frm.doc.status) {
			frm.page.set_indicator(frm.doc.status, colors[frm.doc.status] || "grey");
		}
	},

	render_action_buttons(frm) {
		if (frm.is_new()) return;

		const cancelable = !["Paid", "Cancelled"].includes(frm.doc.status);
		const editable = !["Paid", "Waived", "Cancelled"].includes(frm.doc.status);

		if (cancelable && frappe.user.has_role(["System Manager", "Campus Admin"])) {
			frm.add_custom_button(__("Cancel Demand"), () => {
				frappe.confirm(
					__("Are you sure you want to cancel this fee demand? This action cannot be undone."),
					() => {
						frm.call("cancel_demand").then(() => frm.reload_doc());
					}
				);
			}, __("Actions"));
		}

		// Show outstanding amount prominently
		if (frm.doc.outstanding_amount > 0) {
			frm.dashboard.add_comment(
				__("Outstanding: <strong>₹{0}</strong> | Due Date: <strong>{1}</strong>",
					[
						format_currency(frm.doc.outstanding_amount, "INR"),
						frappe.datetime.str_to_user(frm.doc.due_date)
					]
				),
				frm.doc.status === "Overdue" ? "red" : "blue",
				true
			);
		}
	},

	student(frm) {
		if (frm.doc.student) {
			frappe.db.get_value(
				"Student Master",
				frm.doc.student,
				["academic_year"],
				(r) => {
					if (r && r.academic_year && !frm.doc.academic_year) {
						frm.set_value("academic_year", r.academic_year);
					}
				}
			);
		}
	},

	fee_component(frm) {
		if (frm.doc.fee_component && !frm.doc.description) {
			frm.set_value("description", frm.doc.fee_component);
		}
		// Auto-set demand_type based on component type
		frappe.db.get_value("Fee Component", frm.doc.fee_component, "component_type", (r) => {
			if (r && r.component_type && !frm.doc.demand_type) {
				const type_map = {
					"Admission Fee": "Academic",
					"Re-admission Fee": "Academic",
					"Tuition and Facilities Fee": "Academic",
					"Housing and Mess Fee": "Hostel",
					"Off-campus Housing and Mess Fee": "Hostel",
					"Re-registration Tuition Fee": "Academic",
					"Student Refundable Deposit": "Deposit",
					"Annual Fee (PhD)": "Academic",
					"Continuation Fee (PhD)": "Academic",
					"Course Work Fee (PhD)": "Academic",
					"Registration Fee (PhD)": "Academic",
					"Examination Fee": "Examination",
					"Revaluation Fee": "Examination",
					"Convocation Fee": "Service",
					"Certificate Fee": "Service",
					"ID Card Fee": "Service",
					"Fine - Disciplinary": "Fine",
					"Fine - Hostel": "Fine",
					"Gap Year Fee": "Academic",
					"Mess Charges": "Hostel",
					"Electrical Appliance Charges": "Hostel",
					"Laundry Charges": "Hostel",
				};
				const demand_type = type_map[r.component_type];
				if (demand_type) frm.set_value("demand_type", demand_type);
			}
		});
	},

	original_amount(frm) {
		frm.trigger("recalculate_amounts");
	},

	waiver_amount(frm) {
		if (flt(frm.doc.waiver_amount) > flt(frm.doc.original_amount)) {
			frappe.msgprint({
				message: __("Waiver Amount cannot exceed Original Amount."),
				indicator: "red",
			});
			frm.set_value("waiver_amount", frm.doc.original_amount);
			return;
		}
		frm.trigger("recalculate_amounts");

		// Warn if editing a demand with existing payments
		if (flt(frm.doc.paid_amount) > 0) {
			frappe.show_alert({
				message: __("This demand already has payments recorded. "
					+ "Changing the waiver will update the outstanding amount."),
				indicator: "orange",
			});
		}
	},

	recalculate_amounts(frm) {
		const original = flt(frm.doc.original_amount);
		const waiver = flt(frm.doc.waiver_amount);
		const paid = flt(frm.doc.paid_amount);
		const credit = flt(frm.doc.credit_adjusted);

		const net_payable = original - waiver;
		const outstanding = Math.max(0, net_payable - paid - credit);

		frm.set_value("net_payable", net_payable);
		frm.set_value("outstanding_amount", outstanding);
	},
});
