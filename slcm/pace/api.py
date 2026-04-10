import frappe
from frappe.utils import get_url, strip_html_tags
from urllib.parse import quote


def _abs_url(path: str | None) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return get_url(path)


def _safe_error(message: str, exc: Exception | None = None) -> dict:
    if exc:
        frappe.log_error(frappe.get_traceback(), "PACE API")
    if exc and getattr(frappe.conf, "developer_mode", 0):
        return {"success": False, "message": f"{message} ({exc})"}
    return {"success": False, "message": message}


def _get_active_pace_admission_name(academic_year=None) -> str | None:
    filters = {"active": 1}
    if academic_year:
        filters["academic_year"] = academic_year
    return frappe.db.get_value("PACE Admission", filters, "name", order_by="creation desc")


@frappe.whitelist(allow_guest=True)
def get_pace_programmes(academic_year=None):
    """
    Programmes from the active PACE Admission (child table PACE Admission Programme),
    enriched from PACE Programme. Only includes published programmes.

    Each item includes detail_slug for URLs: /pace/admission/<detail_slug>
    """
    pace_admission = _get_active_pace_admission_name(academic_year=academic_year)
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

        image = _abs_url(p.banner_image)

        admission_status = (p.admission_status or "Closed").strip() or "Closed"

        out.append(
            {
                "programme": p.name,
                "name": p.name,
                "programme_name": p.programme_name or p.name,
                "programme_type": "PACE PROGRAMME",
                "route": p.route,
                "detail_slug": slug,
                "detail_url": f"/pace/admission/{quote(slug, safe='')}",
                "description": overview_plain,
                "short_description": overview_plain,
                "duration_label": duration_label,
                "duration": p.duration,
                "admission_status": admission_status,
                "image_url": image,
                "programme_image": image,
                "total_seats": row.total_seats,
                "max_applications": row.max_applications,
                "application_received": row.application_received,
                "appliocation_fee_indian": row.appliocation_fee_indian,
                "appliocation_fee_foreign": row.appliocation_fee_foreign,
            }
        )

    return out


@frappe.whitelist(allow_guest=True)
def get_pace_page_data():
    """
    Composite payload for /pace/admission page.
    """
    try:
        pc = frappe.get_single("Applicant Portal Config")

        ticker_items = []
        for row in pc.get("ticker_items") or []:
            if (row.is_active or 0) == 1:
                ticker_items.append(
                    {"ticker_text": row.ticker_text or "", "ticker_link": row.ticker_link or ""}
                )

        faqs = frappe.get_all(
            "PACE FAQs",
            filters={"category": "Admission", "is_programme_specific": 0},
            fields=["question", "answer"],
            order_by="creation desc",
        )

        programmes = []
        pace_admission = _get_active_pace_admission_name()
        hero_badge = (pc.get("hero_badge_text") or "").strip()

        if pace_admission:
            # Dynamically fetch academic year from the active admission record
            academic_year = frappe.db.get_value("PACE Admission", pace_admission, "academic_year")
            if academic_year:
                hero_badge = f"Enrolling Now for {academic_year}"

            rows = frappe.get_all(
                "PACE Admission Programme",
                filters={"parent": pace_admission, "parenttype": "PACE Admission"},
                fields=["programme"],
                order_by="idx asc",
            )
            for r in rows:
                if not r.programme:
                    continue
                p = frappe.db.get_value(
                    "PACE Programme",
                    r.programme,
                    [
                        "name",
                        "programme_name",
                        "route",
                        "published",
                        "overview",
                        "duration",
                        "duration_type",
                        "banner_image",
                    ],
                    as_dict=True,
                )
                if not p or not p.published:
                    continue

                slug = (p.route or "").strip() or p.name
                programmes.append(
                    {
                        "name": p.name,
                        "programme": p.name,
                        "programme_name": p.programme_name or p.name,
                        "programme_type": "PACE PROGRAMME",
                        "programme_image": _abs_url(p.banner_image),
                        "short_description": strip_html_tags(p.overview or "").strip(),
                        "duration": p.duration,
                        "duration_type": p.duration_type or "",
                        "detail_url": f"/pace/admission/{quote(slug, safe='')}",
                    }
                )

        return {
            "success": True,
            "hero_title": (pc.get("hero_title") or "").strip(),
            "hero_subtitle": (pc.get("hero_subtitle") or "").strip(),
            "hero_description": (pc.get("hero_description") or "").strip(),
            "hero_badge_text": hero_badge,
            "hero_background_image": _abs_url(pc.get("hero_background_image")),
            "hero_cta_label": (pc.get("hero_cta_label") or "").strip(),
            "hero_cta2_label": (pc.get("hero_cta2_label") or "").strip(),
            "hero_prospectus_file": _abs_url(pc.get("hero_prospectus_file")),
            "show_ticker": int(pc.get("show_ticker") or 0),
            "enable_pace_admission": int(pc.get("enable_pace_admission") or 0),
            "ticker_items": ticker_items,
            "faqs": faqs or [],
            "programmes": programmes,
            "contact_email": (pc.get("contact_email") or "").strip(),
            "support_email": (pc.get("support_email") or "").strip(),
        }
    except Exception as e:
        return _safe_error("Could not load PACE page data.", e)


@frappe.whitelist(allow_guest=True)
def submit_pace_enquiry(full_name=None, email=None, phone=None, programme_of_interest=None):
    try:
        full_name = (full_name or "").strip()
        email = (email or "").strip()
        phone = (phone or "").strip()
        programme_of_interest = (programme_of_interest or "").strip()

        if not full_name or not email or not phone or not programme_of_interest:
            return _safe_error("All fields are required.")

        pc = frappe.get_single("Applicant Portal Config")
        notify_to = (pc.get("contact_email") or "").strip()
        if not notify_to:
            return _safe_error("Contact email is not configured.")

        doc = frappe.get_doc(
            {
                "doctype": "PACE Enquiry",
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "programme_of_interest": programme_of_interest,
                "status": "New",
            }
        )
        doc.insert(ignore_permissions=True)

        subject = f"New PACE Programme Enquiry — {programme_of_interest}"
        message = (
            "<p>A new PACE programme enquiry has been submitted.</p>"
            "<ul>"
            f"<li><b>Full Name</b>: {frappe.utils.escape_html(full_name)}</li>"
            f"<li><b>Email</b>: {frappe.utils.escape_html(email)}</li>"
            f"<li><b>Phone</b>: {frappe.utils.escape_html(phone)}</li>"
            f"<li><b>Programme of Interest</b>: {frappe.utils.escape_html(programme_of_interest)}</li>"
            "</ul>"
        )
        frappe.sendmail(recipients=[notify_to], subject=subject, message=message, delayed=False)

        return {"success": True}
    except Exception as e:
        return _safe_error("Could not submit enquiry. Please try again.", e)
