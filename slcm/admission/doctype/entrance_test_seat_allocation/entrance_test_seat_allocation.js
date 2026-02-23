frappe.ui.form.on("Entrance Test Seat Allocation", {

    // ─── On form load ────────────────────────────────────────────────────────
    refresh: function (frm) {
        // Filter the Entrance Test Provider link field to only show
        // providers that were assigned as preferences for THIS applicant
        frm.set_query("entrance_test_provider", function () {
            const preferences = (frm.doc.assigned_preferences || []).map(p => p.provider);
            return {
                filters: {
                    name: ["in", preferences]
                }
            };
        });

        // If already Allocated — lock the provider field
        if (frm.doc.allocation_status === "Allocated") {
            frm.set_df_property("entrance_test_provider", "read_only", 1);
        }
    },

    // ─── Download Admit Card Button ──────────────────────────────────────────
    download_admit_card: function (frm) {
        const url = frappe.urllib.get_full_url(
            `/api/method/frappe.utils.print_format.download_pdf?doctype=${encodeURIComponent(frm.doc.doctype)}&name=${encodeURIComponent(frm.doc.name)}&format=Entrance Test Admit Card&no_letterhead=1`
        );
        window.open(url, "_blank");
    },

    // ─── When provider is selected ───────────────────────────────────────────
    entrance_test_provider: function (frm) {
        const provider = frm.doc.entrance_test_provider;

        if (!provider) {
            frm.set_value("center_name", "");
            frm.set_value("center_address", "");
            return;
        }

        // Check if this provider is in the assigned preferences
        const assigned_prefs = (frm.doc.assigned_preferences || []);
        const pref = assigned_prefs.find(p => p.provider === provider);

        if (!pref) {
            frappe.show_alert({
                message: __("Please choose from your assigned preference centers."),
                indicator: "red"
            });
            frm.set_value("entrance_test_provider", "");
            return;
        }

        // Auto-fetch center details
        frm.set_value("center_name", pref.center_name || "");
        frm.set_value("center_address", pref.center_address || "");

        // Check capacity and warn if full
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
                        message: __(
                            "<b>{0}</b> is currently full. Please choose another center.",
                            [pinfo.center_name || provider]
                        ),
                        indicator: "orange"
                    });
                    frm.set_value("entrance_test_provider", "");
                }
            }
        });
    },

    // ─── Before Save — confirmation flow ─────────────────────────────
    before_save: function (frm) {
        if (
            frm.doc.entrance_test_provider &&
            frm.doc.allocation_status === "Not Allocated"
        ) {
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
                                // Toast notification as requested
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
// Client Script: Entrance Test Seat Allocation
// DocType      : Entrance Test Seat Allocation
// Purpose      : Handle "Download Admit Card" button click
//                — generates a professional admit card PDF
//                  using the browser's print-to-PDF API via
//                  a hidden iframe and an injected HTML page.
// ============================================================

frappe.ui.form.on("Entrance Test Seat Allocation", {

    // --------------------------------------------------------
    // Button click handler
    // --------------------------------------------------------
    download_admit_card: function (frm) {

        // Guard: must be saved first
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
                message: __("Admit Card can only be downloaded when Allocation Status is <b>Allocated</b> or <b>Reallocated</b>."),
                indicator: "red"
            });
            return;
        }

        // Show loading indicator
        frappe.show_progress(__("Generating Admit Card"), 30, 100, __("Please wait..."));

        // Fetch full doc values (handles linked field display values)
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Entrance Test Seat Allocation",
                name: frm.doc.name
            },
            callback: function (r) {
                frappe.hide_progress();
                if (r.exc || !r.message) {
                    frappe.msgprint(__("Failed to fetch document. Please try again."));
                    return;
                }
                generate_admit_card_pdf(r.message);
            }
        });
    }
});

// --------------------------------------------------------
// Core function: build HTML + trigger browser print
// --------------------------------------------------------
function generate_admit_card_pdf(doc) {

    // Helper — return value or a styled placeholder
    const val = (v) => (v && String(v).trim() !== "") ? frappe.utils.escape_html(String(v)) : '<span style="color:#bbb;">—</span>';

    // Generate admit card number if not set
    const admit_no = doc.admit_card_number || ("AC-" + doc.name);

    // Format allocation date
    let alloc_date = "—";
    if (doc.allocation_date) {
        try {
            alloc_date = frappe.datetime.str_to_user(doc.allocation_date);
        } catch (e) {
            alloc_date = doc.allocation_date;
        }
    }

    // Current date for "Date of Issue"
    const issue_date = frappe.datetime.nowdate()
        ? frappe.datetime.str_to_user(frappe.datetime.nowdate())
        : new Date().toLocaleDateString("en-IN");

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Admit Card - ${frappe.utils.escape_html(doc.candidate_name || doc.name)}</title>
<style>
  /* ── Reset ── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: "Segoe UI", Arial, sans-serif;
    background: #f0f2f5;
    color: #1a1a2e;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }

  /* ── Page wrapper ── */
  .page {
    width: 794px;
    min-height: 1123px;
    margin: 30px auto;
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 8px 40px rgba(0,0,0,0.18);
    position: relative;
  }

  /* ── Header ── */
  .header {
    background: linear-gradient(135deg, #1a237e 0%, #283593 40%, #1565c0 100%);
    padding: 28px 36px 22px;
    display: flex;
    align-items: center;
    gap: 22px;
    position: relative;
  }
  .header::after {
    content: "";
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, #ffd600, #ff6d00, #d50000, #aa00ff, #2962ff, #00b8d4);
  }
  .header .logo-circle {
    width: 70px; height: 70px;
    border-radius: 50%;
    background: rgba(255,255,255,0.15);
    border: 2.5px solid rgba(255,255,255,0.4);
    display: flex; align-items: center; justify-content: center;
    font-size: 28px; color: #fff;
    flex-shrink: 0;
  }
  .header .inst-info { flex: 1; }
  .header .inst-name {
    font-size: 22px; font-weight: 700;
    color: #fff; letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .header .inst-sub {
    font-size: 12px; color: rgba(255,255,255,0.75);
    margin-top: 4px; letter-spacing: 0.3px;
  }
  .header .card-title-box {
    text-align: right;
  }
  .header .card-title {
    font-size: 15px; font-weight: 700;
    color: #fff; letter-spacing: 1.5px;
    text-transform: uppercase;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.25);
    padding: 6px 14px;
    border-radius: 6px;
    display: inline-block;
  }
  .header .admit-no {
    font-size: 11px; color: rgba(255,255,255,0.65);
    margin-top: 6px;
    text-align: right;
  }

  /* ── CONFIDENTIAL ribbon ── */
  .ribbon {
    background: #e53935;
    color: #fff;
    text-align: center;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 3px;
    padding: 4px 0;
    text-transform: uppercase;
  }

  /* ── Body ── */
  .body { padding: 26px 36px 30px; }

  /* ── Section heading ── */
  .section-heading {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #1565c0;
    border-bottom: 2px solid #1565c0;
    padding-bottom: 5px;
    margin-bottom: 14px;
    margin-top: 22px;
  }
  .section-heading:first-child { margin-top: 0; }

  /* ── Info grid ── */
  .info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px 24px;
  }
  .info-grid.three-col {
    grid-template-columns: 1fr 1fr 1fr;
  }
  .info-item { display: flex; flex-direction: column; gap: 3px; }
  .info-label {
    font-size: 10px;
    font-weight: 600;
    color: #888;
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }
  .info-value {
    font-size: 13px;
    font-weight: 600;
    color: #1a1a2e;
    line-height: 1.4;
  }
  .info-value.large {
    font-size: 15px;
    font-weight: 700;
    color: #1565c0;
  }

  /* ── Highlight box (Seat Number) ── */
  .seat-highlight {
    background: linear-gradient(135deg, #e3f2fd, #bbdefb);
    border: 2px solid #1565c0;
    border-radius: 10px;
    padding: 16px 24px;
    margin-top: 18px;
    display: flex;
    align-items: center;
    gap: 24px;
  }
  .seat-highlight .seat-icon {
    font-size: 36px;
    flex-shrink: 0;
  }
  .seat-highlight .seat-details { flex: 1; }
  .seat-highlight .seat-number-val {
    font-size: 32px;
    font-weight: 800;
    color: #1a237e;
    letter-spacing: 2px;
    line-height: 1;
  }
  .seat-highlight .seat-label {
    font-size: 11px;
    font-weight: 600;
    color: #555;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-top: 4px;
  }
  .seat-highlight .room-info {
    text-align: right;
    flex-shrink: 0;
  }
  .seat-highlight .room-info .room-val {
    font-size: 16px;
    font-weight: 700;
    color: #1565c0;
  }
  .seat-highlight .room-info .room-label {
    font-size: 10px;
    color: #777;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  /* ── Instructions box ── */
  .instructions {
    background: #fffde7;
    border-left: 4px solid #f9a825;
    border-radius: 4px;
    padding: 14px 18px;
    margin-top: 22px;
  }
  .instructions .inst-title {
    font-size: 11px;
    font-weight: 700;
    color: #f57f17;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .instructions ol {
    padding-left: 18px;
    margin: 0;
  }
  .instructions ol li {
    font-size: 11.5px;
    color: #4a4a4a;
    margin-bottom: 5px;
    line-height: 1.5;
  }

  /* ── Signature strip ── */
  .sig-strip {
    display: flex;
    justify-content: space-between;
    margin-top: 36px;
    padding-top: 16px;
    border-top: 1.5px dashed #ccc;
  }
  .sig-box { text-align: center; }
  .sig-line {
    width: 140px;
    border-bottom: 1.5px solid #333;
    margin: 0 auto 6px;
    height: 38px;
  }
  .sig-label {
    font-size: 10px;
    font-weight: 600;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  /* ── Footer ── */
  .footer {
    background: #1a237e;
    color: rgba(255,255,255,0.7);
    text-align: center;
    font-size: 10px;
    padding: 10px 20px;
    letter-spacing: 0.4px;
  }
  .footer strong { color: #fff; }

  /* ── Status badge ── */
  .status-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: #e8f5e9;
    color: #2e7d32;
    border: 1px solid #a5d6a7;
  }

  /* ── Watermark ── */
  .watermark {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%) rotate(-40deg);
    font-size: 80px;
    font-weight: 900;
    color: rgba(21, 101, 192, 0.05);
    white-space: nowrap;
    pointer-events: none;
    z-index: 0;
    letter-spacing: 8px;
    text-transform: uppercase;
    user-select: none;
  }

  .body { position: relative; z-index: 1; }

  /* ── Print styles ── */
  @media print {
    body { background: #fff; }
    .page {
      margin: 0;
      border-radius: 0;
      box-shadow: none;
      width: 100%;
      min-height: 100vh;
    }
    .no-print { display: none !important; }
  }
</style>
</head>
<body>

<!-- Print button (hidden on print) -->
<div class="no-print" style="text-align:center; padding:16px 0 4px; font-family:Arial,sans-serif;">
  <button onclick="window.print()" style="
    background:#1565c0; color:#fff; border:none;
    padding:10px 28px; font-size:14px; font-weight:600;
    border-radius:6px; cursor:pointer; letter-spacing:0.5px;
    box-shadow:0 3px 8px rgba(21,101,192,0.4);
  ">⬇ Download / Print Admit Card</button>
  <p style="font-size:11px; color:#888; margin-top:8px;">
    Use <b>Save as PDF</b> in the print dialog to download.
  </p>
</div>

<div class="page">

  <!-- Watermark -->
  <div class="watermark">ADMIT CARD</div>

  <!-- Header -->
  <div class="header">
    <div class="logo-circle">🎓</div>
    <div class="inst-info">
      <div class="inst-name">Entrance Examination Admit Card</div>
      <div class="inst-sub">Office of Admissions &nbsp;|&nbsp; Examination Cell</div>
    </div>
    <div class="card-title-box">
      <div class="card-title">Admit Card</div>
      <div class="admit-no">No: <strong style="color:#fff;">${val(admit_no)}</strong></div>
    </div>
  </div>

  <!-- Ribbon -->
  <div class="ribbon">Confidential — For Candidate Use Only</div>

  <!-- Body -->
  <div class="body">

    <!-- Section 1: Academic Details -->
    <div class="section-heading">Academic Details</div>
    <div class="info-grid three-col">
      <div class="info-item">
        <div class="info-label">Academic Year</div>
        <div class="info-value">${val(doc.academic_year)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Admission Cycle</div>
        <div class="info-value">${val(doc.admission_cycle)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Campus</div>
        <div class="info-value">${val(doc.campus)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Program Level</div>
        <div class="info-value">${val(doc.program_level)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Program</div>
        <div class="info-value">${val(doc.program)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Allocation Status</div>
        <div class="info-value">
          <span class="status-badge">${val(doc.allocation_status)}</span>
        </div>
      </div>
    </div>

    <!-- Section 2: Candidate Details -->
    <div class="section-heading">Candidate Details</div>
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Candidate Name</div>
        <div class="info-value large">${val(doc.candidate_name)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Application Number</div>
        <div class="info-value large">${val(doc.applicant)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Reservation Category</div>
        <div class="info-value">${val(doc.reservation_category)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Gender</div>
        <div class="info-value">${val(doc.gender)}</div>
      </div>
    </div>

    <!-- Section 3: Test & Venue Details -->
    <div class="section-heading">Examination Venue Details</div>
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Entrance Test Provider</div>
        <div class="info-value">${val(doc.entrance_test_provider)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Allocation Date</div>
        <div class="info-value">${val(alloc_date)}</div>
      </div>
      <div class="info-item" style="grid-column:1/-1;">
        <div class="info-label">Center Name</div>
        <div class="info-value large">${val(doc.center_name)}</div>
      </div>
      <div class="info-item" style="grid-column:1/-1;">
        <div class="info-label">Center Address</div>
        <div class="info-value">${val(doc.center_address)}</div>
      </div>
    </div>

    <!-- Section 4: Seat Details (Highlighted) -->
    <div class="section-heading">Seat Allocation Details</div>
    <div class="seat-highlight">
      <div class="seat-icon">🪑</div>
      <div class="seat-details">
        <div class="seat-number-val">${val(doc.seat_number)}</div>
        <div class="seat-label">Seat Number</div>
      </div>
      <div class="room-info">
        <div class="room-label">Room Code</div>
        <div class="room-val">${val(doc.room_code)}</div>
        <div class="room-label" style="margin-top:8px;">Room Name</div>
        <div class="room-val">${val(doc.room_name)}</div>
      </div>
    </div>

    <div class="info-grid three-col" style="margin-top:12px;">
      <div class="info-item">
        <div class="info-label">Building</div>
        <div class="info-value">${val(doc.building)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Floor</div>
        <div class="info-value">${val(doc.floor)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Date of Issue</div>
        <div class="info-value">${val(issue_date)}</div>
      </div>
    </div>

    <!-- Instructions -->
    <div class="instructions">
      <div class="inst-title">⚠ Important Instructions for Candidates</div>
      <ol>
        <li>Carry this Admit Card (printed or digital) along with a valid Government-issued Photo ID proof to the examination center.</li>
        <li>Report to the exam center at least <strong>30 minutes before</strong> the scheduled start time. Late entry will NOT be permitted.</li>
        <li>Electronic devices (mobile phones, smart watches, calculators, etc.) are strictly prohibited inside the examination hall.</li>
        <li>Candidates must occupy the <strong>exact seat number</strong> allotted to them. Exchange of seats is not allowed under any circumstance.</li>
        <li>This Admit Card is non-transferable and valid only for the candidate named herein.</li>
        <li>Contact the Examination Cell immediately in case of any discrepancy in the details printed on this card.</li>
      </ol>
    </div>

    <!-- Signature strip -->
    <div class="sig-strip">
      <div class="sig-box">
        <div class="sig-line"></div>
        <div class="sig-label">Candidate's Signature</div>
      </div>
      <div class="sig-box">
        <div class="sig-line"></div>
        <div class="sig-label">Invigilator's Signature</div>
      </div>
      <div class="sig-box">
        <div class="sig-line"></div>
        <div class="sig-label">Controller of Examinations</div>
      </div>
    </div>

  </div><!-- /body -->

  <!-- Footer -->
  <div class="footer">
    <strong>Entrance Test Seat Allocation</strong> &nbsp;|&nbsp;
    Document Ref: ${val(doc.name)} &nbsp;|&nbsp;
    Generated on: ${val(issue_date)} &nbsp;|&nbsp;
    This is a system-generated document and does not require a physical signature.
  </div>

</div><!-- /page -->

<script>
  // Auto-trigger print for seamless PDF download experience
  window.onload = function() {
    // Small delay to ensure full render before print dialog
    setTimeout(function() {
      // Don't auto-print; let user click the button for better UX
    }, 500);
  };
</script>
</body>
</html>`;

    // --------------------------------------------------------
    // Open in new tab and trigger print dialog
    // --------------------------------------------------------
    const win = window.open("", "_blank", "width=900,height=1000,scrollbars=yes");
    if (!win) {
        frappe.msgprint({
            title: __("Popup Blocked"),
            message: __("Please allow pop-ups for this site and try again. Your browser has blocked the Admit Card window."),
            indicator: "orange"
        });
        return;
    }

    win.document.open();
    win.document.write(html);
    win.document.close();

    // Mark admit card as generated on the doc (silently)
    if (!frm.doc.admit_card_generated) {
        frappe.call({
            method: "frappe.client.set_value",
            args: {
                doctype: "Entrance Test Seat Allocation",
                name: frm.doc.name,
                fieldname: {
                    "admit_card_generated": 1,
                    "admit_card_number": admit_no
                }
            },
            callback: function () {
                frm.reload_doc();
            }
        });
    }

    frappe.show_alert({
        message: __("Admit Card opened in a new tab. Click <b>Download / Print Admit Card</b> in that tab."),
        indicator: "green"
    }, 6);
}