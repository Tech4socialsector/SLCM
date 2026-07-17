import json, frappe

frappe.init(site='slcm.local', sites_path='/home/nishanth/SLCM_V16/sites')
frappe.connect()

NOTE = (
    '<p style="color:#64748b;font-size:13px;">'
    'All master records defined here are the foundation for every SLCM module &mdash; '
    'Admissions, Enrollment, Examination, Fees, and Portal. '
    'Ensure Academic Structure and Grading Schemas are fully configured '
    'before any student transactions begin.'
    '</p>'
)

def hdr(code, text):
    return f'<span class="h4">{code} {text}</span>'

content = [
    {"id":"mst_p1",       "type":"paragraph", "data":{"text": NOTE,                                          "col":12}},
    {"id":"mst_sp0",      "type":"spacer",    "data":{"col":12}},
    {"id":"mst_h1",       "type":"paragraph", "data":{"text": hdr("&#127979;","Academic Structure"),          "col":12}},
    {"id":"mst_sc_dept",  "type":"shortcut",  "data":{"shortcut_name":"Department",    "col":3}},
    {"id":"mst_sc_prog",  "type":"shortcut",  "data":{"shortcut_name":"Programme",       "col":3}},
    {"id":"mst_sc_crs",   "type":"shortcut",  "data":{"shortcut_name":"Course",        "col":3}},
    {"id":"mst_sc_cm",    "type":"shortcut",  "data":{"shortcut_name":"Course Master", "col":3}},
    {"id":"mst_sp1",      "type":"spacer",    "data":{"col":12}},
    {"id":"mst_h2",       "type":"paragraph", "data":{"text": hdr("&#128218;","Curriculum &amp; Calendar"),   "col":12}},
    {"id":"mst_sc_curr",  "type":"shortcut",  "data":{"shortcut_name":"Curriculum",        "col":3}},
    {"id":"mst_sc_ay",    "type":"shortcut",  "data":{"shortcut_name":"Academic Year",     "col":3}},
    {"id":"mst_sc_at",    "type":"shortcut",  "data":{"shortcut_name":"Academic Term",     "col":3}},
    {"id":"mst_sc_ah",    "type":"shortcut",  "data":{"shortcut_name":"Academic Holiday",  "col":3}},
    {"id":"mst_sp2",      "type":"spacer",    "data":{"col":12}},
    {"id":"mst_h3",       "type":"paragraph", "data":{"text": hdr("&#128101;","People &amp; Groups"),         "col":12}},
    {"id":"mst_sc_fac",   "type":"shortcut",  "data":{"shortcut_name":"Faculty",           "col":4}},
    {"id":"mst_sc_gen",   "type":"shortcut",  "data":{"shortcut_name":"Gender",            "col":4}},
    {"id":"mst_sc_skill", "type":"shortcut",  "data":{"shortcut_name":"Skill",             "col":4}},
    {"id":"mst_sc_scat",  "type":"shortcut",  "data":{"shortcut_name":"Student Category",  "col":4}},
    {"id":"mst_sc_sm",    "type":"shortcut",  "data":{"shortcut_name":"Student Master",    "col":4}},
    {"id":"mst_sp3",      "type":"spacer",    "data":{"col":12}},
    {"id":"mst_h4",       "type":"paragraph", "data":{"text": hdr("&#128221;","Assessment &amp; Grading"),    "col":12}},
    {"id":"mst_sc_ec",    "type":"shortcut",  "data":{"shortcut_name":"Exam Component",         "col":4}},
    {"id":"mst_sc_eat",   "type":"shortcut",  "data":{"shortcut_name":"Exam Assessment Type",   "col":4}},
    {"id":"mst_sc_es",    "type":"shortcut",  "data":{"shortcut_name":"Evaluation Schema",      "col":4}},
    {"id":"mst_sc_gs",    "type":"shortcut",  "data":{"shortcut_name":"Grading Schema",         "col":4}},
    {"id":"mst_sc_csa",   "type":"shortcut",  "data":{"shortcut_name":"Course Schema Assignment","col":4}},
    {"id":"mst_sc_cgpa",  "type":"shortcut",  "data":{"shortcut_name":"CGPA Percentage Scale",  "col":4}},
    {"id":"mst_sp4",      "type":"spacer",    "data":{"col":12}},
    {"id":"mst_h5",       "type":"paragraph", "data":{"text": hdr("&#9881;","Configuration &amp; Settings"),  "col":12}},
    {"id":"mst_sc_ams",   "type":"shortcut",  "data":{"shortcut_name":"Academic Management System","col":4}},
    {"id":"mst_sc_atts",  "type":"shortcut",  "data":{"shortcut_name":"Attendance Settings",       "col":4}},
    {"id":"mst_sc_cond",  "type":"shortcut",  "data":{"shortcut_name":"Condonation Reason",        "col":4}},
    {"id":"mst_sc_exs",   "type":"shortcut",  "data":{"shortcut_name":"Examination Settings",      "col":4}},
    {"id":"mst_sc_prs",   "type":"shortcut",  "data":{"shortcut_name":"Publish Result Setting",    "col":4}},
    {"id":"mst_sc_sps",   "type":"shortcut",  "data":{"shortcut_name":"Student Portal Settings",   "col":4}},
    {"id":"mst_sc_ars",   "type":"shortcut",  "data":{"shortcut_name":"Access Result Settings",    "col":4}},
    {"id":"mst_sc_hs",    "type":"shortcut",  "data":{"shortcut_name":"Hostel Settings",           "col":4}},
    {"id":"mst_sc_ts",    "type":"shortcut",  "data":{"shortcut_name":"Transcript Settings",       "col":4}},
    {"id":"mst_sc_ads",   "type":"shortcut",  "data":{"shortcut_name":"Admission Settings",        "col":4}},
    {"id":"mst_sp5",      "type":"spacer",    "data":{"col":12}},
    {"id":"mst_h6",       "type":"paragraph", "data":{"text": hdr("&#128106;","Parent Portal"),               "col":12}},
    {"id":"mst_sc_pli",   "type":"shortcut",  "data":{"shortcut_name":"Parent Login Invite Tool",  "col":4}},
]

shortcuts = [
    {"color":"Blue",   "doc_view":"List","label":"Department",               "link_to":"Department",               "type":"DocType"},
    {"color":"Green",  "doc_view":"List","label":"Programme",                  "link_to":"Programme",                  "type":"DocType"},
    {"color":"Purple", "doc_view":"List","label":"Course",                   "link_to":"Course",                   "type":"DocType"},
    {"color":"Cyan",   "doc_view":"List","label":"Course Master",            "link_to":"Course Master",            "type":"DocType"},
    {"color":"Green",  "doc_view":"List","label":"Curriculum",               "link_to":"Curriculum",               "type":"DocType"},
    {"color":"Yellow", "doc_view":"List","label":"Academic Year",            "link_to":"Academic Year",            "type":"DocType"},
    {"color":"Orange", "doc_view":"List","label":"Academic Term",            "link_to":"Academic Term",            "type":"DocType"},
    {"color":"Blue",   "doc_view":"List","label":"Academic Holiday",         "link_to":"Academic Holiday",         "type":"DocType"},
    {"color":"Blue",   "doc_view":"List","label":"Faculty",                  "link_to":"Faculty",                  "type":"DocType"},
    {"color":"Pink",   "doc_view":"List","label":"Gender",                   "link_to":"Gender",                   "type":"DocType"},
    {"color":"Yellow", "doc_view":"List","label":"Skill",                    "link_to":"Skill",                    "type":"DocType"},
    {"color":"Cyan",   "doc_view":"List","label":"Student Category",         "link_to":"Student Category",         "type":"DocType"},
    {"color":"Green",  "doc_view":"List","label":"Student Master",           "link_to":"Student Master",           "type":"DocType"},
    {"color":"Red",    "doc_view":"List","label":"Exam Component",           "link_to":"Exam Component",           "type":"DocType"},
    {"color":"Orange", "doc_view":"List","label":"Exam Assessment Type",     "link_to":"Exam Assessment Type",     "type":"DocType"},
    {"color":"Purple", "doc_view":"List","label":"Evaluation Schema",        "link_to":"Evaluation Schema",        "type":"DocType"},
    {"color":"Pink",   "doc_view":"List","label":"Grading Schema",           "link_to":"Grading Schema",           "type":"DocType"},
    {"color":"Yellow", "doc_view":"List","label":"Course Schema Assignment", "link_to":"Course Schema Assignment", "type":"DocType"},
    {"color":"Blue",   "doc_view":"List","label":"CGPA Percentage Scale",    "link_to":"CGPA Percentage Scale",    "type":"DocType"},
    {"color":"Blue",   "doc_view":"List","label":"Academic Management System","link_to":"Academic Management System","type":"DocType"},
    {"color":"Green",  "doc_view":"List","label":"Attendance Settings",      "link_to":"Attendance Settings",      "type":"DocType"},
    {"color":"Cyan",   "doc_view":"List","label":"Condonation Reason",       "link_to":"Condonation Reason",       "type":"DocType"},
    {"color":"Purple", "doc_view":"List","label":"Examination Settings",     "link_to":"Examination Settings",     "type":"DocType"},
    {"color":"Orange", "doc_view":"List","label":"Publish Result Setting",   "link_to":"Publish Result Setting",   "type":"DocType"},
    {"color":"Cyan",   "doc_view":"List","label":"Student Portal Settings",  "link_to":"Student Portal Settings",  "type":"DocType"},
    {"color":"Red",    "doc_view":"List","label":"Access Result Settings",   "link_to":"Access Result Settings",   "type":"DocType"},
    {"color":"Grey",   "doc_view":"List","label":"Hostel Settings",          "link_to":"Hostel Settings",          "type":"DocType"},
    {"color":"Grey",   "doc_view":"List","label":"Transcript Settings",      "link_to":"Transcript Settings",      "type":"DocType"},
    {"color":"Grey",   "doc_view":"List","label":"Admission Settings",       "link_to":"Admission Settings",       "type":"DocType"},
    {"color":"Pink",   "doc_view":"List","label":"Parent Login Invite Tool", "link_to":"Parent Login Invite Tool", "type":"DocType"},
]

links = [
    {"label":"Department",               "link_to":"Department",               "link_type":"DocType","onboard":1,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Programme",                  "link_to":"Programme",                  "link_type":"DocType","onboard":1,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Course",                   "link_to":"Course",                   "link_type":"DocType","onboard":1,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Course Master",            "link_to":"Course Master",            "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Curriculum",               "link_to":"Curriculum",               "link_type":"DocType","onboard":1,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Academic Year",            "link_to":"Academic Year",            "link_type":"DocType","onboard":1,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Academic Term",            "link_to":"Academic Term",            "link_type":"DocType","onboard":1,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Academic Holiday",         "link_to":"Academic Holiday",         "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Faculty",                  "link_to":"Faculty",                  "link_type":"DocType","onboard":1,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Gender",                   "link_to":"Gender",                   "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Skill",                    "link_to":"Skill",                    "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Student Category",         "link_to":"Student Category",         "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Student Master",           "link_to":"Student Master",           "link_type":"DocType","onboard":1,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Exam Component",           "link_to":"Exam Component",           "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Exam Assessment Type",     "link_to":"Exam Assessment Type",     "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Evaluation Schema",        "link_to":"Evaluation Schema",        "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Grading Schema",           "link_to":"Grading Schema",           "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Course Schema Assignment", "link_to":"Course Schema Assignment", "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"CGPA Percentage Scale",    "link_to":"CGPA Percentage Scale",    "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Academic Management System","link_to":"Academic Management System","link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Attendance Settings",      "link_to":"Attendance Settings",      "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Condonation Reason",       "link_to":"Condonation Reason",       "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Examination Settings",     "link_to":"Examination Settings",     "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Publish Result Setting",   "link_to":"Publish Result Setting",   "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Student Portal Settings",  "link_to":"Student Portal Settings",  "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Access Result Settings",   "link_to":"Access Result Settings",   "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Hostel Settings",          "link_to":"Hostel Settings",          "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Transcript Settings",      "link_to":"Transcript Settings",      "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Admission Settings",       "link_to":"Admission Settings",       "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
    {"label":"Parent Login Invite Tool", "link_to":"Parent Login Invite Tool", "link_type":"DocType","onboard":0,"type":"Link","hidden":0,"is_query_report":0},
]

# Validate
sc_labels = {s['label'] for s in shortcuts}
missing = [b['data']['shortcut_name'] for b in content if b['type']=='shortcut' and b['data']['shortcut_name'] not in sc_labels]
if missing:
    print("ERROR — missing shortcuts:", missing)
    frappe.destroy()
    raise SystemExit(1)

doc = frappe.get_doc('Workspace', 'Master')
doc.content = json.dumps(content)
doc.icon = 'book-open'
doc.indicator_color = 'purple'
doc.set('shortcuts', [])
for sc in shortcuts:
    doc.append('shortcuts', sc)
doc.set('links', [])
for lk in links:
    doc.append('links', lk)
doc.flags.ignore_permissions = True
doc.flags.ignore_validate    = True
doc.save()
frappe.db.commit()
print(f"SUCCESS — content:{len(content)} shortcuts:{len(shortcuts)} links:{len(links)}")
frappe.destroy()
