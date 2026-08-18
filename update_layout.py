import re

html_template = """
        let html = `
        <div style="max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; padding-bottom: 40px;">
            
            <!-- Top Bar -->
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
                <h2 style="margin: 0; font-weight: 700; font-size: 1.8rem; color: #1e293b;">{{ _("Offer Letter & Fee Details") }}</h2>
                <a href="/applicant" class="btn btn-default" style="display: inline-flex; align-items: center; gap: 8px; border-radius: 8px; border: 1px solid #e2e8f0; padding: 8px 16px; color: #64748b; font-weight: 500; text-decoration: none; background: white;">
                    <span class="material-symbols-outlined" style="font-size: 18px;">arrow_back</span>
                    {{ _("Back to Applications") }}
                </a>
            </div>

            <!-- Fee Details Block (Yellow Theme) -->
            <div class="ui-card" style="background: #fefce8; border: 1px solid #fde047; padding: 32px; border-radius: 12px; display: flex; flex-direction: column; gap: 24px;">
                <!-- Title -->
                <h4 style="margin: 0; display: flex; align-items: center; gap: 12px; color: #1e293b; font-weight: 700;">
                    <div style="background: #facc15; border-radius: 8px; padding: 8px; display: flex; align-items: center; justify-content: center;">
                        <span class="material-symbols-outlined" style="color: #422006;">account_balance_wallet</span>
                    </div>
                    {{ _("Fee Details") }}
                </h4>

                <div style="display: flex; flex-wrap: wrap; gap: 32px; align-items: stretch;">
                    <!-- Left Column: Summary Table -->
                    <div style="flex: 1 1 600px; background: white; border-radius: 12px; border: 1px solid #fef08a; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
                        <div style="font-weight: 600; margin-bottom: 16px; color: #334155; font-size: 0.95rem;">{{ _("Fee Summary") }}</div>
                        <table style="width: 100%; border-collapse: collapse; text-align: left;">
                            <thead>
                                <tr style="border-bottom: 1px solid #e2e8f0; color: #64748b; font-size: 0.85rem;">
                                    <th style="padding: 12px 12px 12px 0; font-weight: 600;">#</th>
                                    <th style="padding: 12px; font-weight: 600;">{{ _("Fee Component") }}</th>
                                    <th style="padding: 12px 0 12px 12px; font-weight: 600; text-align: right;">{{ _("Amount") }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${(() => {
                                    let active_fee_breakdown = fee_breakdown;
                                    if (offer.status === 'Accepted' && offer.needs_accommodation === 'No') {
                                        active_fee_breakdown = fee_breakdown.filter(f => !f.is_accommodation_fee);
                                    }

                                    const base_components = active_fee_breakdown.filter(f => !f.is_discount);
                                    const deductions = active_fee_breakdown.filter(f => f.is_discount);
                                    const total_full_fee = base_components.reduce((sum, f) => sum + f.amount, 0);
                                    const total_deductions = deductions.reduce((sum, f) => sum + Math.abs(f.amount), 0);
                                    const calculated_payable = total_full_fee - total_deductions;
                                    
                                    // Make sure confirmation fee is extracted correctly, even if it's implicitly part of the total
                                    let conf_amount = offer.confirmation_fee_amount || 0;
                                    let has_conf_fee_deduction = deductions.some(d => d.component.includes('Confirmation'));

                                    let index = 1;
                                    
                                    // First, show the Confirmation Fee row if it hasn't been paid yet (or show it anyway based on the design mockup)
                                    let html = '';
                                    
                                    // The design shows Confirmation Fee as item 1 in the full fee breakdown, even if it's an upfront fee.
                                    if (offer.status === 'Issued' || offer.status === 'Accepted') {
                                        html += `
                                        <tr style="border-bottom: 1px solid #f1f5f9; font-size: 0.95rem; color: #475569;">
                                            <td style="padding: 16px 16px 16px 0;">${index++}</td>
                                            <td style="padding: 16px;">
                                                <div style="display: flex; align-items: center; gap: 8px;">
                                                    {{ _("Confirmation Fee") }}
                                                    <span style="background: #fef08a; color: #b45309; padding: 2px 8px; border-radius: 99px; font-size: 0.75rem; font-weight: 600; border: 1px solid #fde047;">Due</span>
                                                </div>
                                            </td>
                                            <td style="padding: 16px 0 16px 16px; text-align: right; color: #1e293b;">
                                                ${format_currency(conf_amount, currency)}
                                            </td>
                                        </tr>`;
                                    }

                                    html += base_components.map(f => {
                                        let note = '';
                                        if (f.is_accommodation_fee) {
                                            note = (offer.status === 'Issued') ? ' (Optional)' : (offer.status === 'Accepted' ? ' (Opted)' : '');
                                        }
                                        return `
                                        <tr style="border-bottom: 1px solid #f1f5f9; font-size: 0.95rem; color: #475569;">
                                            <td style="padding: 16px 16px 16px 0;">${index++}</td>
                                            <td style="padding: 16px;">
                                                ${f.component}${note}
                                            </td>
                                            <td style="padding: 16px 0 16px 16px; text-align: right; color: #1e293b;">
                                                ${format_currency(f.amount, currency)}
                                            </td>
                                        </tr>`;
                                    }).join('');
                                    
                                    html += `
                                    </tbody>
                                </table>
                                
                                <div style="margin-top: 24px; border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0;">
                                    <div style="background: #f8fafc; padding: 16px 24px; display: flex; justify-content: space-between; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">
                                        <span>{{ _("Total Full Fee (Before Deduction)") }}</span>
                                        <span style="color: #0f172a;">${format_currency(total_full_fee, currency)}</span>
                                    </div>
                                    <div style="background: white; padding: 16px 24px; display: flex; justify-content: space-between; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #dc2626;">
                                        <span>{{ _("Less: Confirmation Fee (To be Deducted)") }}</span>
                                        <span>- ${format_currency(conf_amount, currency)}</span>
                                    </div>
                                    <div style="background: #f0fdf4; padding: 16px 24px; display: flex; justify-content: space-between; font-weight: 700; color: #1e293b;">
                                        <span>{{ _("Total Payable (After Deduction)") }}</span>
                                        <span style="color: #16a34a; font-size: 1.1rem;">${format_currency(Math.max(0, total_full_fee - conf_amount), currency)}</span>
                                    </div>
                                </div>`;
                                    
                                    return html;
                                })()}
                    </div>

                    <!-- Right Column: How it works -->
                    <div style="flex: 0 0 350px; background: #fef9c3; border-radius: 12px; padding: 24px; border: 1px solid #fde047; display: flex; flex-direction: column; justify-content: space-between;">
                        <div>
                            <div style="font-weight: 700; margin-bottom: 24px; color: #334155; display: flex; align-items: center; gap: 8px;">
                                <span class="material-symbols-outlined" style="color: #ca8a04;">info</span> {{ _("How it works") }}
                            </div>
                            
                            <div style="display: flex; flex-direction: column; gap: 20px; position: relative;">
                                <!-- Vertical timeline line -->
                                <div style="position: absolute; left: 11px; top: 24px; bottom: 24px; width: 1px; background: #facc15; z-index: 0;"></div>
                                
                                <div style="display: flex; gap: 16px; align-items: flex-start; position: relative; z-index: 1;">
                                    <div style="width: 24px; height: 24px; border-radius: 50%; background: #fefce8; border: 1px solid #ca8a04; color: #ca8a04; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0;">1</div>
                                    <div style="font-size: 0.9rem; color: #475569; line-height: 1.5;">{{ _("Pay the Confirmation Fee to secure your admission.") }}</div>
                                </div>
                                <div style="display: flex; gap: 16px; align-items: flex-start; position: relative; z-index: 1;">
                                    <div style="width: 24px; height: 24px; border-radius: 50%; background: #fefce8; border: 1px solid #ca8a04; color: #ca8a04; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0;">2</div>
                                    <div style="font-size: 0.9rem; color: #475569; line-height: 1.5;">{{ _("The Confirmation Fee will be deducted from the Total Full Fee.") }}</div>
                                </div>
                                <div style="display: flex; gap: 16px; align-items: flex-start; position: relative; z-index: 1;">
                                    <div style="width: 24px; height: 24px; border-radius: 50%; background: #fefce8; border: 1px solid #ca8a04; color: #ca8a04; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0;">3</div>
                                    <div style="font-size: 0.9rem; color: #475569; line-height: 1.5;">{{ _("Pay the remaining balance (Total Payable) to complete your admission.") }}</div>
                                </div>
                            </div>
                        </div>

                        <!-- Payment Actions -->
                        <div style="margin-top: 32px;">
                            ${offer.status === 'Issued' ? `
                                <div style="display: flex; gap: 12px; margin-bottom: 12px;">
                                    <button class="btn" style="flex: 1; border: 1px solid #ef4444; color: #ef4444; background: white; font-weight: 600; padding: 12px; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px;" onclick="handle_reject()">
                                        <span class="material-symbols-outlined" style="font-size: 18px;">close</span> {{ _("Reject") }}
                                    </button>
                                    <button class="btn" style="flex: 2; background: #facc15; color: #422006; font-weight: 700; border: none; padding: 12px; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px;" onclick="handle_primary_action()">
                                        <span class="material-symbols-outlined" style="font-size: 18px;">check_circle</span>
                                        {{ _("Accept Offer") }}
                                    </button>
                                </div>
                            ` : ''}

                            ${offer.status === 'Accepted' && online_payment_enabled ? `
                                <button class="btn btn-pay" style="width: 100%; background: #facc15; color: #422006; font-weight: 700; border: none; padding: 12px; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px;" onclick="handle_primary_action()" ${data.scholarship_application && data.scholarship_application.status === 'Submitted' ? 'disabled style="opacity: 0.6; cursor: not-allowed;"' : ''}>
                                    <span class="material-symbols-outlined" style="font-size: 18px;">account_balance_wallet</span>
                                    {{ _("Pay Confirmation Fee") }}
                                </button>
                                <div style="text-align: center; margin-top: 12px; color: #475569; font-size: 0.95rem;">
                                    Amount to Pay: <strong style="color: #1e293b;">${format_currency(offer.confirmation_fee_amount, currency)}</strong>
                                </div>
                            ` : ''}

                            ${offer.status === 'Confirmation Fee Paid' && online_payment_enabled ? `
                                <button class="btn btn-pay" style="width: 100%; background: #facc15; color: #422006; font-weight: 700; border: none; padding: 12px; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px;" onclick="handle_primary_action()">
                                    <span class="material-symbols-outlined" style="font-size: 18px;">account_balance_wallet</span>
                                    {{ _("Pay Full Fee") }}
                                </button>
                            ` : ''}

                            ${(data.receipts && data.receipts.length > 0) ? 
                                data.receipts.map(r => `
                                    <button class="btn btn-pay" style="width: 100%; margin-top: 12px; background: white; border: 1px solid #facc15; color: #422006; font-weight: 600; padding: 12px; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px;" onclick="window.open('/api/method/frappe.utils.print_format.download_pdf?doctype=Applicant+Payment+Receipt&name=${r.name}&format=Applicant+Payment+Receipt&no_letterhead=0&letterhead=No+Letterhead&settings=%7B%7D&_lang=en', '_blank')">
                                        <span class="material-symbols-outlined" style="font-size: 18px;">receipt</span> ${r.fee_type || 'Fee'} {{ _("Receipt") }}
                                    </button>
                                `).join('') 
                            : (['Payment Completed', 'Full Fee Paid'].includes(offer.status) || is_fee_paid || (applicant && ['Confirmation Fee Paid', 'Full Fee Paid'].includes(applicant.status)) ? `
                                <button class="btn btn-pay" style="width: 100%; margin-top: 12px; background: white; border: 1px solid #facc15; color: #422006; font-weight: 600; padding: 12px; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px;" onclick="handle_download_receipt()">
                                    <span class="material-symbols-outlined" style="font-size: 18px;">receipt</span> {{ _("Download Receipt") }}
                                </button>
                            ` : '')}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Status Block (Blue Theme) -->
            <div class="ui-card" style="background: #eff6ff; border: 1px solid #bfdbfe; padding: 32px; border-radius: 12px;">
                <!-- Title -->
                <h4 style="margin: 0; margin-bottom: 24px; display: flex; align-items: center; gap: 12px; color: #1e293b; font-weight: 700;">
                    <div style="background: #3b82f6; border-radius: 8px; padding: 8px; display: flex; align-items: center; justify-content: center;">
                        <span class="material-symbols-outlined" style="color: white;">stacked_line_chart</span>
                    </div>
                    {{ _("Status") }}
                </h4>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; background: white; border-radius: 12px; border: 1px solid #dbeafe; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
                    
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #dcfce7; color: #16a34a; display: flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                            <span class="material-symbols-outlined" style="font-size: 18px;">check_circle</span>
                        </div>
                        <div style="color: #64748b; font-size: 0.9rem;">{{ _("Offer Status") }}</div>
                        <div style="display: inline-flex; align-items: center; background: #dcfce7; color: #16a34a; padding: 4px 16px; border-radius: 99px; font-weight: 600; font-size: 0.85rem; width: fit-content; border: 1px solid #bbf7d0;">
                            ${display_status}
                        </div>
                        ${offer.accepted_on ? `
                            <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{{ _("Offer accepted on") }}<br>${format_date_dd_mm_yyyy(offer.accepted_on)}</div>
                        ` : ''}
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 8px; border-left: 1px solid #f1f5f9; padding-left: 24px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #eff6ff; color: #3b82f6; display: flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                            <span class="material-symbols-outlined" style="font-size: 18px;">calendar_today</span>
                        </div>
                        <div style="color: #64748b; font-size: 0.9rem;">{{ _("Confirmation Fee Due Date") }}</div>
                        <div style="font-weight: 700; color: #1e293b; font-size: 1.05rem;">${offer.confirmation_fee_deadline ? format_date_dd_mm_yyyy(offer.confirmation_fee_deadline) : '-'}</div>
                        <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{{ _("Pay the confirmation fee") }}<br>{{ _("on or before this date") }}</div>
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 8px; border-left: 1px solid #f1f5f9; padding-left: 24px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #eff6ff; color: #3b82f6; display: flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                            <span class="material-symbols-outlined" style="font-size: 18px;">calendar_today</span>
                        </div>
                        <div style="color: #64748b; font-size: 0.9rem;">{{ _("Full Fee Payment Due Date") }}</div>
                        <div style="font-weight: 700; color: #1e293b; font-size: 1.05rem;">${offer.payment_deadline ? format_date_dd_mm_yyyy(offer.payment_deadline) : '-'}</div>
                        <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{{ _("Pay the remaining balance") }}<br>{{ _("on or before this date") }}</div>
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 8px; border-left: 1px solid #f1f5f9; padding-left: 24px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #f8fafc; color: #64748b; display: flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                            <span class="material-symbols-outlined" style="font-size: 18px;">description</span>
                        </div>
                        <div style="color: #64748b; font-size: 0.9rem;">{{ _("Offer Issued On") }}</div>
                        <div style="font-weight: 700; color: #1e293b; font-size: 1.05rem;">${offer.issue_date ? format_date_dd_mm_yyyy(offer.issue_date) : '-'}</div>
                        <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{{ _("Offer issued by the university") }}</div>
                    </div>

                </div>
            </div>

            <!-- Offer Letter Block -->
            <div class="ui-card" style="padding: 32px; border-radius: 12px; border: 1px solid #e2e8f0; background: white;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 16px;">
                    <h4 style="margin: 0; display: flex; align-items: center; gap: 12px; color: #1e293b; font-weight: 700;">
                        <div style="background: #f1f5f9; border-radius: 8px; padding: 8px; display: flex; align-items: center; justify-content: center;">
                            <span class="material-symbols-outlined" style="color: #475569;">description</span>
                        </div>
                        {{ _("Offer Letter") }}
                    </h4>
                    
                    ${offer.status === 'Issued' || offer.status === 'Accepted' || offer.status === 'Confirmation Fee Paid' || offer.status === 'Full Fee Paid' ? `
                        <button class="btn btn-default" style="border: 1px solid #e2e8f0; background: white; color: #475569; display: flex; align-items: center; gap: 8px; font-weight: 600; padding: 8px 16px; border-radius: 8px;" onclick="window.open('/api/method/frappe.utils.print_format.download_pdf?doctype=Offer+Letter&name=${offer.name}&format=Offer+Letter&no_letterhead=0&letterhead=No+Letterhead&settings=%7B%7D&_lang=en', '_blank')">
                            <span class="material-symbols-outlined" style="font-size: 18px;">print</span>
                            {{ _("Print / Download PDF") }}
                        </button>
                    ` : ''}
                </div>

                <div class="letter-content" style="width: 100%; height: 800px; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
                    ${rendered_content ? `<iframe id="offer-letter-iframe" style="width: 100%; height: 100%; border: none;"></iframe>` : '<div class="text-center text-muted p-5"><span class="material-symbols-outlined" style="font-size: 48px; color: #cbd5e1; margin-bottom: 16px; display: block;">visibility_off</span><br>{{ _("No preview available") }}</div>'}
                </div>
            </div>
            
        </div>`;
"""

import sys

file_path = "/home/bsoft/frappe16-bench/apps/slcm/slcm/www/offer_letter/offer-letter-detail.html"

with open(file_path, "r") as f:
    content = f.read()

# We need to replace everything from `let html = \`` up to `wrapper.html(html);`
# Actually, the best way is to extract using a regex.

start_str = "let html = `"
end_str = "wrapper.html(html);"

start_idx = content.find(start_str)

# Find the end of the template literal, which is before `wrapper.html(html);`
end_idx = content.find(end_str, start_idx)

if start_idx == -1 or end_idx == -1:
    print("Could not find the HTML block to replace.")
    sys.exit(1)

# Ensure we don't accidentally remove wrapper.html(html);
new_content = content[:start_idx] + html_template + "        " + content[end_idx:]

with open(file_path, "w") as f:
    f.write(new_content)

print("HTML block replaced successfully.")
