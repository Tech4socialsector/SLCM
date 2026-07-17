import pytest
import frappe

class MockPolicy:
    def __init__(self):
        self.shortlisting_multiplier = 5.0
        from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc
        self.categories = [
            MockDoc("Admission Category Row", "Gen", category_name="General", seats=49, shortlisting_target=245),
            MockDoc("Admission Category Row", "SC", category_name="SC", seats=18, shortlisting_target=90),
            MockDoc("Admission Category Row", "ST", category_name="ST", seats=9, shortlisting_target=45),
            MockDoc("Admission Category Row", "OBC", category_name="OBC-NCL", seats=32, shortlisting_target=160),
            MockDoc("Admission Category Row", "EWS", category_name="EWS", seats=12, shortlisting_target=60),
        ]
        self.compartmental_reservations = [
            MockDoc("Comp Row", "Kar", category_name="Karnataka", percentage=25.0)
        ]
        self.horizontal_reservations = [
            MockDoc("Horiz Row", "PWD", category_name="PWD", seats=6, shortlisting_target=30),
            MockDoc("Horiz Row", "Women", category_name="Women", seats=36, shortlisting_target=180)
        ]

    def get(self, key, default=None):
        return getattr(self, key, default)

original_get_doc = frappe.get_doc
def mock_get_doc(doctype, name=None, **kwargs):
    if doctype == "Programme Reservation Policy":
        return MockPolicy()
    if doctype in ("Merit List", "Entrance Test Seat Allocation"):
        from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, mock_doc_registry
        if name in mock_doc_registry:
            return mock_doc_registry[name]
        return MockDoc(doctype, name, **kwargs)
    return original_get_doc(doctype, name, **kwargs)

@pytest.fixture
def mock_policy():
    pass

@pytest.fixture(autouse=True)
def setup_frappe_mocks(monkeypatch):
    """
    Auto-applied fixture to mock frappe DB calls in merit_service and seat_allocation
    """
    monkeypatch.setattr(frappe, "get_doc", mock_get_doc)
    monkeypatch.setattr(frappe, "new_doc", lambda doctype: mock_get_doc(doctype, "New Doc"))
    
    original_get_value = frappe.db.get_value
    original_set_value = frappe.db.set_value
    original_get_all = frappe.db.get_all
    original_sql = frappe.db.sql

    def _mock_get_value(doctype, filters=None, fieldname=None, **kwargs):
        if doctype == "Programme Reservation Policy":
            return "MockPolicyName"
        return original_get_value(doctype, filters=filters, fieldname=fieldname, **kwargs)
        
    def _mock_set_value(doctype, name, fieldname, value=None, **kwargs):
        if doctype == "Entrance Test Seat Allocation":
            return None
        return original_set_value(doctype, name, fieldname, value, **kwargs)
        
    def _mock_get_all(doctype, **kwargs):
        if doctype == "Applicant Category":
            return []
        return original_get_all(doctype, **kwargs)
        
    def _mock_sql(*args, **kwargs):
        if args and "SELECT" in args[0] and "merit" not in args[0].lower():
            pass
        return original_sql(*args, **kwargs)
        
    def mock_get_applicant_categories(applicant_id):
        from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
        app = mock_doc_registry.get(f"Applicant-{applicant_id}")
        cats = []
        if app:
            if getattr(app, "original_vertical_category", None):
                cats.append(app.original_vertical_category)
            hc = getattr(app, "original_horizontal_categories", "")
            if hc:
                if isinstance(hc, str):
                    cats.extend([c.strip() for c in hc.split(",") if c.strip()])
                elif isinstance(hc, list):
                    cats.extend(hc)
        return cats or ["General"]

    monkeypatch.setattr("slcm.admission.doctype.seat_allocation.seat_allocation.get_applicant_categories", mock_get_applicant_categories)
    monkeypatch.setattr("slcm.admission.doctype.merit_generation.merit_service.get_applicant_categories", mock_get_applicant_categories)
    
    monkeypatch.setattr(frappe.db, "get_value", _mock_get_value)
    monkeypatch.setattr(frappe.db, "set_value", _mock_set_value)
    monkeypatch.setattr(frappe.db, "get_all", _mock_get_all)
    
    # Mock clear_cache
    if hasattr(frappe, "cache"):
        monkeypatch.setattr(frappe.cache(), "hdel", lambda *args, **kwargs: None)
        monkeypatch.setattr(frappe.cache(), "delete_value", lambda *args, **kwargs: None)
