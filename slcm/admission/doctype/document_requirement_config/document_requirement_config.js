frappe.ui.form.on("Document Requirement Config", {
    refresh: function(frm) {
        if (!frm.is_new()) {
            const count = (frm.doc.document_requirements || []).length;
            const mandatory = (frm.doc.document_requirements || []).filter(d => d.is_mandatory).length;
            frm.dashboard.set_headline(
                `<span style="color:#444">${count} document(s) defined — ${mandatory} mandatory</span>`
            );
            frm.add_custom_button("Preview Requirements", function() {
                const docs = frm.doc.document_requirements || [];
                let html = "<table style='width:100%;font-size:13px;border-collapse:collapse'>";
                html += "<tr style='background:#f0f0f0'><th style='padding:6px;text-align:left'>Document</th><th>Formats</th><th>Max Size</th><th>Mandatory</th><th>Verify</th></tr>";
                docs.forEach(d => {
                    html += `<tr style='border-bottom:1px solid #eee'>
                        <td style='padding:6px'><b>${d.document_name}</b><br><small>${d.help_text || ""}</small></td>
                        <td style='padding:6px'>${d.allowed_formats || "Any"}</td>
                        <td style='padding:6px'>${d.max_size_mb ? d.max_size_mb + " MB" : "—"}</td>
                        <td style='padding:6px;text-align:center'>${d.is_mandatory ? "✅" : "—"}</td>
                        <td style='padding:6px;text-align:center'>${d.verification_required ? "🔍" : "—"}</td>
                    </tr>`;
                });
                html += "</table>";
                frappe.msgprint({title: "Document Requirements Preview", message: html, wide: true});
            });
        }
        if (frm.doc.quota_category === "All") {
            frm.dashboard.add_comment("This config applies to ALL categories. Category-specific configs override this.", "blue", true);
        }
    }
});
