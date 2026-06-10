frappe.ui.form.on("PACE Fee Structure", {
    refresh: function (frm) {
        // Any refresh logic
        setTimeout(() => {

            // Hide Assignments
            frm.page.wrapper.find('.form-assignments').hide();

            // Hide Tags
            frm.page.wrapper.find('.form-tags').hide();

            // Hide Shared
            frm.page.wrapper.find('.form-shared').hide();

            frm.page.wrapper.find('.form-attachments').hide();

        }, 200);
    },
    currency: function(frm) {
        // Refresh child tables to show updated currency symbols
        frm.refresh_field("fee_components_for_indians");
        frm.refresh_field("fee_components_for_foreign");
        frm.refresh_field("other_fees");
    },
    validate: function (frm) {
        if (frm.is_new() && frm.doc.valid_from) {
            if (frm.doc.valid_from < frappe.datetime.get_today()) {
                frappe.throw(__("Valid From date cannot be a past date"));
            }
        }
        // Ensure valid_from <= valid_to on client side too
        if (frm.doc.valid_from && frm.doc.valid_to) {
            if (frm.doc.valid_from > frm.doc.valid_to) {
                frappe.throw(__("Valid From cannot be greater than Valid Until"));
            }
        }
    },
    fee_components_for_indians_add: function (frm) {
        calculate_grand_total(frm);
    },
    fee_components_for_indians_remove: function (frm) {
        calculate_grand_total(frm);
    },
    fee_components_for_foreign_add: function (frm) {
        calculate_grand_total(frm);
    },
    fee_components_for_foreign_remove: function (frm) {
        calculate_grand_total(frm);
    },
    other_fees_add: function (frm) {
        calculate_grand_total(frm);
    },
    other_fees_remove: function (frm) {
        calculate_grand_total(frm);
    }
});

frappe.ui.form.on("PACE Fee Component", {
    fee_component: function (frm, cdt, cdn) {
        // Trigger calculation when fee component is selected (amount is fetched)
        setTimeout(() => {
            calculate_row_total(frm, cdt, cdn);
        }, 500);
    },
    amount: function (frm, cdt, cdn) {
        calculate_row_total(frm, cdt, cdn);
    },
    tax_rate: function (frm, cdt, cdn) {
        calculate_row_total(frm, cdt, cdn);
    }
});

function calculate_row_total(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let amount = flt(row.amount);
    let tax_rate = flt(row.tax_rate);
    
    let tax_amount = (amount * tax_rate) / 100;
    let total_amount = amount + tax_amount;

    frappe.model.set_value(cdt, cdn, "tax_amount", tax_amount);
    frappe.model.set_value(cdt, cdn, "total_amount", total_amount);
    
    // Refresh the specific table field to show updated values in the grid
    if (row.parentfield) {
        frm.refresh_field(row.parentfield);
    }
    
    calculate_grand_total(frm);
}

function calculate_grand_total(frm) {
    let total_indian = 0;
    let total_foreign = 0;

    // Sum Indian components
    (frm.doc.fee_components_for_indians || []).forEach(row => {
        total_indian += flt(row.total_amount);
    });

    // Sum Foreign components
    (frm.doc.fee_components_for_foreign || []).forEach(row => {
        total_foreign += flt(row.total_amount);
    });

    // Note: other_fees are intentionally excluded from these totals as per user request

    frm.set_value("total_amount", total_indian);
    frm.set_value("total_amount_for_foreign", total_foreign);
}
