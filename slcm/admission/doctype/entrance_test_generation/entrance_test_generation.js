frappe.ui.form.on("Entrance Test Generation", {
    onload: function (frm) {
        frm.set_query("admission_cycle", function () {
            return {
                filters: {
                    "status": "Active"
                }
            };
        });
    },

    refresh: function (frm) {

        // Remove any previously added buttons with the same label (safety)
        frm.remove_custom_button("Generate Test List");

        // Show button only when:
        // 1. Document is Draft (not submitted)
        // 2. Status is Draft or In Progress
        // 3. Required fields are filled (basic validation)

        if (
            !frm.is_new() &&                                    // Check if document is saved
            frm.doc.docstatus === 0 &&                          // still draft / not submitted
            ["Draft", "In Progress"].includes(frm.doc.status || "Draft") &&
            frm.doc.academic_year &&
            frm.doc.campus &&
            frm.doc.admission_cycle
            // you can add more required checks if needed → && frm.doc.program_level
        ) {
            frm.add_custom_button(__("Generate Test List"), function () {

                // Optional: extra client-side confirmation / validation
                if (!frm.doc.program_level) {
                    frappe.throw("Please select Program Level before generating");
                    return;
                }

                frappe.confirm(
                    __(
                        "Are you sure you want to generate the Entrance Test list with the following configuration?<br><br>"
                        + "<b>Filters:</b><br>"
                        + "Academic Year: {0}<br>"
                        + "Campus: {1}<br>"
                        + "Cycle: {2}<br>"
                        + "Level: {3}",
                        [
                            frm.doc.academic_year,
                            frm.doc.campus,
                            frm.doc.admission_cycle,
                            frm.doc.program_level
                        ]
                    ),
                    () => {
                        // Start generation
                        frm.call({
                            method: "generate_test_list",
                            doc: frm.doc,
                            freeze: true,
                            freeze_message: __("Generating Entrance Test List... Please wait"),
                            callback: (r) => {
                                if (r.message) {
                                    const listName = r.message;
                                    const listUrl = `/app/entrance-test-list/${listName}`;

                                    // Inject keyframe styles once
                                    if (!document.getElementById("etg-toast-style")) {
                                        const style = document.createElement("style");
                                        style.id = "etg-toast-style";
                                        style.innerHTML = `
                                            @keyframes etgSlideDown {
                                                from { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                                                to   { opacity: 1; transform: translateX(-50%) translateY(0); }
                                            }
                                            @keyframes etgSlideUp {
                                                from { opacity: 1; transform: translateX(-50%) translateY(0); }
                                                to   { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                                            }
                                            #etg-top-toast {
                                                position: fixed;
                                                top: 20px;
                                                left: 50%;
                                                z-index: 99999;
                                                background: #ffffff;
                                                border: 1.5px solid #2da44e;
                                                border-left: 5px solid #2da44e;
                                                border-radius: 10px;
                                                padding: 14px 20px;
                                                min-width: 340px;
                                                max-width: 480px;
                                                box-shadow: 0 8px 30px rgba(45,164,78,0.18), 0 2px 8px rgba(0,0,0,0.10);
                                                display: flex;
                                                align-items: flex-start;
                                                gap: 12px;
                                                animation: etgSlideDown 0.35s cubic-bezier(.4,0,.2,1) forwards;
                                                font-family: inherit;
                                            }
                                            #etg-top-toast.hide {
                                                animation: etgSlideUp 0.35s cubic-bezier(.4,0,.2,1) forwards;
                                            }
                                            #etg-top-toast .etg-icon {
                                                flex-shrink: 0;
                                                width: 36px;
                                                height: 36px;
                                                background: #eafbee;
                                                border-radius: 50%;
                                                display: flex;
                                                align-items: center;
                                                justify-content: center;
                                                font-size: 18px;
                                            }
                                            #etg-top-toast .etg-title {
                                                font-weight: 700;
                                                font-size: 14px;
                                                color: #1a7f37;
                                                margin-bottom: 3px;
                                            }
                                            #etg-top-toast .etg-sub {
                                                font-size: 12.5px;
                                                color: #555;
                                                margin-bottom: 8px;
                                            }
                                            #etg-top-toast .etg-btn {
                                                display: inline-block;
                                                background: #2da44e;
                                                color: #fff;
                                                padding: 5px 14px;
                                                border-radius: 6px;
                                                font-size: 12px;
                                                font-weight: 600;
                                                text-decoration: none;
                                                transition: background 0.2s;
                                            }
                                            #etg-top-toast .etg-btn:hover { background: #218838; }
                                            #etg-top-toast .etg-close {
                                                margin-left: auto;
                                                flex-shrink: 0;
                                                cursor: pointer;
                                                color: #aaa;
                                                font-size: 18px;
                                                line-height: 1;
                                                padding: 0 4px;
                                                align-self: flex-start;
                                            }
                                            #etg-top-toast .etg-close:hover { color: #333; }
                                        `;
                                        document.head.appendChild(style);
                                    }

                                    // Remove any existing toast
                                    const existing = document.getElementById("etg-top-toast");
                                    if (existing) existing.remove();

                                    // Build the toast element
                                    const toast = document.createElement("div");
                                    toast.id = "etg-top-toast";
                                    toast.innerHTML = `
                                        <div class="etg-icon">✅</div>
                                        <div style="flex:1;">
                                            <div class="etg-title">Entrance Test List Generated!</div>
                                            <div class="etg-sub">The test list has been successfully created.</div>
                                            <a href="${listUrl}" class="etg-btn">View List → ${listName}</a>
                                        </div>
                                        <span class="etg-close" title="Dismiss">✕</span>
                                    `;
                                    document.body.appendChild(toast);

                                    // Close button
                                    const dismissToast = () => {
                                        toast.classList.add("hide");
                                        setTimeout(() => toast.remove(), 350);
                                    };
                                    toast.querySelector(".etg-close").addEventListener("click", dismissToast);

                                    // Auto-dismiss after 6 seconds
                                    setTimeout(dismissToast, 6000);

                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );


            }, __("Actions"))
                .addClass("btn-primary")
                .css({ "font-weight": "bold" });
        }

        // Remove and Add "View Entrance Test List" button when status is Completed or Allocation Done
        frm.remove_custom_button("View Entrance Test List");
        if (["Completed", "Allocation Done"].includes(frm.doc.status)) {
            frm.add_custom_button(__("View Entrance Test List"), function () {
                frappe.db.get_value("Entrance Test List", {
                    academic_year: frm.doc.academic_year,
                    campus: frm.doc.campus,
                    admission_cycle: frm.doc.admission_cycle,
                    program_level: frm.doc.program_level
                }, "name", (r) => {
                    if (r && r.name) {
                        frappe.set_route("Form", "Entrance Test List", r.name);
                    } else {
                        frappe.msgprint(__("Associated Entrance Test List not found."));
                    }
                });
            }, __("Actions"));
        }
    },

    // Optional: refresh button visibility when these fields change
    academic_year: function (frm) { frm.trigger("refresh"); },
    campus: function (frm) { frm.trigger("refresh"); },
    admission_cycle: function (frm) { frm.trigger("refresh"); },
    program_level: function (frm) { frm.trigger("refresh"); },
    status: function (frm) { frm.trigger("refresh"); }

});