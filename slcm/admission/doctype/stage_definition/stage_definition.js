frappe.ui.form.on("Stage Definition", {
    stage_type: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const eval_types = ["Interview", "Evaluation"];
        if (eval_types.includes(row.stage_type)) {
            frappe.show_alert({
                message: `Set an Evaluation Config for ${row.stage_name} to define scoring.`,
                indicator: "blue"
            }, 4);
        }
    }
});
