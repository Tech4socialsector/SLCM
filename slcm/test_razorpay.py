import frappe
import razorpay

def test_razorpay_auth():
	try:
		settings = frappe.get_doc("Razorpay Settings")
		api_key = settings.api_key
		api_secret = settings.get_password("api_secret")
		
		print(f"Testing with Key: {api_key}")
		client = razorpay.Client(auth=(api_key, api_secret))
		
		# Try a simple API call
		try:
			payments = client.payment.all({'count': 1})
			print("Authentication successful!")
			print(f"Found {len(payments['items'])} payments.")
		except razorpay.errors.BadRequestError as e:
			print(f"Bad Request Error: {e}")
		except razorpay.errors.GatewayError as e:
			print(f"Gateway Error: {e}")
		except razorpay.errors.ServerError as e:
			print(f"Server Error: {e}")
		except Exception as e:
			print(f"Razorpay API Error: {e}")
			
	except Exception as e:
		print(f"Script Error: {e}")

if __name__ == "__main__":
	test_razorpay_auth()
