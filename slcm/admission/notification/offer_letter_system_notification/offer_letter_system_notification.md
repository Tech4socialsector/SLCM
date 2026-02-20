### Congratulations!

Dear **{{ doc.applicant_name or doc.applicant }}**,

We are pleased to inform you that an admission offer has been issued for the **{{ doc.program }}** program at our **{{ doc.campus }}** campus.

Please log in to the student portal to review your offer letter, fee details, and complete the acceptance process before the deadline of **{{ frappe.utils.formatdate(doc.payment_deadline) }}**.

[View Offer Letter](/app/applicant-offer-lett/{{ doc.name }})

Best regards,
Admission Team