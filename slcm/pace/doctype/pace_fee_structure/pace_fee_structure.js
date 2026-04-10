frappe.ui.form.on("PACE Fee Structure", {
    refresh: function (frm) {
        // Any refresh logic
    },
    validate: function (frm) {
        // Ensure valid_from <= valid_to on client side too
        if (frm.doc.valid_from && frm.doc.valid_to) {
            if (frm.doc.valid_from > frm.doc.valid_to) {
                frappe.throw(__("Valid From cannot be greater than Valid Until"));
            }
        }
    },
    fee_components_add: function (frm) {
        calculate_grand_total(frm);
    },
    fee_components_remove: function (frm) {
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
    
    // Refresh the table field to show updated values in the grid
    frm.refresh_field("fee_components");
    
    calculate_grand_total(frm);
}

function calculate_grand_total(frm) {
    let total = 0;
    (frm.doc.fee_components || []).forEach(row => {
        total += flt(row.total_amount);
    });
    frm.set_value("total_amount", total);
}
