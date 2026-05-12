import frappe
from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level

m = generate_merit_for_level(
    'AY-June to December', 
    'National Law School of India University', 
    'Undergraduate', 
    processing_stage='Part A Ranking', 
    save=False
)
results = [(r.candidate_name, r.entrance_score, r.total_score, r.overall_rank) for r in m.merit_applicants[:10]]
for res in results:
    print(res)
