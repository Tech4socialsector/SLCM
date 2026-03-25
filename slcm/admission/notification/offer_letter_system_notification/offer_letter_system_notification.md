{% if doc.offer_status == 'Issued' %}
### Congratulations!

Dear **{{ doc.applicant_name or doc.applicant }}**,

We are pleased to inform you that an admission offer has been issued for the **{{ doc.program }}** program at our **{{ doc.campus }}** campus.

Please log in to the student portal to review your offer letter, fee details, and complete the acceptance process before the deadline of **{{ frappe.utils.formatdate(doc.payment_deadline) }}**.

[View Offer Letter](/app/applicant-offer-lett/{{ doc.name }})

{% elif doc.offer_status == 'Accepted' %}
### Offer Accepted Successfully

Dear **{{ doc.applicant_name or doc.applicant }}**,

Thank you for accepting the admission offer for **{{ doc.program }}**. 

Your fee assignment has been generated. Please proceed to the payment section to complete your admission.

{% elif doc.offer_status == 'Payment Completed' %}
### Fee Payment Successful

Dear **{{ doc.applicant_name or doc.applicant }}**,

We have successfully received your fee payment for the **{{ doc.program }}** program. 

Congratulations! Your admission is now confirmed. You can download your payment receipt from the portal.

{% elif doc.offer_status == 'Rejected' %}
### Offer Rejected

Dear **{{ doc.applicant_name or doc.applicant }}**,

We acknowledge that you have declined the admission offer for **{{ doc.program }}**. 

If this was a mistake, please contact the admission office immediately.

{% elif doc.offer_status == 'Expired' %}
### Offer Expired

Dear **{{ doc.applicant_name or doc.applicant }}**,

We regret to inform you that your admission offer for **{{ doc.program }}** has expired as the payment deadline has passed.

{% elif doc.offer_status == 'Withdrawn' %}
### Offer Withdrawn

Dear **{{ doc.applicant_name or doc.applicant }}**,

Please be informed that your admission offer for **{{ doc.program }}** has been withdrawn by the administration.

{% endif %}

Best regards,
Admission Team