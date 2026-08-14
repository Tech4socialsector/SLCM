import re

file_path = "/home/bsoft/frappe16-bench/apps/slcm/slcm/www/offer_letter/offer-letter-detail.html"

with open(file_path, "r") as f:
    content = f.read()

step_2_3_old = """                                <div style="display: flex; gap: 16px; align-items: flex-start; position: relative; z-index: 1;">
                                    <div style="width: 24px; height: 24px; border-radius: 50%; background: #fefce8; border: 1px solid #ca8a04; color: #ca8a04; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0;">2</div>
                                    <div style="font-size: 0.9rem; color: #475569; line-height: 1.5;">{{ _("The Confirmation Fee will be deducted from the Total Full Fee.") }}</div>
                                </div>
                                <div style="display: flex; gap: 16px; align-items: flex-start; position: relative; z-index: 1;">
                                    <div style="width: 24px; height: 24px; border-radius: 50%; background: #fefce8; border: 1px solid #ca8a04; color: #ca8a04; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0;">3</div>
                                    <div style="font-size: 0.9rem; color: #475569; line-height: 1.5;">{{ _("Pay the remaining balance (Total Payable) to complete your admission.") }}</div>
                                </div>"""

step_2_3_new = """                                ${has_conf_fee_deduction ? `
                                <div style="display: flex; gap: 16px; align-items: flex-start; position: relative; z-index: 1;">
                                    <div style="width: 24px; height: 24px; border-radius: 50%; background: #fefce8; border: 1px solid #ca8a04; color: #ca8a04; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0;">2</div>
                                    <div style="font-size: 0.9rem; color: #475569; line-height: 1.5;">{{ _("The Confirmation Fee will be deducted from the Total Full Fee.") }}</div>
                                </div>
                                <div style="display: flex; gap: 16px; align-items: flex-start; position: relative; z-index: 1;">
                                    <div style="width: 24px; height: 24px; border-radius: 50%; background: #fefce8; border: 1px solid #ca8a04; color: #ca8a04; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0;">3</div>
                                    <div style="font-size: 0.9rem; color: #475569; line-height: 1.5;">{{ _("Pay the remaining balance (Total Payable) to complete your admission.") }}</div>
                                </div>
                                ` : `
                                <div style="display: flex; gap: 16px; align-items: flex-start; position: relative; z-index: 1;">
                                    <div style="width: 24px; height: 24px; border-radius: 50%; background: #fefce8; border: 1px solid #ca8a04; color: #ca8a04; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0;">2</div>
                                    <div style="font-size: 0.9rem; color: #475569; line-height: 1.5;">{{ _("Pay the Full Fee to complete your admission.") }}</div>
                                </div>
                                `}"""

content = content.replace(step_2_3_old, step_2_3_new)

dates_old = """                        <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{{ _("Pay the confirmation fee") }}<br>{{ _("on or before this date") }}</div>
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 8px; border-left: 1px solid #f1f5f9; padding-left: 24px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #eff6ff; color: #3b82f6; display: flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                            <span class="material-symbols-outlined" style="font-size: 18px;">calendar_today</span>
                        </div>
                        <div style="color: #64748b; font-size: 0.9rem;">{{ _("Full Fee Payment Due Date") }}</div>
                        <div style="font-weight: 700; color: #1e293b; font-size: 1.05rem;">${offer.payment_deadline ? format_date_dd_mm_yyyy(offer.payment_deadline) : '-'}</div>
                        <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{{ _("Pay the remaining balance") }}<br>{{ _("on or before this date") }}</div>"""

dates_new = """                        ${offer.confirmation_fee_paid_on ? `
                            <div style="color: #16a34a; font-size: 0.85rem; margin-top: 4px; font-weight: 600;">{{ _("Paid on") }} ${format_date_dd_mm_yyyy(offer.confirmation_fee_paid_on)}</div>
                        ` : `
                            <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{{ _("Pay the confirmation fee") }}<br>{{ _("on or before this date") }}</div>
                        `}
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 8px; border-left: 1px solid #f1f5f9; padding-left: 24px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #eff6ff; color: #3b82f6; display: flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                            <span class="material-symbols-outlined" style="font-size: 18px;">calendar_today</span>
                        </div>
                        <div style="color: #64748b; font-size: 0.9rem;">{{ _("Full Fee Payment Due Date") }}</div>
                        <div style="font-weight: 700; color: #1e293b; font-size: 1.05rem;">${offer.payment_deadline ? format_date_dd_mm_yyyy(offer.payment_deadline) : '-'}</div>
                        ${offer.full_fee_paid_on ? `
                            <div style="color: #16a34a; font-size: 0.85rem; margin-top: 4px; font-weight: 600;">{{ _("Paid on") }} ${format_date_dd_mm_yyyy(offer.full_fee_paid_on)}</div>
                        ` : `
                            <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{{ _("Pay the remaining balance") }}<br>{{ _("on or before this date") }}</div>
                        `}"""

content = content.replace(dates_old, dates_new)

with open(file_path, "w") as f:
    f.write(content)
print("done")
