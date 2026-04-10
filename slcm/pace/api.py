import frappe
from frappe.utils import get_url, strip_html_tags
from urllib.parse import quote


@frappe.whitelist(allow_guest=True)
def get_pace_programmes(academic_year=None):
    """
    Programmes from the active PACE Admission (child table PACE Admission Programme),
    enriched from PACE Programme. Only includes published programmes.

    Each item includes detail_slug for URLs: /pace/admission/<detail_slug>
    """
    filters = {"active": 1}
    if academic_year:
        filters["academic_year"] = academic_year

    pace_admission = frappe.db.get_value(
        "PACE Admission", filters, "name", order_by="creation desc"
    )
    if not pace_admission:
        return []

    rows = frappe.get_all(
        "PACE Admission Programme",
        filters={"parent": pace_admission, "parenttype": "PACE Admission"},
        fields=[
            "programme",
            "total_seats",
            "max_applications",
            "application_received",
            "appliocation_fee_indian",
            "appliocation_fee_foreign",
        ],
        order_by="idx asc",
    )

    out = []
    for row in rows:
        if not row.programme:
            continue

        p = frappe.db.get_value(
            "PACE Programme",
            row.programme,
            [
                "name",
                "programme_name",
                "route",
                "published",
                "overview",
                "duration",
                "duration_type",
                "admission_status",
                "banner_image",
            ],
            as_dict=True,
        )
        if not p or not p.published:
            continue

        slug = (p.route or "").strip() or p.name
        overview_plain = strip_html_tags(p.overview or "").strip()
        if len(overview_plain) > 240:
            overview_plain = overview_plain[:237] + "…"

        dur = p.duration
        dt = p.duration_type or "Year"
        duration_label = ""
        if dur is not None and dur != "":
            try:
                n = int(dur)
                unit = "Year" if dt == "Year" else "Month"
                duration_label = f"{n} {unit}{'s' if n != 1 else ''}"
            except (TypeError, ValueError):
                duration_label = str(dur)

        image = (p.banner_image or "").strip()
        if image and not image.startswith("http"):
            image = get_url(image)

        admission_status = (p.admission_status or "Closed").strip() or "Closed"

        out.append(
            {
                "programme": p.name,
                "programme_name": p.programme_name or p.name,
                "route": p.route,
                "detail_slug": slug,
                "detail_url": f"/pace/admission/{quote(slug, safe='')}",
                "description": overview_plain,
                "duration_label": duration_label,
                "admission_status": admission_status,
                "image_url": image,
                "total_seats": row.total_seats,
                "max_applications": row.max_applications,
                "application_received": row.application_received,
                "appliocation_fee_indian": row.appliocation_fee_indian,
                "appliocation_fee_foreign": row.appliocation_fee_foreign,
            }
        )

    return out
