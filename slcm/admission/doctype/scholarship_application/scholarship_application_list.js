// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

/**
 * Robust Kanban/List Intercept for Scholarship Application
 * This script ensures that dragging a card to 'Rejected' in Kanban 
 * or changing status to 'Rejected' in List view prompts for a reason.
 */

(function() {
    // Prevent double-patching
    if (window._scholarship_list_patched) return;
    window._scholarship_list_patched = true;

    console.log("Scholarship Application List: Loading Interceptors...");

    const original_frappe_call = frappe.call;
    
    frappe.call = function(opts, args, callback) {
        // Standardize opts to handle both frappe.call({method: '...'}) and frappe.call('method', {...})
        let call_opts = opts;
        if (typeof opts === 'string') {
            call_opts = {
                method: opts,
                args: args,
                callback: callback
            };
        }

        if (!call_opts || !call_opts.method || !call_opts.args) {
            return original_frappe_call.apply(this, arguments);
        }

        // Detection logic
        const method = call_opts.method;
        const call_args = call_opts.args;
        
        const is_set_value = method === "frappe.client.set_value" && call_args.doctype === "Scholarship Application";
        const is_kanban_update = method.includes("kanban_board.update_order_for_single_card");

        // For Kanban, we check if the current route is Scholarship Application or if docname matches pattern
        const is_scholarship_kanban = is_kanban_update && (
            (cur_list && cur_list.doctype === "Scholarship Application") ||
            (frappe.get_route()[1] === "Scholarship Application") ||
            (call_args.docname && typeof call_args.docname === 'string' && call_args.docname.startsWith("SA-"))
        );

        // Check if value is being set to 'Rejected'
        const is_setting_rejected = 
            call_args.value === "Rejected" || 
            call_args.to_colname === "Rejected" ||
            (call_args.fieldname && call_args.fieldname.status === "Rejected") ||
            (typeof call_args.fieldname === 'object' && call_args.fieldname.status === "Rejected");

        const is_reject_call = (is_set_value || is_scholarship_kanban) && is_setting_rejected && !call_args._skip_intercept;

        if (is_reject_call) {
            console.log("Scholarship Application: Intercepting Rejection for", call_args.name || call_args.docname);
            const docname = call_args.name || call_args.docname;
            
            // Aggressively unfreeze the UI. Kanban view often freezes before the call.
            frappe.dom.unfreeze();
            setTimeout(() => frappe.dom.unfreeze(), 100);
            setTimeout(() => frappe.dom.unfreeze(), 500);

            const deferred = $.Deferred();

            // Show mandatory rejection reason dialog
            const d = new frappe.ui.Dialog({
                title: __("Enter Rejection Reason"),
                fields: [
                    {
                        label: __("Rejection Reason"),
                        fieldname: "rejection_reason",
                        fieldtype: "Small Text",
                        reqd: 1,
                        placeholder: __("Explain why this application is being rejected...")
                    }
                ],
                primary_action_label: __("Reject"),
                primary_action(values) {
                    d.hide();
                    
                    // Make the ACTUAL call using set_value
                    original_frappe_call({
                        method: "frappe.client.set_value",
                        args: {
                            doctype: "Scholarship Application",
                            name: docname,
                            fieldname: {
                                "status": "Rejected",
                                "rejection_reason": values.rejection_reason
                            },
                            _skip_intercept: true 
                        },
                        freeze: true,
                        freeze_message: __("Rejecting Application..."),
                        callback: function(r) {
                            if (!r.exc) {
                                frappe.show_alert({
                                    message: __("Application Rejected Successfully"),
                                    indicator: "red"
                                });
                                deferred.resolve(r);
                            } else {
                                deferred.reject(r);
                            }
                            if (cur_list) cur_list.refresh();
                        },
                        error: function(r) {
                            deferred.reject(r);
                            if (cur_list) cur_list.refresh();
                        }
                    });
                }
            });

            // On cancel/close, we must refresh to move the card back and resolve the promise
            d.onhide = () => {
                if (deferred.state() === "pending") {
                    deferred.reject();
                }
                // Final unfreeze to be safe
                frappe.dom.unfreeze();
                if (cur_list) cur_list.refresh();
            };

            d.show();
            
            // Ensure dialog is above freeze overlay if any remains
            if (d.$wrapper) {
                d.$wrapper.css("z-index", 2000);
                $(".modal-backdrop").css("z-index", 1990);
            }
            
            return deferred;
        }

        // Normal behavior
        return original_frappe_call.apply(this, arguments);
    };
})();

frappe.listview_settings["Scholarship Application"] = {
    get_indicator(doc) {
        const colors = {
            "Submitted": "blue",
            "Approved": "green",
            "Rejected": "red",
            "Revoked": "orange"
        };
        return [__(doc.status), colors[doc.status], "status,=," + doc.status];
    }
};
