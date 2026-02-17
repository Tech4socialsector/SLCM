frappe.ui.form.on('Applicant', {
    refresh: function(frm) {
        // Set evaluation status as read-only
        frm.set_df_property('evaluation_status', 'read_only', 1);
        frm.set_df_property('rejected_reason', 'read_only', 1);
        
        // Add styling for eligibility status
        if (frm.doc.evaluation_status) {
            let color = frm.doc.evaluation_status === 'Eligible' ? 'green' : 'red';
            frm.get_field('evaluation_status').$wrapper.find('.control-value').css('color', color);
        }
    },

    // Trigger eligibility check on field changes
    program: function(frm) {
        check_eligibility(frm);
    },
    
    campus: function(frm) {
        check_eligibility(frm);
    },
    
    admission_cycle: function(frm) {
        check_eligibility(frm);
    },
    
    academic_year: function(frm) {
        check_eligibility(frm);
    },
    
    hsc_group: function(frm) {
        check_eligibility(frm);
    },
    
    hsc_percentage: function(frm) {
        check_eligibility(frm);
    },
    
    hsc_score: function(frm) {
        check_eligibility(frm);
    },
    
    ug_program: function(frm) {
        check_eligibility(frm);
    },
    
    ug_cgpa: function(frm) {
        check_eligibility(frm);
    },
    
    pg_program: function(frm) {
        check_eligibility(frm);
    },
    
    pg_cgpa: function(frm) {
        check_eligibility(frm);
    },
    
    before_submit: function(frm) {
        if (frm.doc.evaluation_status === 'Ineligible') {
            frappe.msgprint({
                title: __('Submission Not Allowed'),
                message: __('You are not eligible for the selected program.'),
                indicator: 'red'
            });
            frappe.validated = false;
            return false;
        }
    }
});

// Child table events
frappe.ui.form.on('Applicant Category', {
    category: function(frm, cdt, cdn) {
        check_eligibility(frm);
    },
    
    categories_remove: function(frm) {
        check_eligibility(frm);
    },
    
    categories_add: function(frm) {
        check_eligibility(frm);
    }
});

function check_eligibility(frm) {
    // Debounce the eligibility check
    if (frm.eligibility_timeout) {
        clearTimeout(frm.eligibility_timeout);
    }
    
    frm.eligibility_timeout = setTimeout(function() {
        if (!frm.doc.program || !frm.doc.campus || !frm.doc.admission_cycle || !frm.doc.academic_year) {
            frm.set_value('evaluation_status', '');
            frm.set_value('rejected_reason', '');
            return;
        }
        
        // Show loading indicator
        frm.set_value('evaluation_status', 'Checking...');
        
        frappe.call({
            method: 'slcm.admission.doctype.applicant.applicant.check_eligibility_on_change',
            args: {
                doc: frm.doc
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value('evaluation_status', r.message.evaluation_status);
                    frm.set_value('rejected_reason', r.message.rejected_reason);
                    
                    // Show message if ineligible
                    if (r.message.evaluation_status === 'Ineligible' && r.message.rejected_reason) {
                        frappe.show_alert({
                            message: __('Eligibility Check: ') + r.message.rejected_reason,
                            indicator: 'red'
                        });
                    } else if (r.message.evaluation_status === 'Eligible') {
                        frappe.show_alert({
                            message: __('You are eligible for this program'),
                            indicator: 'green'
                        });
                    }
                    
                    // Update field styling
                    let color = r.message.evaluation_status === 'Eligible' ? 'green' : 'red';
                    frm.get_field('evaluation_status').$wrapper.find('.control-value').css('color', color);
                }
            },
            error: function(r) {
                frm.set_value('evaluation_status', '');
                frm.set_value('rejected_reason', '');
                console.error('Eligibility check error:', r);
            }
        });
    }, 500); // 500ms delay
}
