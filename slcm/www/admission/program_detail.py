import frappe

login_required = False

def get_context(context):
    import frappe, re
    frappe.log_error(title="Portal Debug", message=f"program_detail start. form_dict={dict(frappe.form_dict)}")

    # 1. Portal config
    try:
        from slcm.admission.utils.portal import get_portal_config
        context.portal_config = get_portal_config()
        frappe.log_error(title="Portal Debug", message=f"portal_config loaded. primary={context.portal_config.get('primary_color')}")
    except Exception as e:
        frappe.log_error(title="Portal Debug", message=f"portal_config FAILED: {e}")
        context.portal_config = {}

    # 2. Resolve program slug
    slug = frappe.form_dict.get("name") or frappe.form_dict.get("program_slug") or ""
    frappe.log_error(title="Portal Debug", message=f"slug={repr(slug)}")

    def _normalize_slug(s):
        if not s: return ""
        s = s.lower()
        s = re.sub(r'[^a-z0-9]+', '-', s)
        return s.strip('-')

    program_name = None
    # 1. Direct name match
    if frappe.db.exists("Program", slug):
        program_name = slug
    
    # 2. Direct slug match
    if not program_name:
        program_name = frappe.db.get_value("Program", {"program_slug": slug}, "name")
    
    # 3. Normalized slug match
    if not program_name:
        all_progs = frappe.get_all("Program", fields=["name","program_slug"])
        slug_norm = _normalize_slug(slug)
        for p in all_progs:
            if _normalize_slug(p.program_slug) == slug_norm:
                program_name = p.name
                break
            if _normalize_slug(p.name) == slug_norm:
                program_name = p.name
                break

    frappe.log_error(title="Portal Debug", message=f"program_name resolved: {repr(program_name)}")

    if not program_name:
        frappe.log_error(title="Portal Debug", message=f"Program not found for slug={repr(slug)}")
        context.program = None
        context.app_open = False
        context.no_cache = 1
        return

    # 3. Get active cycle
    cycle = frappe.db.get_value("Admission Cycle", {"status": "Active"}, "name")
    frappe.log_error(title="Portal Debug", message=f"active_cycle={repr(cycle)}")

    # 4. Get cycle program record
    cp = None
    if cycle:
        cp = frappe.db.get_value(
            "Admission Cycle Program",
            {"parent": cycle, "program": program_name},
            ["program_name", "desciption", "eligibility_hint",
             "program_media", "reservation_policy", "seats", "brochure_url"],
            as_dict=True
        )
        frappe.log_error(title="Portal Debug", message=f"cycle_program={cp}")

    if not cp:
        # Fallback: get from Program DocType directly
        frappe.log_error(title="Portal Debug", message=f"No cycle program found, falling back to Program DocType")
        try:
            prog_doc = frappe.get_doc("Program", program_name)
            cp = frappe._dict({
                "program_name": prog_doc.program_name or program_name,
                "desciption": getattr(prog_doc, 'description', '') or '',
                "eligibility_hint": '',
                "program_media": program_name,  # Program Media name = Program name
                "reservation_policy": None,
                "seats": 0,
                "brochure_url": '',
            })
        except:
             cp = frappe._dict({
                "program_name": program_name,
                "desciption": '',
                "eligibility_hint": '',
                "program_media": program_name,
                "reservation_policy": None,
                "seats": 0,
                "brochure_url": '',
            })

    # 5. Get media
    images = []
    videos = []
    try:
        media_items = frappe.get_all("Media",
            filters={"parent": cp.program_media, "parentfield": "media_gallery"},
            fields=["media_type", "file", "caption", "sequence"],
            order_by="sequence asc"
        )
        frappe.log_error(title="Portal Debug", message=f"media_items found: {len(media_items)} for parent={cp.program_media}")
        for m in media_items:
            if (m.media_type or "").lower() == "video":
                videos.append({"file": m.file, "caption": m.caption})
            else:
                images.append({"file": m.file, "caption": m.caption})
    except Exception as e:
        frappe.log_error(title="Portal Debug", message=f"media fetch FAILED: {e}")

    # 6. Get categories from reservation policy
    categories = []
    try:
        if cp.reservation_policy:
            cats = frappe.get_all(
                "Program Reservation Category",
                filters={"parent": cp.reservation_policy},
                fields=["category_name", "seats", "application_fee", "percentage"],
                order_by="idx asc"
            )
            categories = cats
            frappe.log_error(title="Portal Debug", message=f"categories found: {len(categories)}")
    except Exception as e:
        frappe.log_error(title="Portal Debug", message=f"categories FAILED: {e}")

    # 7. Get brochure from Program Media
    brochure_url = cp.brochure_url or ''
    try:
        if cp.program_media:
            brochure_url = frappe.db.get_value(
                "Program Media", cp.program_media, "brochure_pdf"
            ) or brochure_url
    except Exception as e:
        frappe.log_error(title="Portal Debug", message=f"brochure FAILED: {e}")

    # 8. Check app window
    app_open = False
    try:
        if cycle:
            cyc_doc = frappe.get_doc("Admission Cycle", cycle)
            from frappe.utils import now_datetime, get_datetime
            now = now_datetime()
            start = get_datetime(cyc_doc.application_start) if cyc_doc.application_start else None
            end   = get_datetime(cyc_doc.application_end) if cyc_doc.application_end else None
            app_open = (not start or now >= start) and (not end or now <= end)
    except Exception as e:
        frappe.log_error(title="Portal Debug", message=f"app_open check FAILED: {e}")
        app_open = True

    # Compute fill badge logic
    p_fill_badge = ""
    p_fill_class = ""
    p_fill_pct   = 0
    try:
        received    = int(cp.get("application_count") or 0)
        total_seats = int(cp.get("max_applications") or cp.seats or 0)

        if total_seats > 0:
            pct = round((received / total_seats) * 100)
            p_fill_pct = pct
            if pct >= 90:
                p_fill_badge = f"Only {total_seats - received} seats left"
                p_fill_class = "badge-danger"
            elif pct >= 70:
                p_fill_badge = f"{pct}% filled"
                p_fill_class = "badge-warning"
            elif pct >= 40:
                p_fill_badge = f"{pct}% filled"
                p_fill_class = "badge-info"
            else:
                p_fill_badge = "Seats available"
                p_fill_class = "badge-success"
    except Exception as e:
        frappe.log_error(title="Portal Debug", message=f"program_detail fill badge failed: {e}")

    # 9. Build context
    context.program = frappe._dict({
        "program":          program_name,
        "program_name":     cp.program_name or program_name,
        "description":      cp.desciption or '',
        "eligibility_hint": cp.eligibility_hint or '',
        "total_seats":      cp.seats or 0,
        "brochure_url":     brochure_url,
        "images":           images,
        "videos":           videos,
        "categories":       categories,
        "program_slug":     slug,
        "fill_badge":       p_fill_badge,
        "fill_class":       p_fill_class,
        "fill_pct":         p_fill_pct,
    })
    context.app_open    = app_open
    context.active_cycle = cycle
    context.program_slug = slug
    context.no_cache    = 1

    frappe.log_error(
        title="Portal Debug",
        message=f"program_detail DONE. program={program_name} images={len(images)} "
        f"categories={len(categories)} description_len={len(cp.desciption or '')}"
    )
