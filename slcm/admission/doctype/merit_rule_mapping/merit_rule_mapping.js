

frappe.ui.form.on("Merit Rule Mapping", {
	refresh(frm) {


	},
	onload:function(frm){
        frm.set_query("admission_cycle", function() {
            return {
                filters: {
                    status: "Active"
                }
            };
        });
    },
});
