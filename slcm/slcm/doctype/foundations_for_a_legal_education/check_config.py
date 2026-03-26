
import frappe
from slcm.slcm.doctype.foundations_for_a_legal_education.foundations_for_a_legal_education import create_razorpay_order

def debug_razorpay_config():
    print("--- DEBUG START ---")
    try:
        # Check Payment Gateway
        if not frappe.db.exists("Payment Gateway", "Razorpay"):
            print("ERROR: Payment Gateway 'Razorpay' does not exist.")
        else:
            print("SUCCESS: Payment Gateway 'Razorpay' exists.")
            
        # Check Razorpay Settings
        settings = frappe.get_doc("Razorpay Settings")
        if not settings.api_key:
            print("ERROR: Razorpay Settings API Key is missing.")
        else:
            print(f"SUCCESS: Razorpay Settings API Key is present: {settings.api_key[:4]}...")
            
    except Exception as e:
        print(f"EXCEPTION config check: {str(e)}")

def debug_create_order():
    print("--- ORDER CREATION DEBUG START ---")
    try:
        # Find a document
        docs = frappe.get_all("Foundations for a Legal Education", limit=1)
        if not docs:
            print("WARNING: No 'Foundations for a Legal Education' documents found. Creating a dummy one (not saving).")
            # We can't easily create a dummy doc without mandatory fields.
            # Let's try to create a temporary one if possible, or just fail.
            print("Cannot test create_order without a document.")
            return

        doc_name = docs[0].name
        print(f"Testing with document: {doc_name}")
        
        # Call the method
        try:
            res = create_razorpay_order(doc_name)
            print("SUCCESS: Order created successfully.")
            print(f"Response: {res}")
        except Exception as inner_e:
            print(f"ERROR: create_razorpay_order failed.")
            print(f"Exception: {inner_e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"EXCEPTION top level: {str(e)}")
    print("--- ORDER CREATION DEBUG END ---")
