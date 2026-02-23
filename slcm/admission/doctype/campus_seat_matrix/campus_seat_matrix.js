frappe.ui.form.on("Campus Seat Matrix", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Fetch from Program Offering"), function () {
                frm.call({
                    doc: frm.doc,
                    method: "fetch_seats_from_offering",
                    callback: function (r) {
                        if (!r.exc) {
                            frm.refresh_field("category_seats");
                            frm.refresh_field("total_seats");
                        }
                    }
                });
            });
        }
    },
    admission_cycle: function (frm) {
        frm.trigger("set_queries");
    },
    campus: function (frm) {
        frm.trigger("set_queries");
    },
    set_queries: function (frm) {
        if (frm.doc.admission_cycle && frm.doc.campus) {
            frm.set_query("program", function () {
                return {
                    query: "slcm.admission.doctype.program_offering.program_offering.get_programs_for_matrix",
                    filters: {
                        admission_cycle: frm.doc.admission_cycle,
                        campus: frm.doc.campus
                    }
                };
            });
        }
    }
});
