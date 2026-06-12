frappe.ui.form.on("Fee Concession", {
	refresh(frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("set_fee_demand_filter");
	},

	set_status_indicator(frm) {
		const colors = {
			"Draft": "orange",
			"Approved": "green",
			"Rejected": "red",
			"Reversed": "grey",
		};
		if (frm.doc.status) {
			frm.page.set_indicator(frm.doc.status, colors[frm.doc.status] || "grey");
		}
	},

	set_fee_demand_filter(frm) {
		frm.set_query("fee_demand", () => {
			const filters = {
				status: ["not in", ["Paid", "Cancelled", "Waived"]],
			};
			if (frm.doc.student) {
				filters.student = frm.doc.student;
			}
			return { filters };
		});
	},

	student(frm) {
		frm.set_value("fee_demand", "");
		frm.trigger("set_fee_demand_filter");
	},

	fee_demand(frm) {
		if (!frm.doc.fee_demand) return;
		frappe.db.get_value(
			"Fee Demand",
			frm.doc.fee_demand,
			["fee_component", "original_amount", "paid_amount", "status"],
			(r) => {
				if (r) {
					frm.set_value("fee_component", r.fee_component);
					frm.set_value("original_amount", r.original_amount);
				}
			}
		);
	},

	waiver_mode(frm) {
		frm.trigger("calculate_waiver");
	},

	waiver_value(frm) {
		frm.trigger("calculate_waiver");
	},

	original_amount(frm) {
		frm.trigger("calculate_waiver");
	},

	calculate_waiver(frm) {
		const original = flt(frm.doc.original_amount);
		const value = flt(frm.doc.waiver_value);

		if (!original || !value) return;

		let waiver = 0;
		if (frm.doc.waiver_mode === "Percentage") {
			if (value > 100) {
				frappe.show_alert({ message: __("Percentage cannot exceed 100."), indicator: "red" });
				return;
			}
			waiver = Math.round(original * value / 100 * 100) / 100;
		} else {
			waiver = value;
		}

		if (waiver > original) {
			frappe.show_alert({
				message: __("Waiver Amount cannot exceed Original Amount ₹{0}", [format_currency(original, "INR")]),
				indicator: "red",
			});
			return;
		}

		frm.set_value("waiver_amount", waiver);

		// Show live preview
		frappe.show_alert({
			message: __("Waiver: ₹{0} | Outstanding after waiver: ₹{1}", [
				format_currency(waiver, "INR"),
				format_currency(Math.max(0, original - waiver - flt(frm.doc.paid_amount)), "INR"),
			]),
			indicator: "blue",
		});
	},
});
