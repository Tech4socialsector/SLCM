import pytest
import random
import datetime

# Global registry to store mocked docs (especially for Entrance Test Seat Allocation)
mock_doc_registry = {}

class MockRow:
    def __init__(self, **kwargs):
        self.status = "Selected"
        self.shortlist_status = "Shortlisted"
        self.__dict__.update(kwargs)
        
    def get(self, key, default=None):
        return getattr(self, key, default)
        
    def as_dict(self):
        return self.__dict__

class MockDoc:
    def __init__(self, doctype, name, **kwargs):
        self.doctype = doctype
        self.name = name
        self.status = "Selected"
        self.__dict__.update(kwargs)
        if doctype == "Entrance Test Seat Allocation":
            mock_doc_registry[name] = self

    def get(self, key, default=None):
        return getattr(self, key, default)

    def db_set(self, fieldname, value, *args, **kwargs):
        setattr(self, fieldname, value)

    def db_insert(self, *args, **kwargs):
        from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
        if hasattr(self, "name") and self.name:
            mock_doc_registry[self.name] = self

    def add_comment(self, *args, **kwargs):
        return None

    def __getattr__(self, name):

        if name in self.__dict__:
            return self.__dict__[name]
        if name in ("part_a_total_marks_scored", "part_b_total_marks_scored"):
            if name in self.__dict__:
                return self.__dict__[name]
            app_key = f"Applicant-{self.name}"
            from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
            if app_key in mock_doc_registry:
                prop = "et_part_a_total_marks_scored" if "part_a" in name else "et_part_b_total_marks_scored"
                if hasattr(mock_doc_registry[app_key], prop):
                    return getattr(mock_doc_registry[app_key], prop)
            return 100.0 if "part_a" in name else 40.0



        if name.endswith("_list"):
            self.__dict__[name] = []
            return self.__dict__[name]
        if name in ("waitlist_seats", "compartmentalized_waitlist_seats", "min_percentile", "priority", "seats", "shortlisting_target"):
            return 0
        if name in ("compartmentalized_category",):
            return ""
        if name in ("allocation_stage_multiplier",):
            return 1.0
        if "status" in name or name in ("result_status", "entrance_test_status", "shortlist_status"):
            return "Pass" if name == "result_status" else "Attended"
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def append(self, fieldname, row_dict):
        if not hasattr(self, fieldname):
            setattr(self, fieldname, [])
        lst = getattr(self, fieldname)
        row = MockRow(**row_dict)
        lst.append(row)
        return row
        
    def set(self, fieldname, value):
        setattr(self, fieldname, value)


def generate_candidate(applicant_id, part_a=0, part_b=0, dob="2000-01-01", 
                       vertical="General", is_karnataka=False, is_pwd=False, gender="Male"):
    """
    Generates a mock candidate dictionary suitable for merit lists.
    """
    traits = []
    if is_karnataka:
        traits.append("Karnataka")
    if is_pwd:
        traits.append("PWD")

    if gender == "Female":
        traits.append("Women")
    
    total = part_a + part_b
    row = MockRow(
        applicant_id=applicant_id,
        applicant=applicant_id,
        candidate_name=f"Candidate {applicant_id}",
        program="BA LLB",
        program_level="Undergraduate",
        et_part_a_total_marks_scored=part_a,
        nlsat_part_a_score=part_a,
        entrance_score=part_a,
        et_part_b_total_marks_scored=part_b,
        interview_score=part_b,
        nlsat_part_b_score=part_b,
        total_score=total,
        date_of_birth=dob,
        vertical_category=vertical,
        original_vertical_category=vertical,
        actual_category=vertical,
        allocation_type="",
        horizontal_categories=",".join(traits),
        original_horizontal_categories=",".join(traits),
        traits=traits,
        status="Selected"
    )
    
    # Ensure there is a corresponding Entrance Test Seat Allocation mock doc
    etsa = MockDoc("Entrance Test Seat Allocation", row.applicant_id)
    etsa.entrance_test_status = "Attended"
    etsa.result_status = "Pass"
    mock_doc_registry[row.applicant_id] = etsa
    mock_doc_registry[f"Applicant-{row.applicant_id}"] = row
    
    return row

def generate_bulk_candidates(count, start_id=1, score_range=(20, 100), vertical_distribution=None):
    """
    Generates a large list of candidates.
    vertical_distribution: dict of vertical to count (e.g. {"General": 500, "SC": 100})
    """
    candidates = []
    curr_id = start_id
    
    if not vertical_distribution:
        vertical_distribution = {"General": count}
        
    for v_cat, v_count in vertical_distribution.items():
        for _ in range(v_count):
            part_a = round(random.uniform(score_range[0], score_range[1]), 2)
            part_b = round(random.uniform(10, 50), 2)
            # Random DOB between 2000 and 2005
            year = random.randint(2000, 2005)
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            dob = f"{year}-{month:02d}-{day:02d}"
            
            c = generate_candidate(
                applicant_id=f"APP-2026-{curr_id:05d}",
                part_a=part_a,
                part_b=part_b,
                dob=dob,
                vertical=v_cat
            )
            candidates.append(c)
            curr_id += 1
            
    return candidates
