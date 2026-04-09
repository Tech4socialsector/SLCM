import frappe
from slcm.admission.doctype.applicant_payment_receipt.applicant_payment_receipt import ApplicantPaymentReceipt

def run():
    print("Starting Receipt PDF Pre-generation...")
    
    # Fetch all submitted receipts that don't have a PDF yet
    receipts = frappe.get_all("Applicant Payment Receipt", 
                              filters={"docstatus": 1, "receipt_pdf": ["is", "not set"]},
                              fields=["name"])
    
    total = len(receipts)
    print(f"Found {total} receipts to process.")
    
    for i, entry in enumerate(receipts):
        try:
            doc = frappe.get_doc("Applicant Payment Receipt", entry.name)
            doc.generate_and_attach_pdf()
            
            if (i + 1) % 10 == 0 or i == total - 1:
                print(f"Processed {i + 1} / {total} receipts...")
                frappe.db.commit() # Commit in batches
                
        except Exception as e:
            print(f"Failed to process {entry.name}: {str(e)}")
            
    print("Finished successfully.")

if __name__ == "__main__":
    run()
