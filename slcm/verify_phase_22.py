import frappe, os

def verify():
    ok = True

    # 1. Admission Stage Config fields
    meta = frappe.get_meta('Admission Stage Config')
    fnames = [f.fieldname for f in meta.fields]
    required = ['applicable_workflow','allow_application','is_editable',
                'start_date','end_date']
    for r in required:
        exists = r in fnames
        if not exists: ok = False
        print(f'  AdmStageConfig.{r}: {"OK" if exists else "MISSING"}')

    # 2. Program.intake_type
    meta2 = frappe.get_meta('Programme')
    exists = any(f.fieldname == 'intake_type' for f in meta2.fields)
    if not exists: ok = False
    print(f'  Program.intake_type: {"OK" if exists else "MISSING"}')

    # 3. Applicant.intake_type
    meta3 = frappe.get_meta('Applicant')
    exists = any(f.fieldname == 'intake_type' for f in meta3.fields)
    if not exists: ok = False
    print(f'  Applicant.intake_type: {"OK" if exists else "MISSING"}')

    # 4. stage_control.py
    # Fixed path for verification in the container/bench environment
    spath = '/home/joy-sathish/frappe/slcm/apps/slcm/slcm/admission/utils/stage_control.py'
    exists = os.path.exists(spath)
    if not exists: ok = False
    print(f'  stage_control.py: {"OK" if exists else "MISSING"}')

    # 5. Import test
    try:
        from slcm.admission.utils.stage_control import (
            can_apply, can_edit_application, get_portal_stage_list
        )
        print('  stage_control import: OK')
    except Exception as e:
        ok = False
        print(f'  stage_control import: FAIL — {e}')

    # 6. Active cycle stage data
    cycles = frappe.get_all('Admission Cycle',
        filters={'status':'Active'}, fields=['name','cycle_name'], limit=1)
    if cycles:
        doc = frappe.get_doc('Admission Cycle', cycles[0].name)
        print(f'  Active cycle: {cycles[0].cycle_name} ({len(doc.stages)} stages)')
        for s in sorted(doc.stages, key=lambda x: getattr(x,'sequence',0) or 0):
            wf = getattr(s,'applicable_workflow','NOT SET')
            aa = getattr(s,'allow_application','NOT SET')
            print(f'    [{s.stage_name}] workflow={wf} | allow_app={aa}')

    print()
    print('RESULT:', 'ALL PASS' if ok else 'SOME CHECKS FAILED — review above')

if __name__ == "__main__":
    verify()
