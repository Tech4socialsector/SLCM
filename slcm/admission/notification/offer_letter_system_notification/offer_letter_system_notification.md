{% if doc.status == 'Issued' %}
### Congratulations!

Dear **{{ doc.applicant_name or doc.applicant }}**,

We are pleased to inform you that an admission offer has been issued for the **{{ doc.program }}** programme at our **{{ doc.campus }}** campus.

Your offer letter for the **{{ doc.program }}** programme has been issued.

**Deadline to accept and pay:** {{ doc.payment_deadline }}
**Payable Amount:** ₹{{ doc.payable_amount }}

Please log in to your admission portal to view and accept the offer.

**Action Required:** Log in to your admission dashboard and navigate to the 'My Admission Offers' section to accept your offer.

[View Offer Letter](/app/applicant-offer-lett/{{ doc.name }})

{% elif doc.status == 'Accepted' %}
### Offer Accepted Successfully

Dear **{{ doc.applicant_name or doc.applicant }}**,

Congratulations! You have successfully accepted the offer for the **{{ doc.program }}** programme. 

Your application is moving forward, and we look forward to welcoming you.

**Next Steps:** Wait for further communication regarding enrolment or next stages.
<br>

{% elif doc.status == 'Payment Completed' %}
### Fee Payment Successful

Dear **{{ doc.applicant_name or doc.applicant }}**,

We have received your admission fee payment for the **{{ doc.program }}** programme.

Your admission process for this programme is now moving to the next stage.

**Next Steps:** You will receive further updates about your enrolment shortly.
<br>

{% elif doc.status == 'Rejected' %}
### Offer Rejected

Dear **{{ doc.applicant_name or doc.applicant }}**,

You have chosen to reject the offer for the **{{ doc.program }}** programme.

If you believe this was a mistake or you have questions, please reach out to our admission office.
<br>

{% elif doc.status == 'Expired' %}
### Offer Expired

Dear **{{ doc.applicant_name or doc.applicant }}**,

Your offer for the **{{ doc.program }}** programme has expired.

The payment and acceptance deadline of **{{ doc.payment_deadline }}** has passed. If you still wish to proceed, please contact the admission office immediately.
<br>

{% elif doc.status == 'Withdrawn' %}
### Offer Withdrawn

Dear **{{ doc.applicant_name or doc.applicant }}**,

Your offer for the **{{ doc.program }}** programme has been withdrawn.

If you need more information regarding this withdrawal, please contact the admission team.

{% endif %}

Best regards,
Admission Team