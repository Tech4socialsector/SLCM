import frappe
import requests
import datetime
from slcm.api.razorpay_webhook import _fetch_settlement_recon

@frappe.whitelist()
def run_sync():
	"""
	Run this once to sync all past settlements from Razorpay.
	You can call this via API: 
	http://your-site/api/method/slcm.api.sync_settlements.run_sync
	Or run in bench console:
	frappe.get_doc("slcm.api.sync_settlements").run_sync()
	"""
	settings = frappe.get_single("Razorpay Settings")
	api_key = settings.api_key
	api_secret = settings.get_password("api_secret")

	if not api_key or not api_secret:
		return "API Keys are missing in Razorpay Settings."

	# Fetch recent settlements (max 100 for example, you can handle pagination if you have more)
	url = "https://api.razorpay.com/v1/settlements"
	resp = requests.get(url, auth=(api_key, api_secret), params={"count": 100})
	
	if resp.status_code != 200:
		return f"Error fetching settlements: {resp.text}"

	settlements = resp.json().get("items", [])
	total_updated = 0

	for st in settlements:
		settlement_id = st.get("id")
		utr = st.get("utr") or ""
		status = st.get("status") or "processed"
		created_at = st.get("created_at")
		
		settlement_date = None
		if created_at:
			try:
				settlement_date = datetime.datetime.utcfromtimestamp(int(created_at)).date()
			except Exception:
				pass
		
		recon_items = _fetch_settlement_recon(settlement_id, api_key, api_secret)
		updated = 0

		for item in recon_items:
			if item.get("type") not in ("payment", None):
				continue

			rzp_payment_id = item.get("razorpay_payment_id") or item.get("entity_id") or ""
			if not rzp_payment_id:
				continue

			log_name = frappe.db.get_value("FLE Payment Log", {"transaction_id": rzp_payment_id}, "name")
			if not log_name:
				continue

			fee_paise = item.get("fee") or 0
			tax_paise = item.get("tax") or 0
			credit_paise = item.get("credit") or item.get("amount") or 0

			frappe.db.set_value("FLE Payment Log", log_name, {
				"settlement_id": settlement_id,
				"settlement_utr": utr,
				"settlement_date": settlement_date,
				"settlement_status": status,
				"gateway_fees": round(fee_paise / 100, 2),
				"gateway_tax": round(tax_paise / 100, 2),
				"net_settled": round(credit_paise / 100, 2),
			})
			updated += 1
		
		frappe.logger().info(f"Sync: Settlement {settlement_id} updated {updated} records.")
		total_updated += updated

	return f"Successfully synchronized {len(settlements)} settlements and updated {total_updated} FLE Payment Log records."
