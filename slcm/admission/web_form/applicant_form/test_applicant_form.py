import frappe
from frappe.tests.utils import FrappeTestCase
from slcm.admission.web_form.applicant_form.applicant_form import city_query, state_query

class TestApplicantForm(FrappeTestCase):
    def test_city_query(self):
        # 1. Test with dict filter (standard backend approach)
        frappe.form_dict = frappe._dict({})
        res1 = city_query(filters={"state": "TAMIL NADU"}, txt="CH")
        self.assertTrue(len(res1) > 0)

        # 2. Test with stringified JSON filter
        frappe.form_dict = frappe._dict({})
        res2 = city_query(filters='{"state": "TAMIL NADU"}', txt="CH")
        self.assertTrue(len(res2) > 0)

        # 3. Test with jQuery GET request encoding (the web form scenario)
        frappe.form_dict = frappe._dict({
            "filters[state]": "TAMIL NADU",
            "txt": "CH"
        })
        res3 = city_query(txt="CH")
        self.assertTrue(len(res3) > 0)

    def test_state_query(self):
        frappe.form_dict = frappe._dict({
            "filters[country]": "India"
        })
        res = state_query()
        self.assertTrue(len(res) > 0)
