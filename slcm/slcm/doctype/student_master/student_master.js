// Copyright (c) 2025, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student Master", {
	before_save(frm) {
		if (frm.doc.program_shortcode && frm.doc.current_year) {
			frm.set_value(
				"naming_series",
				`${frm.doc.program_shortcode}${frm.doc.current_year}.###`
			);
		}
	},

	dob(frm) {
		if (!frm.doc.dob) return;

		const dob = frappe.datetime.str_to_obj(frm.doc.dob);
		const today = frappe.datetime.str_to_obj(frappe.datetime.now_date());

		// DOB cannot be today or future
		if (dob >= today) {
			frappe.msgprint(__("Date of Birth cannot be today or a future date."));
			frm.set_value("dob", "");
			return;
		}

		// DOB cannot be current year
		if (dob.getFullYear() === today.getFullYear()) {
			frappe.msgprint(__("Date of Birth cannot be in the current year."));
			frm.set_value("dob", "");
			return;
		}

		// Minimum age = 15
		let age = today.getFullYear() - dob.getFullYear();
		const m = today.getMonth() - dob.getMonth();

		if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
			age--;
		}

		if (age < 15) {
			frappe.msgprint(__("Student must be at least 15 years old."));
			frm.set_value("dob", "");
		}
	},

	refresh(frm) {
		// Hide default left sidebar
		$(".layout-side-section").hide();

		// Render custom right-side profile panel
		frm.trigger("render_profile_sidebar");

		// Custom Status Button
		if (!frm.is_new()) {
			const status_btn = frm.add_custom_button(
				__("Status"),
				function () {
					frm.trigger("show_status_dialog");
				},
				__("Update Status")
			).addClass("btn-primary");

			status_btn.css({
				"background-color": "#000",
				color: "#fff",
				"border-color": "#000",
				"box-shadow": "none",
			});

			// Download Registration Slip
			const download_btn = frm.add_custom_button(
				__("Registration Slip"),
				function () {
					const student_name = frm.doc.name;
					const url = frappe.urllib.get_full_url(
						`/api/method/frappe.utils.print_format.download_pdf?doctype=Student+Master&name=${encodeURIComponent(student_name)}&format=Student+Registration+Slip`
					);
					frappe.show_alert({ message: __("Generating PDF..."), indicator: "blue" });
					fetch(url, { credentials: "same-origin" })
						.then((res) => {
							if (!res.ok) throw new Error("Failed");
							return res.blob();
						})
						.then((blob) => {
							const a = document.createElement("a");
							a.href = URL.createObjectURL(blob);
							a.download = `Registration_Slip_${student_name}.pdf`;
							document.body.appendChild(a);
							a.click();
							a.remove();
							URL.revokeObjectURL(a.href);
						})
						.catch(() => {
							frappe.msgprint({
								title: __("Error"),
								message: __("Could not generate PDF. Please try again."),
								indicator: "red",
							});
						});
				},
				__("Download")
			);

			setDarkButtonStyle(download_btn);

			// ── Download Fee Invoice — standalone button (live server fetch) ──
			const inv_dl_btn = frm.add_custom_button(
				__("⬇ Fee Invoice"),
				function () {
					// Always fetch live from DB — never rely on stale frm.doc.fee_invoices
					frappe.show_alert({ message: __("Loading invoices…"), indicator: "blue" });
					frappe.call({
						method: "frappe.client.get_list",
						args: {
							doctype:          "Fee Invoice",
							filters:          { student: frm.doc.name },
							fields:           ["name", "academic_term", "academic_year",
							                   "invoice_date", "due_date",
							                   "final_payable_amount", "paid_amount",
							                   "outstanding_amount", "status"],
							order_by:         "invoice_date desc, creation desc",
							limit_page_length: 50,
						},
						callback: function (r) {
							const invoices = r.message || [];
							if (!invoices.length) {
								frappe.msgprint({
									title:     __("No Fee Invoices"),
									message:   __("No fee invoices exist for this student yet."),
									indicator: "orange",
								});
								return;
							}
							_show_invoice_download_dialog(frm, invoices);
						},
					});
				}
			);
			inv_dl_btn.css({
				"background-color": "#1a3c6e",
				"color":            "#fff",
				"border-color":     "#1a3c6e",
				"font-weight":      "600",
			});

			// ── Sync Fee Invoices — standalone button ─────────────────────────
			const sync_btn = frm.add_custom_button(
				__("🔄 Sync Fee Invoices"),
				function () {
					frappe.show_alert({ message: __("Syncing fee invoices…"), indicator: "blue" });
					frappe.call({
						method: "slcm.slcm.doctype.student_master.student_master.sync_fee_invoices",
						args:   { student_name: frm.doc.name },
						callback: function (r) {
							const n = (r.message && r.message.synced) || 0;
							frappe.show_alert({
								message:   __(`✔ ${n} invoice(s) synced successfully.`),
								indicator: "green",
							});
							frm.reload_doc();
						},
						error: function () {
							frappe.show_alert({ message: __("Sync failed. Check error log."), indicator: "red" });
						},
					});
				}
			);
			// Style: teal/green background
			sync_btn.css({
				"background-color": "#0d7a5f",
				"color":            "#fff",
				"border-color":     "#0d7a5f",
				"font-weight":      "600",
			});

			// Check Enrollment Eligibility and Add Button
			frappe.call({
				method: "slcm.slcm.doctype.student_master.student_master.validate_new_enrollment",
				args: {
					student_id: frm.doc.name,
				},
				callback: function (r) {
					if (r.message && r.message.allowed) {
						const enroll_btn = frm.add_custom_button(__("Enroll"), function () {
							// Re-validate on click to prevent race conditions
							frappe.call({
								method: "slcm.slcm.doctype.student_master.student_master.validate_new_enrollment",
								args: {
									student_id: frm.doc.name,
								},
								callback: function (r2) {
									if (r2.message && r2.message.allowed) {
										frappe.new_doc("Student Enrollment", {
											student: frm.doc.name,
											student_name: [
												frm.doc.first_name,
												frm.doc.middle_name,
												frm.doc.last_name,
											]
												.filter(Boolean)
												.join(" "),
											cohort: frm.doc.programme,
											batch_year_ref: frm.doc.batch_year,
											academic_year: frm.doc.academic_year,
										});
									} else {
										frappe.msgprint({
											title: __("Not Allowed"),
											message: r2.message
												? r2.message.message
												: __("Enrollment not allowed."),
											indicator: "orange",
										});
									}
								},
							});
						}).addClass("btn-primary");
								setDarkButtonStyle(enroll_btn);
					}
				},
			});
		}
	},

	show_status_dialog(frm) {
		// Fetch available actions
		frappe.call({
			method: "slcm.slcm.doctype.student_master.student_master.get_available_status_actions",
			args: {
				student_id: frm.doc.name,
			},
			callback: function (r) {
				if (r.message) {
					show_status_transition_dialog(frm, r.message);
				}
			},
		});
	},

	render_profile_sidebar(frm) {
		if (frm.is_new()) {
			return;
		}

		const image = frm.doc.student_image || frm.doc.passport_size_photo || "/assets/frappe/images/default-avatar.png";

		const html = `
			<div class="student-profile-card">
				<img src="${image}" class="student-avatar" />
				<button class="btn btn-sm btn-primary upload-btn">
					Upload Image
				</button>
				<hr />
				<div class="attachment-area">
					<h6>Attachments</h6>
					<div class="attachments"></div>
				</div>
			</div>
		`;

		if (frm.fields_dict.profile_sidebar) {
			frm.fields_dict.profile_sidebar.$wrapper.html(html);

			frm.fields_dict.profile_sidebar.$wrapper.find(".upload-btn").on("click", () => {
				new frappe.ui.FileUploader({
					doctype: frm.doctype,
					docname: frm.doc.name,
					on_success(file) {
						if (file.file_url && file.file_url.match(/\.(jpg|jpeg|png|webp)$/i)) {
							frm.set_value("passport_size_photo", file.file_url);
							frm.save().then(() => {
								frm.reload_doc();
							});
						}
					},
				});
			});
		}
	},

	programme(frm) {
		if (!frm.doc.programme) return;
		frappe.call({
			method: "slcm.slcm.doctype.student_master.student_master.fetch_program_fee_details",
			args: { programme: frm.doc.programme },
			callback(r) {
				const data = r && r.message;
				if (!data || !data.total_program_fee) {
					frappe.show_alert({ message: __("No active Student Fee Structure found for this programme."), indicator: "orange" });
					return;
				}
				if (!frm.doc.total_program_fee) {
					frm.set_value("total_program_fee", data.total_program_fee);
				}
				if (data.fee_structure && !frm.doc.fee_structure) {
					frm.set_value("fee_structure", data.fee_structure);
				}
				frappe.show_alert({
					message: __("Fee loaded: ₹{0}", [frappe.utils.fmt_money(data.total_program_fee, 0, "INR")]),
					indicator: "green"
				});
			},
		});
	},

	total_program_fee(frm) {
		frm.trigger("calculate_fees");
	},

	scholarship_percentage(frm) {
		frm.trigger("calculate_fees");
	},

	total_paid_amount(frm) {
		frm.trigger("calculate_fees");
	},

	applying_scholarship(frm) {
		if (frm.doc.applying_scholarship !== "Yes") {
			frm.set_value("scholarship_percentage", 0);
		}
		frm.trigger("calculate_fees");
	},

	calculate_fees(frm) {
		let total_fee = frm.doc.total_program_fee || 0;
		let scholarship_pct = frm.doc.scholarship_percentage || 0;
		let paid_amount = frm.doc.total_paid_amount || 0;

		if (frm.doc.applying_scholarship !== "Yes") {
			scholarship_pct = 0;
		}

		let discount = (total_fee * scholarship_pct) / 100;
		let net_fee = total_fee - discount;
		let balance = net_fee - paid_amount;

		frm.set_value("discount_amount", discount);
		frm.set_value("net_program_fee", net_fee);
		frm.set_value("outstanding_balance", balance);
	},

	state(frm) {
		// Clear district when state changes
		if (frm.doc.district) {
			frm.set_value('district', '');
		}

		// Set filter for district based on selected state
		frm.set_query('district', function () {
			return {
				filters: {
					'state': frm.doc.state
				}
			};
		});
	}
});

function setDarkButtonStyle(btn) {
	if (!btn || !btn.length) return;
	btn.css({
		"background-color": "#000",
		color: "#fff",
		"border-color": "#000",
		"box-shadow": "none",
	});
}

/* ── Fee Invoice Download Dialog ─────────────────────────────────────────────
   Shows a clean term-wise table of all invoices.
   Each row has its own "Download PDF" button so the REGO office can pick
   any term without extra prompts.
   Data is always fetched live from the server — never from cached doc fields.
────────────────────────────────────────────────────────────────────────────── */
function _show_invoice_download_dialog(frm, invoices) {
	const student_label = [frm.doc.first_name, frm.doc.last_name].filter(Boolean).join(" ")
	                      || frm.doc.name;

	// Status badge colours
	const STATUS_COLOR = {
		"Paid":           { bg: "#dcfce7", text: "#166534" },
		"Partially Paid": { bg: "#fef3c7", text: "#92400e" },
		"Unpaid":         { bg: "#fee2e2", text: "#991b1b" },
		"Overdue":        { bg: "#fee2e2", text: "#991b1b" },
		"Cancelled":      { bg: "#f3f4f6", text: "#6b7280" },
	};

	function fmt_inr(v) {
		return "₹" + parseFloat(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 0 });
	}
	function badge(status) {
		const c = STATUS_COLOR[status] || STATUS_COLOR["Unpaid"];
		return `<span style="background:${c.bg};color:${c.text};padding:2px 10px;
		        border-radius:20px;font-size:11px;font-weight:700;">${status}</span>`;
	}

	// Build table rows
	let rows_html = invoices.map((inv, idx) => {
		const term   = inv.academic_term  || inv.academic_year || "—";
		const i_date = inv.invoice_date   ? frappe.datetime.str_to_user(inv.invoice_date) : "—";
		const d_date = inv.due_date       ? frappe.datetime.str_to_user(inv.due_date)     : "—";
		const net    = fmt_inr(inv.final_payable_amount);
		const paid   = fmt_inr(inv.paid_amount);
		const due    = fmt_inr(Math.max(inv.outstanding_amount || 0, 0));
		const row_bg = idx % 2 === 0 ? "#fff" : "#f9fafb";

		return `
		<tr style="background:${row_bg};">
			<td style="padding:10px 12px;font-weight:600;color:#1f2937;">${inv.name}</td>
			<td style="padding:10px 12px;color:#374151;">${term}</td>
			<td style="padding:10px 12px;color:#6b7280;font-size:12px;">${i_date}</td>
			<td style="padding:10px 12px;color:#6b7280;font-size:12px;">${d_date}</td>
			<td style="padding:10px 12px;font-weight:600;">${net}</td>
			<td style="padding:10px 12px;color:#16a34a;font-weight:600;">${paid}</td>
			<td style="padding:10px 12px;color:#dc2626;font-weight:600;">${due}</td>
			<td style="padding:10px 12px;">${badge(inv.status)}</td>
			<td style="padding:10px 12px;text-align:center;">
				<button
					class="btn btn-xs"
					style="background:#1a3c6e;color:#fff;border:none;border-radius:6px;
					       padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;
					       white-space:nowrap;"
					onclick="_sp_dl_invoice('${inv.name}', this)">
					⬇ PDF
				</button>
			</td>
		</tr>`;
	}).join("");

	const table_html = `
	<style>
		.sp-inv-table { width:100%; border-collapse:collapse; font-family:inherit; }
		.sp-inv-table th { background:#1a3c6e; color:#fff; padding:10px 12px;
		                   font-size:11px; font-weight:700; text-transform:uppercase;
		                   letter-spacing:0.04em; text-align:left; }
		.sp-inv-table tr:hover td { background:#eff6ff !important; }
	</style>
	<div style="overflow-x:auto;margin-top:4px;">
		<table class="sp-inv-table">
			<thead>
				<tr>
					<th>Invoice #</th>
					<th>Term</th>
					<th>Invoice Date</th>
					<th>Due Date</th>
					<th>Net Payable</th>
					<th>Paid</th>
					<th>Outstanding</th>
					<th>Status</th>
					<th style="text-align:center;">Download</th>
				</tr>
			</thead>
			<tbody>${rows_html}</tbody>
		</table>
	</div>
	<p style="font-size:11px;color:#9ca3af;margin-top:10px;">
		${invoices.length} invoice(s) found for <strong>${student_label}</strong>
	</p>`;

	const d = new frappe.ui.Dialog({
		title:  `Fee Invoices — ${student_label}`,
		fields: [{ fieldtype: "HTML", fieldname: "inv_table", options: table_html }],
		size:   "extra-large",
	});
	d.show();

	// Attach the per-row download handler to window so inline onclick can reach it.
	// Use window.open() instead of fetch() — fetch() routes through Frappe's request.js
	// which can trigger logout when any concurrent 403 (e.g. route_history) is detected.
	window._sp_dl_invoice = function (inv_name, btn_el) {
		const orig_text = btn_el.innerHTML;
		btn_el.disabled    = true;
		btn_el.textContent = "…";

		// Include the CSRF token as a query parameter so Frappe never treats
		// this as an unauthenticated request even in strict browser contexts.
		const csrf  = frappe.csrf_token || "";
		const url   = `/api/method/slcm.api.student_portal.download_fee_invoice_admin`
		            + `?invoice_name=${encodeURIComponent(inv_name)}`
		            + (csrf ? `&X-Frappe-CSRF-Token=${encodeURIComponent(csrf)}` : "");

		// Open in new tab — browser handles the PDF download natively,
		// completely bypassing Frappe's JS error / session handler.
		window.open(url, "_blank");

		frappe.show_alert({ message: `Downloading Invoice ${inv_name}…`, indicator: "blue" });

		// Give visual feedback then reset the button
		setTimeout(() => {
			btn_el.innerHTML        = "✔ Done";
			btn_el.style.background = "#16a34a";
			setTimeout(() => {
				btn_el.innerHTML        = orig_text;
				btn_el.style.background = "#1a3c6e";
				btn_el.disabled         = false;
			}, 2500);
		}, 600);
	};
}

function show_status_transition_dialog(frm, data) {
	const current_status = data.current_status || "Selected";
	const available_actions = data.available_actions || [];

	if (available_actions.length === 0) {
		frappe.msgprint({
			title: __("No Actions Available"),
			message: __("You do not have permission to change the status from {0}.", [
				current_status,
			]),
			indicator: "orange",
		});
		return;
	}

	// Create dialog
	let dialog = new frappe.ui.Dialog({
		title: __("Update Registration Status"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<div class="alert alert-info">
					<strong>Current Status:</strong> ${current_status}
				</div>`,
			},
			{
				fieldtype: "Select",
				fieldname: "new_status",
				label: __("New Status"),
				options: available_actions.map((a) => a.next_state).join("\n"),
				reqd: 1,
			},
			{
				fieldtype: "Small Text",
				fieldname: "remarks",
				label: __("Remarks"),
				reqd: 1,
			},
		],
		primary_action_label: __("Update Status"),
		primary_action: function () {
			const values = dialog.get_values();
			if (!values.new_status) {
				frappe.msgprint({
					title: __("Required"),
					message: __("Please select a new status"),
					indicator: "orange",
				});
				return;
			}

			if (!values.remarks || !values.remarks.trim()) {
				frappe.msgprint({
					title: __("Required"),
					message: __("Please enter remarks"),
					indicator: "orange",
				});
				return;
			}

			let confirm_message = __("Are you sure you want to change status from <b>{0}</b> to <b>{1}</b>?", [
				current_status,
				values.new_status,
			]);

			if (values.new_status === "Re-Open") {
				confirm_message = __("Are you sure you want to <b>Re-Open</b> this application? <br>This might require re-verification of all details.");
			}
			

			// Confirm action
			frappe.confirm(
				confirm_message,
				function () {
					// Yes
					frappe.call({
						method: "slcm.slcm.doctype.student_master.student_master.update_registration_status",
						args: {
							student_id: frm.doc.name,
							new_status: values.new_status,
							remarks: values.remarks,
						},
						freeze: true,
						freeze_message: __("Updating status..."),
						callback: function (r) {
							if (r.message && r.message.status === "success") {
								frappe.show_alert({
									message: r.message.message,
									indicator: "green",
								});
								dialog.hide();
								frm.reload_doc();
							} else {
								frappe.msgprint({
									title: __("Error"),
									message: r.message
										? r.message.message || r.message
										: __("Failed to update status"),
									indicator: "red",
								});
							}
						},
						error: function (r) {
							frappe.msgprint({
								title: __("Error"),
								message:
									r.message || __("Failed to update status. Please try again."),
								indicator: "red",
							});
						},
					});
				},
				function () {
					// No
					dialog.hide();
				}
			);
		},
	});

	dialog.show();
}
