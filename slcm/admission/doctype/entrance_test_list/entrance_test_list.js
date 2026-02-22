frappe.ui.form.on("Entrance Test List", {
    refresh: function (frm) {
        if (frm.doc.status === "Generated") {
            frm.add_custom_button(__("Allocate Seats"), function () {
                open_allocation_dialog(frm);
            }, __("Actions"));
        }
    }
});

function open_allocation_dialog(frm) {
    // Filter unallocated applicants
    const applicants = (frm.doc.entrance_test_applicant || []).filter(a => a.allocation_status !== "Allocated");

    if (!applicants.length) {
        frappe.msgprint({
            title: __("No Applicants"),
            message: __("All applicants in this list have already been allocated seats."),
            indicator: "orange"
        });
        return;
    }

    // Build table rows
    const rows_html = applicants.map((row, idx) => `
		<tr data-idx="${idx}">
			<td style="text-align:center; width:40px;">
				<input type="checkbox" class="applicant-checkbox" data-name="${row.name}" data-idx="${idx}">
			</td>
			<td><b>${row.candidate_name || "Unknown"}</b></td>
			<td>${row.applicant_id || "-"}</td>
			<td>${row.program || "-"}</td>
			<td>${row.reservation_category || "-"}</td>
		</tr>
	`).join("");

    let d = new frappe.ui.Dialog({
        title: __("Allocate Seats"),
        size: "extra-large",
        fields: [
            {
                label: __("Provider Type"),
                fieldname: "provider_type",
                fieldtype: "Select",
                options: ["Internal", "External"],
                reqd: 1,
                on_change: function () {
                    d.set_value("entrance_test_provider", "");
                }
            },
            {
                label: __("Entrance Test Provider"),
                fieldname: "entrance_test_provider",
                fieldtype: "Link",
                options: "Entrance Test Provider",
                reqd: 1,
                get_query: function () {
                    return {
                        filters: {
                            provider_type: d.get_value("provider_type"),
                            active: 1,
                            campus: frm.doc.campus
                        }
                    };
                }
            },
            {
                fieldtype: "Column Break"
            },
            {
                label: __("Auto-select (Enter Number)"),
                fieldname: "auto_select_count",
                fieldtype: "Int",
                description: __("Enter count to automatically select first N students")
            },
            {
                fieldtype: "Section Break"
            },
            {
                fieldtype: "HTML",
                fieldname: "applicant_table",
                options: `
					<div style="margin-bottom:10px; display:flex; gap:12px; align-items:center;">
						<label style="font-weight:600; cursor:pointer; margin:0; display: flex; align-items: center;">
							<input type="checkbox" id="select-all-chk">
							<span style="margin-left: 8px;">Select All</span>
						</label>
						<span id="sel-count" style="color:#6c757d; font-size:12px;">
							0 of ${applicants.length} selected
						</span>
					</div>
					<div style="max-height:400px; overflow-y:auto; border:1px solid #d1d8dd; border-radius:4px;">
						<table class="table table-bordered table-hover" style="margin:0; font-size: 13px;">
							<thead style="position:sticky; top:0; background:#f4f5f6; z-index:1;">
								<tr>
									<th style="width:40px;"></th>
									<th>Candidate Name</th>
									<th>Applicant ID</th>
									<th>Program</th>
									<th>Category</th>
								</tr>
							</thead>
							<tbody>${rows_html}</tbody>
						</table>
					</div>
				`
            }
        ],
        primary_action_label: __("Allocate Seats"),
        primary_action(values) {
            const checked_els = [...d.$wrapper.find(".applicant-checkbox:checked")];
            if (!checked_els.length) {
                frappe.msgprint(__("Please select at least one applicant."));
                return;
            }

            const selected_names = checked_els.map(el => $(el).attr("data-name"));

            frappe.call({
                method: "allocate_seats",
                doc: frm.doc,
                args: {
                    provider: values.entrance_test_provider,
                    selected_applicants: selected_names
                },
                freeze: true,
                freeze_message: __("Allocating Seats..."),
                callback: function (r) {
                    if (!r.exc) {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({
                            message: __("Successfully allocated seats for {0} applicants", [r.message]),
                            indicator: "green"
                        });
                    }
                }
            });
        }
    });

    d.show();

    // Event Listeners for the Table
    const $wrapper = d.$wrapper;

    // Select All
    $wrapper.find("#select-all-chk").on("change", function () {
        $wrapper.find(".applicant-checkbox").prop("checked", this.checked);
        update_sel_count(d, applicants.length);
    });

    // Individual Checkbox
    $wrapper.on("change", ".applicant-checkbox", function () {
        const total = $wrapper.find(".applicant-checkbox").length;
        const n = $wrapper.find(".applicant-checkbox:checked").length;
        $wrapper.find("#select-all-chk").prop("checked", total === n && total > 0);
        update_sel_count(d, applicants.length);
    });

    // Auto-select logic
    d.fields_dict.auto_select_count.$input.on("input", function () {
        let val = parseInt($(this).val()) || 0;
        $wrapper.find(".applicant-checkbox").prop("checked", false);
        $wrapper.find(".applicant-checkbox").slice(0, val).prop("checked", true);

        const total = $wrapper.find(".applicant-checkbox").length;
        const n = $wrapper.find(".applicant-checkbox:checked").length;
        $wrapper.find("#select-all-chk").prop("checked", total === n && total > 0);
        update_sel_count(d, applicants.length);
    });
}

function update_sel_count(d, total) {
    const count = d.$wrapper.find(".applicant-checkbox:checked").length;
    d.$wrapper.find("#sel-count").text(`${count} of ${total} selected`);
}
