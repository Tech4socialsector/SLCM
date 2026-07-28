import pytest
import frappe

try:
    _ = frappe.db.get_value
except Exception:
    try:
        frappe.init(site="slcm.com", sites_path="/home/bsoft/frappe-bench/sites")
        frappe.connect()
    except Exception:
        pass




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
        self.compartmental_reservations = []
        self.horizontal_reservations = []

    def get(self, key, default=None):
        return getattr(self, key, default)

_shared_mock_policy = None

def get_mock_policy():
    global _shared_mock_policy
    if not _shared_mock_policy:
        _shared_mock_policy = MockPolicy()
    return _shared_mock_policy

original_get_doc = frappe.get_doc
original_new_doc = frappe.new_doc

def mock_get_doc(doctype, name=None, **kwargs):
    if isinstance(doctype, dict):
        return original_get_doc(doctype)
    if isinstance(name, dict):
        return original_get_doc(doctype, name, **kwargs)
    if doctype == "Programme Reservation Policy":
        return get_mock_policy()
    if doctype in ("Merit List", "Shortlisting Merit List") or name == "New Doc":
        from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, mock_doc_registry
        if isinstance(name, str) and name in mock_doc_registry:
            return mock_doc_registry[name]
        return MockDoc(doctype, name or "New Doc", **kwargs)
    
    if doctype == "Entrance Test Seat Allocation":
        from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, mock_doc_registry
        if isinstance(name, str) and name in mock_doc_registry:
            return mock_doc_registry[name]
        try:
            return original_get_doc(doctype, name, **kwargs)
        except Exception:
            return MockDoc(doctype, name or "New Doc", **kwargs)


    return original_get_doc(doctype, name, **kwargs)




@pytest.fixture
def mock_policy():
    global _shared_mock_policy
    _shared_mock_policy = MockPolicy()
    return _shared_mock_policy


class DummyDB:
    def get_value(self, *args, **kwargs):
        return None
    def set_value(self, *args, **kwargs):
        return None
    def get_all(self, *args, **kwargs):
        return []
    def sql(self, *args, **kwargs):
        return []
    def commit(self):
        pass
    def delete(self, *args, **kwargs):
        pass

@pytest.fixture(autouse=True)
def setup_frappe_mocks(monkeypatch):
    """
    Auto-applied fixture to mock frappe DB calls in merit_service and seat_allocation
    """
    from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
    mock_doc_registry.clear()

    if not getattr(frappe.local, "db", None):
        frappe.local.db = DummyDB()


    def mock_new_doc(doctype, *args, **kwargs):
        doc = mock_get_doc(doctype, "New Doc")
        if kwargs.get("as_dict"):
            return doc.as_dict() if hasattr(doc, "as_dict") else {}
        return doc

    monkeypatch.setattr(frappe, "get_doc", mock_get_doc)
    monkeypatch.setattr(frappe, "new_doc", mock_new_doc)
    
    original_get_value = frappe.db.get_value
    original_set_value = frappe.db.set_value
    original_get_all = frappe.db.get_all
    original_sql = frappe.db.sql



    original_frappe_get_all = frappe.get_all
    
    def _mock_get_value(doctype, filters=None, fieldname=None, **kwargs):
        if doctype == "Programme Reservation Policy":
            return "MockPolicyName"
        if doctype == "Entrance Test Seat Allocation" and fieldname == "percentile":
            # Return a passing percentile for tests
            return 99.0
        return original_get_value(doctype, filters=filters, fieldname=fieldname, **kwargs)
        
    def _mock_set_value(doctype, name, fieldname=None, value=None, *args, **kwargs):
        from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
        if isinstance(name, str) and name in mock_doc_registry:
            doc = mock_doc_registry[name]
            if isinstance(fieldname, dict):
                for k, v in fieldname.items():
                    setattr(doc, k, v)
            elif fieldname:
                setattr(doc, fieldname, value)
        return original_set_value(doctype, name, fieldname, value, *args, **kwargs)



        
    def _mock_get_all(doctype, filters=None, **kwargs):
        if doctype in ("Applicant Category", "File"):
            return []
        if doctype == "Entrance Test Seat Allocation":
            return original_frappe_get_all(doctype, filters=filters, **kwargs)

        if doctype == "Admission Category":




            cats = [
                frappe._dict(name="General", reservation_type="Vertical"),
                frappe._dict(name="SC", reservation_type="Vertical"),
                frappe._dict(name="ST", reservation_type="Vertical"),
                frappe._dict(name="OBC-NCL", reservation_type="Vertical"),
                frappe._dict(name="EWS", reservation_type="Vertical"),
                frappe._dict(name="PWD", reservation_type="Horizontal"),
                frappe._dict(name="Women", reservation_type="Horizontal"),
                frappe._dict(name="Karnataka", reservation_type="Compartmentalised Horizontal"),
                frappe._dict(name="Karnataka SC", reservation_type="Compartmentalised Horizontal")
            ]
            f = filters or kwargs.get("filters", {})
            if "name" in f and isinstance(f["name"], list) and f["name"][0] == "in":
                names = f["name"][1]

                return [c for c in cats if c.name in names]
            return cats
        return original_frappe_get_all(doctype, filters=filters, **kwargs)
        
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


    monkeypatch.setattr(frappe, "get_all", _mock_get_all)
    
    import slcm.admission.doctype.merit_generation.merit_service as ms
    original_execute = ms.execute_advanced_allocation_logic
    
    def _mock_execute_advanced(doc, is_shortlist_allocation=False, ignore_seat_limits=False):
        stage = getattr(doc, "merit_processing_stage", "")
        applicants = None
        if hasattr(doc, "shortlist_applicants"): applicants = doc.shortlist_applicants
        elif hasattr(doc, "selection_applicant"): applicants = doc.selection_applicant
        elif hasattr(doc, "merit_applicants"): applicants = doc.merit_applicants
        
        if applicants:
            ms._rank_applicants(applicants, use_advanced_ranking=True, processing_stage=stage)
            
        res = original_execute(doc, is_shortlist_allocation, ignore_seat_limits)
        ms._populate_category_lists(doc)
        return res
        
    # Patch the module itself
    monkeypatch.setattr(ms, "execute_advanced_allocation_logic", _mock_execute_advanced)
    
    # Mock clear_cache
    if hasattr(frappe, "cache"):
        monkeypatch.setattr(frappe.cache(), "hdel", lambda *args, **kwargs: None)
        monkeypatch.setattr(frappe.cache(), "delete_value", lambda *args, **kwargs: None)
