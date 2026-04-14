// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("PACE Admission", {
    refresh(frm) {
        // Field Filters
        frm.set_query("academic_year", function () {
            return {
                filters: {
                    status: "Active"
                }
            };
        });

        // Date Constraints
        const today = new Date(frappe.datetime.get_today());
        if (frm.fields_dict.admission_open_date && frm.fields_dict.admission_open_date.datepicker) {
            frm.fields_dict.admission_open_date.datepicker.update({
                minDate: today,
            });
        }
        if (frm.fields_dict.admission_close_date && frm.fields_dict.admission_close_date.datepicker) {
            let until_min = frm.doc.admission_open_date ? new Date(frm.doc.admission_open_date) : today;
            frm.fields_dict.admission_close_date.datepicker.update({
                minDate: until_min,
            });
        }

        // Status Headlines and Intro
        slcm_update_pace_status_ui(frm);

        // Custom Buttons
        if (!frm.is_new() && frm.doc.docstatus < 2) {
            
            // 1. Activate Button
            if (frm.doc.status === "Draft" || frm.doc.status === "Closed") {
                frm.add_custom_button(__("Activate Admission"), function () {
                    const perform_activation = () => {
                        frappe.confirm(slcm_build_activate_confirm_msg(frm), () => {
                            if (frm.doc.docstatus === 0) {
                                frm.set_value("status", "Active");
                                frm.save("Submit");
                            } else {
                                frm.set_value("status", "Active");
                                frm.save();
                            }
                        });
                    };
                    slcm_run_pace_activation_checks(frm, perform_activation);
                }, __("Actions"));
            }

            // 2. Close Button
            if (frm.doc.status === "Active") {
                frm.add_custom_button(__("Close Admission"), function () {
                    frappe.confirm(__("Closing this admission will hide it from the portal. Continue?"), () => {
                        frm.set_value("status", "Closed");
                        frm.save().then(() => {
                            frappe.show_alert({ message: __("Admission Closed"), indicator: "orange" });
                        });
                    });
                }, __("Actions"));
            }
        }
    },
    onload(frm){
        frm.set_query("payment_receipt_template", function() {
            return {
                filters: {
                    'print_format_for': 'DocType',
                    'doc_type': 'PACE Receipt'
                }
            }
        })
    },

    status: function (frm) {
        if (frm.doc.status === "Active") {
            slcm_run_pace_activation_checks(frm, () => {
                // If it's a draft, suggest submission
                if (frm.doc.docstatus === 0) {
                    frappe.confirm(__("Setting status to 'Active' will submit this document upon saving. Do you want to continue?"), () => {
                        frm.save("Submit");
                    }, () => {
                        frm.set_value("status", "Draft");
                    });
                } else {
                    frappe.show_alert({ message: __("Admission status will be set to Active upon saving."), indicator: "green" });
                }
            }, () => {
                // Fail callback: reset to Draft or Closed
                frm.set_value("status", frm.doc.docstatus === 0 ? "Draft" : "Closed");
            });
        }
    },

    admission_open_date: function (frm) {
        if (frm.fields_dict.admission_close_date && frm.fields_dict.admission_close_date.datepicker) {
            let until_min = frm.doc.admission_open_date ? new Date(frm.doc.admission_open_date) : new Date(frappe.datetime.get_today());
            frm.fields_dict.admission_close_date.datepicker.update({
                minDate: until_min,
            });
        }
        slcm_debounced_pace_overlap_check(frm);
    },

    admission_close_date: function (frm) {
        slcm_debounced_pace_overlap_check(frm);
    },

    before_submit: function (frm) {
        // Force activation check on submit if status is Active
        if (!frm.flags) frm.flags = {};
        if (!frm.flags.ignore_submit_check && frm.doc.status === "Active") {
            frappe.validated = false;
            slcm_run_pace_activation_checks(frm, () => {
                frappe.confirm(slcm_build_activate_confirm_msg(frm), () => {
                    frm.set_value("status", "Active");
                    if (!frm.flags) frm.flags = {};
                    frm.flags.ignore_submit_check = true;
                    frm.save("Submit");
                });
            });
        }
    },
});

// Programme Table Validations
frappe.ui.form.on("PACE Admission Programme", {
    programme: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.programme) {
            let duplicate = (frm.doc.programmes || []).find(
                d => d.name !== row.name && d.programme === row.programme
            );
            if (duplicate) {
                frappe.msgprint({
                    title: __("Duplicate Entry"),
                    indicator: "red",
                    message: __("Programme <b>{0}</b> is already added at row {1}.", [row.programme, duplicate.idx])
                });
                frappe.model.set_value(cdt, cdn, "programme", null);
            }
        }
    }
});

// Helper Functions
function slcm_update_pace_status_ui(frm) {
    if (frm.doc.docstatus === 2) {
        frm.set_intro(__("This admission record has been <b>Cancelled</b>."), "red");
        return;
    }

    const s = frm.doc.status;
    if (s === "Active") {
        frm.set_intro(__("This admission is currently <b>Active</b> and visible on the portal."), "green");
    } else if (s === "Closed") {
        frm.set_intro(__("This admission is <b>Closed</b>. It is not visible on the portal."), "orange");
    } else {
        frm.set_intro(__("This admission is in <b>Draft</b> and will not be visible until activated."), "blue");
    }
}

function slcm_run_pace_activation_checks(frm, callback, fail_callback) {
    // 1. Check for any other Active admission
    frappe.db.get_value("PACE Admission", {
        status: "Active",
        name: ["!=", frm.doc.name]
    }, "name", (r) => {
        if (r && r.name) {
            frappe.msgprint({
                message: __("Another PACE Admission <b>{0}</b> is already Active. Close it before activating this one.", [r.name]),
                title: __("Active Admission Conflict"),
                indicator: "red"
            });
            if (fail_callback) fail_callback();
            return;
        }

        // 2. Check for date overlaps
        slcm_check_pace_admission_overlap(frm, callback, fail_callback);
    });
}

function slcm_check_pace_admission_overlap(frm, callback, fail_callback) {
    if (!frm.doc.admission_open_date || !frm.doc.admission_close_date) {
        if (callback) callback();
        return;
    }

    frappe.call({
        method: "slcm.pace.doctype.pace_admission.pace_admission.check_overlap",
        args: {
            name: frm.doc.name,
            open_date: frm.doc.admission_open_date,
            close_date: frm.doc.admission_close_date
        },
        callback: (r) => {
            if (r.message && !r.message.valid) {
                frappe.msgprint({
                    message: r.message.message,
                    title: __("Date Conflict"),
                    indicator: "red"
                });
                if (fail_callback) fail_callback();
            } else {
                if (callback) callback();
            }
        }
    });
}

const slcm_debounced_pace_overlap_check = frappe.utils.debounce((frm) => {
    if (frm.doc.status === "Active") {
        slcm_check_pace_admission_overlap(frm);
    }
}, 500);

function slcm_build_activate_confirm_msg(frm) {
    const today = frappe.datetime.get_today();
    const open_date = frm.doc.admission_open_date;
    const close_date = frm.doc.admission_close_date;

    let msg = "";

    if (open_date && today < open_date) {
        const days = frappe.datetime.get_diff(open_date, today);
        msg += __("⚠️ Opening date <b>{0}</b> is in the future ({1} day(s) from today).<br>", [open_date, days]);
    }

    if (close_date && today > close_date) {
        const days = frappe.datetime.get_diff(today, close_date);
        msg += __("⚠️ Closing date <b>{0}</b> has already passed ({1} day(s) ago).<br>", [close_date, days]);
    }

    if (msg) msg += "<br>";

    if (frm.doc.docstatus === 0) {
        msg += __("Submitting will mark this admission as <b>Active</b> and make it visible on the portal. Continue?");
    } else {
        msg += __("Do you want to activate this admission?");
    }

    return msg;
}
