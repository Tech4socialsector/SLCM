// ============================================================
// Client Script : Entrance Test Seat Allocation
// DocType       : Entrance Test Seat Allocation
// ============================================================

frappe.ui.form.on("Entrance Test Seat Allocation", {

    // ─── On form load ─────────────────────────────────────────
    refresh: function (frm) {
        frm.set_query("entrance_test_provider", function () {
            const preferences = (frm.doc.assigned_preferences || []).map(p => p.provider);
            return { filters: { name: ["in", preferences] } };
        });

        if (frm.doc.allocation_status === "Allocated") {
            frm.set_df_property("entrance_test_provider", "read_only", 1);
        }
    },

    // ─── Download Admit Card Button ────────────────────────────
    download_admit_card: function (frm) {

        // Guard: unsaved changes
        if (frm.is_dirty()) {
            frappe.msgprint({
                title: __("Unsaved Changes"),
                message: __("Please save the document before downloading the Admit Card."),
                indicator: "orange"
            });
            return;
        }

        // Guard: allocation status
        const allowed = ["Allocated", "Reallocated"];
        if (!allowed.includes(frm.doc.allocation_status)) {
            frappe.msgprint({
                title: __("Not Allowed"),
                message: __("Admit Card can only be downloaded when status is <b>Allocated</b> or <b>Reallocated</b>."),
                indicator: "red"
            });
            return;
        }

        // Show a simple loading alert (NOT frappe.show_progress — avoids stuck dialog)
        frappe.show_alert({ message: __("Generating Admit Card…"), indicator: "blue" }, 3);

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Entrance Test Seat Allocation",
                name: frm.doc.name
            },
            callback: function (r) {
                if (r.exc || !r.message) {
                    frappe.msgprint(__("Failed to fetch document. Please try again."));
                    return;
                }
                generate_admit_card_pdf(r.message, frm);
            }
        });
    },

    // ─── When provider is selected ─────────────────────────────
    entrance_test_provider: function (frm) {
        const provider = frm.doc.entrance_test_provider;

        if (!provider) {
            frm.set_value("center_name", "");
            frm.set_value("center_address", "");
            return;
        }

        const assigned_prefs = (frm.doc.assigned_preferences || []);
        const pref = assigned_prefs.find(p => p.provider === provider);

        if (!pref) {
            frappe.show_alert({ message: __("Please choose from your assigned preference centers."), indicator: "red" });
            frm.set_value("entrance_test_provider", "");
            return;
        }

        frm.set_value("center_name", pref.center_name || "");
        frm.set_value("center_address", pref.center_address || "");

        frappe.call({
            method: "slcm.admission.doctype.entrance_test_list.entrance_test_list.get_applicant_preferences",
            args: {
                applicant_id: frm.doc.applicant,
                entrance_test_list: frm.doc.entrance_test_list
            },
            callback: function (r) {
                if (!r.message) return;
                const pinfo = r.message.find(p => p.entrance_test_provider === provider);
                if (pinfo && pinfo.is_full) {
                    frappe.msgprint({
                        title: __("Center Full"),
                        message: __("<b>{0}</b> is currently full. Please choose another center.", [pinfo.center_name || provider]),
                        indicator: "orange"
                    });
                    frm.set_value("entrance_test_provider", "");
                }
            }
        });
    },

    // ─── Before Save — confirmation flow ──────────────────────
    before_save: function (frm) {
        if (frm.doc.entrance_test_provider && frm.doc.allocation_status === "Not Allocated") {
            frappe.validated = false;

            frappe.confirm(
                __("Confirm seat allocation at <b>{0}</b>? This action is permanent.",
                    [frm.doc.center_name || frm.doc.entrance_test_provider]),
                function () {
                    frappe.call({
                        method: "slcm.admission.doctype.entrance_test_list.entrance_test_list.confirm_applicant_preference",
                        args: {
                            allocation_name: frm.doc.name,
                            selected_provider: frm.doc.entrance_test_provider
                        },
                        freeze: true,
                        freeze_message: __("Finalizing your allocation..."),
                        callback: function (r) {
                            if (!r.exc && r.message) {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: __("Seat Successfully Allocated! Seat: <b>{0}</b>", [r.message.seat_number]),
                                    indicator: "green"
                                }, 5);
                            }
                        }
                    });
                }
            );
        }
    }
});


// ============================================================
//  generate_admit_card_pdf
//  Opens a new tab with a clean, professional admit card.
//  window.print() fires automatically → user saves as PDF.
// ============================================================
function generate_admit_card_pdf(doc, frm) {

    const esc  = (v) => frappe.utils.escape_html(String(v || ""));
    const val  = (v) => (v && String(v).trim() !== "") ? esc(v) : "—";

    const admit_no = doc.admit_card_number || ("AC-" + doc.name);

    let alloc_date = "—";
    if (doc.allocation_date) {
        try { alloc_date = frappe.datetime.str_to_user(doc.allocation_date); }
        catch (e) { alloc_date = doc.allocation_date; }
    }

    const issue_date = (() => {
        try { return frappe.datetime.str_to_user(frappe.datetime.nowdate()); }
        catch (e) { return new Date().toLocaleDateString("en-IN"); }
    })();

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Admit Card — ${esc(doc.candidate_name || doc.name)}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: "Segoe UI", Arial, sans-serif;
    background: #eef0f4;
    color: #1a1a2e;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }

  /* ── Print button bar ── */
  .print-bar {
    background: #1a237e;
    color: #fff;
    text-align: center;
    padding: 10px 16px;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
  }
  .print-btn {
    background: #ffd600;
    color: #1a237e;
    border: none;
    padding: 7px 22px;
    font-size: 13px;
    font-weight: 700;
    border-radius: 4px;
    cursor: pointer;
    letter-spacing: 0.3px;
  }
  .print-btn:hover { background: #ffea00; }

  /* ── Card ── */
  .page {
    width: 740px;
    margin: 20px auto;
    background: #fff;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 6px 28px rgba(0,0,0,0.15);
  }

  /* ── Top stripe ── */
  .stripe {
    height: 5px;
    background: linear-gradient(90deg, #1a237e 0%, #1565c0 40%, #c9a84c 70%, #1a237e 100%);
  }

  /* ── Header ── */
  .header {
    background: linear-gradient(135deg, #1a237e 0%, #1565c0 100%);
    padding: 22px 30px 18px;
    display: flex;
    align-items: center;
    gap: 18px;
    position: relative;
  }
  .header::after {
    content: "";
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, transparent, #c9a84c 40%, #c9a84c 60%, transparent);
    opacity: 0.7;
  }
  .logo {
    width: 62px; height: 62px;
    border-radius: 50%;
    border: 2px solid rgba(201,168,76,0.7);
    background: rgba(255,255,255,0.1);
    display: flex; align-items: center; justify-content: center;
    font-size: 26px;
    flex-shrink: 0;
  }
  .hdr-text { flex: 1; }
  .hdr-title {
    font-size: 18px; font-weight: 700;
    color: #fff; letter-spacing: 0.4px;
    text-transform: uppercase;
  }
  .hdr-sub {
    font-size: 11px; color: rgba(255,255,255,0.6);
    margin-top: 4px; letter-spacing: 0.8px;
    text-transform: uppercase;
  }
  .hdr-right { text-align: right; flex-shrink: 0; }
  .badge {
    display: inline-block;
    border: 1.5px solid rgba(201,168,76,0.8);
    color: #c9a84c;
    padding: 5px 14px;
    font-size: 11px; font-weight: 700;
    letter-spacing: 2px;
    border-radius: 3px;
    text-transform: uppercase;
  }
  .ref-no {
    font-size: 10px; color: rgba(255,255,255,0.45);
    margin-top: 6px; letter-spacing: 0.3px;
  }

  /* ── Confidential band ── */
  .conf {
    background: #b71c1c;
    text-align: center;
    font-size: 9.5px; font-weight: 700;
    letter-spacing: 4px;
    color: rgba(255,255,255,0.92);
    padding: 4px 0;
    text-transform: uppercase;
  }

  /* ── Candidate strip ── */
  .cand-strip {
    background: #0d1b3e;
    padding: 20px 30px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 30px;
  }
  
  /* ── Profile Photo Section ── */
  .photo-section {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .photo-frame {
    width: 120px;
    height: 140px;
    border: 2.5px solid #c9a84c;
    border-radius: 3px;
    overflow: hidden;
    background: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    position: relative;
  }
  .photo-frame img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    display: block;
  }
  .photo-placeholder {
    width: 100%;
    height: 100%;
    background: linear-gradient(135deg, #e8dfc4 0%, #f4f0e8 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 42px;
    color: #c9a84c;
  }
  .photo-label {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: #c9a84c;
    text-transform: uppercase;
    white-space: nowrap;
  }
  
  /* ── Candidate Info Section ── */
  .cand-info {
    flex: 1;
  }
  .cand-name-lbl {
    font-size: 9px; font-weight: 600;
    letter-spacing: 2px; color: #c9a84c;
    text-transform: uppercase; margin-bottom: 3px;
  }
  .cand-name {
    font-size: 22px; font-weight: 700;
    color: #fff; letter-spacing: 0.2px;
  }
  .cand-meta {
    display: flex; gap: 20px; margin-top: 6px;
  }
  .cand-meta-lbl {
    font-size: 9px; color: rgba(255,255,255,0.4);
    letter-spacing: 1px; text-transform: uppercase;
  }
  .cand-meta-val {
    font-size: 12px; color: rgba(255,255,255,0.82);
    font-weight: 600; margin-top: 1px;
    font-variant-numeric: tabular-nums;
  }
  
  /* ── Status Section ── */
  .status-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .status-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 5px 14px;
    background: #dcfce7; color: #166534;
    border: 1px solid #bbf7d0;
    border-radius: 100px;
    font-size: 11px; font-weight: 700;
    flex-shrink: 0;
  }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: #166534; }

  /* ── Body ── */
  .body {
    padding: 22px 30px 28px;
    position: relative;
  }
  /* watermark */
  .body::before {
    content: "ADMIT CARD";
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%) rotate(-35deg);
    font-size: 64px; font-weight: 900;
    color: rgba(26,35,126,0.04);
    white-space: nowrap; pointer-events: none;
    letter-spacing: 8px; text-transform: uppercase;
    user-select: none;
  }
  .body > * { position: relative; z-index: 1; }

  /* ── Section label ── */
  .sec {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 12px; margin-top: 20px;
  }
  .sec:first-child { margin-top: 0; }
  .sec-dot { width: 5px; height: 5px; border-radius: 50%; background: #c9a84c; flex-shrink: 0; }
  .sec-txt {
    font-size: 9px; font-weight: 700;
    letter-spacing: 2.5px; color: #1565c0;
    text-transform: uppercase; white-space: nowrap;
  }
  .sec-line { flex: 1; height: 1px; background: #e2d9c8; }

  /* ── Grid ── */
  .grid { display: grid; gap: 12px 24px; }
  .g2 { grid-template-columns: 1fr 1fr; }
  .g3 { grid-template-columns: 1fr 1fr 1fr; }
  .g4 { grid-template-columns: 1fr 1fr 1fr 1fr; }
  .full { grid-column: 1 / -1; }

  .lbl {
    font-size: 9px; font-weight: 600;
    letter-spacing: 1.5px; color: #8a96a6;
    text-transform: uppercase; margin-bottom: 3px;
  }
  .fld {
    font-size: 13px; font-weight: 600; color: #1a1a2e;
    line-height: 1.4;
  }

  /* ── Seat highlight ── */
  .seat-box {
    display: flex;
    border: 1.5px solid #1a237e;
    border-radius: 5px;
    overflow: hidden;
    margin-top: 4px;
  }
  .seat-left {
    background: #1a237e;
    padding: 18px 22px;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 4px; min-width: 130px;
  }
  .seat-num {
    font-size: 44px; font-weight: 900;
    color: #fff; line-height: 1;
    letter-spacing: 1px;
  }
  .seat-lbl {
    font-size: 8px; font-weight: 600;
    letter-spacing: 2px; color: #c9a84c;
    text-transform: uppercase;
  }
  .seat-right {
    flex: 1; padding: 16px 22px;
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 12px 20px; align-content: center;
    background: linear-gradient(135deg, #f4f0e8, #fff);
  }

  /* ── Instructions ── */
  .inst-box {
    background: #fffdf5;
    border: 1px solid #e8dfc4;
    border-left: 3px solid #c9a84c;
    border-radius: 3px;
    padding: 13px 16px;
    margin-top: 4px;
  }
  .inst-title {
    font-size: 9px; font-weight: 700;
    letter-spacing: 2px; color: #9a7a20;
    text-transform: uppercase; margin-bottom: 8px;
  }
  .inst-list { list-style: none; padding: 0; margin: 0; counter-reset: c; }
  .inst-list li {
    counter-increment: c;
    position: relative; padding: 2.5px 0 2.5px 18px;
    font-size: 11px; color: #4a5568; line-height: 1.55;
    border-bottom: 1px solid rgba(0,0,0,0.04);
  }
  .inst-list li:last-child { border-bottom: none; }
  .inst-list li::before {
    content: counter(c);
    position: absolute; left: 0; top: 3px;
    font-size: 9px; font-weight: 700;
    color: #1565c0; width: 14px;
  }

  /* ── Signature strip ── */
  .sig-strip {
    display: flex; justify-content: space-between;
    align-items: flex-end; gap: 16px;
    margin-top: 24px; padding-top: 14px;
    border-top: 1px dashed #ccc;
  }
  .sig-box { text-align: center; flex: 1; }
  .sig-space { height: 32px; }
  .sig-line { border-top: 1px solid #333; margin-top: 5px; }
  .sig-name {
    font-size: 8.5px; font-weight: 600;
    letter-spacing: 1px; color: #8a96a6;
    text-transform: uppercase; margin-top: 4px;
  }

  /* ── Footer ── */
  .footer {
    background: #1a237e;
    padding: 10px 30px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .footer-l {
    font-size: 9px; color: rgba(255,255,255,0.45);
    letter-spacing: 0.3px;
  }
  .footer-l strong { color: rgba(255,255,255,0.7); }
  .footer-r { font-size: 9px; color: #c9a84c; opacity: 0.75; }

  .bottom-stripe {
    height: 4px;
    background: linear-gradient(90deg, #c9a84c, #1565c0, #c9a84c);
  }

  /* ── Print ── */
  @media print {
    body { background: #fff; }
    .print-bar { display: none !important; }
    .page { width: 100%; margin: 0; border-radius: 0; box-shadow: none; }
  }
</style>
</head>
<body>

<!-- Print Bar -->
<div class="print-bar">
  <span>Your Admit Card is ready — </span>
  <button class="print-btn" onclick="window.print()">⬇ Download / Print PDF</button>
  <span style="font-size:12px;opacity:0.7;">Select <b>Save as PDF</b> in the dialog</span>
</div>

<div class="page">
  <div class="stripe"></div>

  <!-- Header -->
  <div class="header">
    <div class="logo">🎓</div>
    <div class="hdr-text">
      <div class="hdr-title">Entrance Examination</div>
      <div class="hdr-sub">Office of Admissions &nbsp;·&nbsp; Examination Cell</div>
    </div>
    <div class="hdr-right">
      <div class="badge">Admit Card</div>
      <div class="ref-no">Ref: ${val(admit_no)} &nbsp;|&nbsp; Issued: ${val(issue_date)}</div>
    </div>
  </div>

  <!-- Confidential -->
  <div class="conf">⬥ &nbsp; Confidential — For Candidate Use Only &nbsp; ⬥</div>

  <!-- Candidate Strip -->
  <div class="cand-strip">
    <!-- Profile Photo -->
    <div class="photo-section">
      <div class="photo-frame">
        ${doc.profile_image ? `<img src="${doc.profile_image}" alt="Candidate Photo">` : '<div class="photo-placeholder">📷</div>'}
      </div>
      <div class="photo-label">Photo</div>
    </div>
    
    <!-- Candidate Information -->
    <div class="cand-info">
      <div class="cand-name-lbl">Candidate Name</div>
      <div class="cand-name">${val(doc.candidate_name)}</div>
      <div class="cand-meta">
        <div>
          <div class="cand-meta-lbl">Application No.</div>
          <div class="cand-meta-val">${val(doc.applicant)}</div>
        </div>
        <div>
          <div class="cand-meta-lbl">Gender</div>
          <div class="cand-meta-val">${val(doc.gender)}</div>
        </div>
        <div>
          <div class="cand-meta-lbl">Category</div>
          <div class="cand-meta-val">${val(doc.reservation_category)}</div>
        </div>
      </div>
    </div>
    
    <!-- Status Badge -->
    <div class="status-section">
      <div class="status-badge"><div class="dot"></div>${val(doc.allocation_status)}</div>
    </div>
  </div>

  <!-- Body -->
  <div class="body">

    <!-- Academic Details -->
    <div class="sec"><div class="sec-dot"></div><div class="sec-txt">Academic Details</div><div class="sec-line"></div></div>
    <div class="grid g4">
      <div><div class="lbl">Academic Year</div><div class="fld">${val(doc.academic_year)}</div></div>
      <div><div class="lbl">Admission Cycle</div><div class="fld">${val(doc.admission_cycle)}</div></div>
      <div><div class="lbl">Program Level</div><div class="fld">${val(doc.program_level)}</div></div>
      <div><div class="lbl">Program</div><div class="fld">${val(doc.program)}</div></div>
    </div>

    <!-- Venue -->
    <div class="sec"><div class="sec-dot"></div><div class="sec-txt">Examination Venue</div><div class="sec-line"></div></div>
    <div class="grid g2">
      <div><div class="lbl">Test Provider</div><div class="fld">${val(doc.entrance_test_provider)}</div></div>
      <div><div class="lbl">Allocation Date</div><div class="fld">${val(alloc_date)}</div></div>
      <div><div class="lbl">Center Name</div><div class="fld">${val(doc.center_name)}</div></div>
      <div><div class="lbl">Campus</div><div class="fld">${val(doc.campus)}</div></div>
      <div class="full"><div class="lbl">Center Address</div><div class="fld">${val(doc.center_address)}</div></div>
    </div>

    <!-- Seat -->
    <div class="sec"><div class="sec-dot"></div><div class="sec-txt">Seat Allocation</div><div class="sec-line"></div></div>
    <div class="seat-box">
      <div class="seat-left">
        <div style="font-size:22px;">🪑</div>
        <div class="seat-num">${val(doc.seat_number)}</div>
        <div class="seat-lbl">Seat No.</div>
      </div>
      <div class="seat-right">
        <div><div class="lbl">Room Code</div><div class="fld">${val(doc.room_code)}</div></div>
        <div><div class="lbl">Room Name</div><div class="fld">${val(doc.room_name)}</div></div>
        <div><div class="lbl">Building</div><div class="fld">${val(doc.building)}</div></div>
        <div><div class="lbl">Floor</div><div class="fld">${val(doc.floor)}</div></div>
      </div>
    </div>

    <!-- Instructions -->
    <div class="sec" style="margin-top:18px;"><div class="sec-dot"></div><div class="sec-txt">Instructions to Candidate</div><div class="sec-line"></div></div>
    <div class="inst-box">
      <div class="inst-title">Read carefully before reporting to the examination center</div>
      <ul class="inst-list">
        <li>Carry this Admit Card along with a valid Government-issued Photo ID to the examination center.</li>
        <li>Report at least <strong>30 minutes before</strong> the scheduled start time. Late entry will not be permitted.</li>
        <li>Mobile phones, smart watches, calculators and Bluetooth devices are strictly prohibited inside the hall.</li>
        <li>Occupy only your <strong>exact allotted seat</strong>. Exchange of seats is not allowed.</li>
        <li>This card is non-transferable. Contact the Examination Cell for any discrepancies.</li>
      </ul>
    </div>

    <!-- Signatures -->
    <div class="sig-strip">
      <div class="sig-box"><div class="sig-space"></div><div class="sig-line"></div><div class="sig-name">Candidate's Signature</div></div>
      <div class="sig-box"><div class="sig-space"></div><div class="sig-line"></div><div class="sig-name">Invigilator's Signature</div></div>
      <div class="sig-box"><div class="sig-space"></div><div class="sig-line"></div><div class="sig-name">Controller of Examinations</div></div>
    </div>

  </div><!-- /body -->

  <!-- Footer -->
  <div class="footer">
    <div class="footer-l">Doc: <strong>${val(doc.name)}</strong> &nbsp;·&nbsp; Generated: <strong>${val(issue_date)}</strong> &nbsp;·&nbsp; System-generated. No physical signature required.</div>
    <div class="footer-r">${val(admit_no)}</div>
  </div>
  <div class="bottom-stripe"></div>

</div><!-- /page -->

<script>
  // Auto-open print dialog once fonts/layout are fully rendered
  window.addEventListener("load", function () {
    setTimeout(function () { window.print(); }, 900);
  });
</script>
</body>
</html>`;

    // ── Open popup ────────────────────────────────────────────
    const win = window.open("", "_blank", "width=900,height=1050,scrollbars=yes,resizable=yes");
    if (!win) {
        frappe.msgprint({
            title: __("Popup Blocked"),
            message: __("Please allow pop-ups for this site and try again."),
            indicator: "orange"
        });
        return;
    }

    win.document.open();
    win.document.write(html);
    win.document.close();

    // ── Silently mark admit card as generated ─────────────────
    if (!doc.admit_card_generated) {
        frappe.call({
            method: "frappe.client.set_value",
            args: {
                doctype: "Entrance Test Seat Allocation",
                name: doc.name,
                fieldname: { admit_card_generated: 1, admit_card_number: admit_no }
            },
            callback: function () { if (frm) frm.reload_doc(); }
        });
    }

    frappe.show_alert({
        message: __("Admit Card opened. Select <b>Save as PDF</b> in the print dialog."),
        indicator: "green"
    }, 6);
}