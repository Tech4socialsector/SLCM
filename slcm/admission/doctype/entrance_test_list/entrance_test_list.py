# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now_datetime


class EntranceTestList(Document):

    @frappe.whitelist()
    def allocate_seats(self, providers, selected_applicants):
        """
        Admin selects:
          - providers             : list of Entrance Test Provider names (preferences)
          - selected_applicants   : list of child-table row names

        Logic:
          - Creates ONE Entrance Test Seat Allocation record per applicant.
          - Stores all selected providers in the 'assigned_preferences' child table.
          - Marks child record as 'Allocated' in entrance_test_applicant.
        """
        # Ensure metadata and database schema are synced with JSON files
        frappe.reload_doc("admission", "doctype", "entrance_test_preference_assigned")
        frappe.reload_doc("admission", "doctype", "entrance_test_seat_allocation")
        frappe.clear_cache(doctype="Entrance Test Seat Allocation")
        
        if isinstance(providers, str):
            providers = json.loads(providers)
        if isinstance(selected_applicants, str):
            selected_applicants = json.loads(selected_applicants)

        if not providers:
            frappe.throw("No providers selected.")
        if not selected_applicants:
            frappe.throw("No applicants selected.")

        # Validate providers
        provider_list = []
        for pname in providers:
            pdoc = frappe.get_doc("Entrance Test Provider", pname)
            if not pdoc.active:
                frappe.throw(f"Provider '{pname}' is not active.")
            provider_list.append(pdoc)

        # Build lookup map for child table rows
        applicant_map = {app.name: app for app in self.entrance_test_applicant}

        created_count = 0

        for app_name in selected_applicants:
            app = applicant_map.get(app_name)
            if not app:
                continue

            # Skip if already processed
            if getattr(app, "allocation_status", "") == "Allocated":
                continue

            # Check if an allocation record already exists for this applicant/test
            existing_allocation = frappe.db.get_value("Entrance Test Seat Allocation", {
                "entrance_test_list": self.name,
                "applicant": app.applicant_id
            }, "name")

            if existing_allocation:
                allocation = frappe.get_doc("Entrance Test Seat Allocation", existing_allocation)
            else:
                # Create NEW single allocation record
                allocation = frappe.new_doc("Entrance Test Seat Allocation")
                allocation.entrance_test_list    = self.name
                allocation.academic_year         = self.academic_year
                allocation.admission_cycle       = self.admission_cycle
                allocation.campus                = self.campus
                allocation.program_level         = self.program_level

                # Applicant details
                allocation.applicant             = app.applicant_id
                allocation.candidate_name        = app.candidate_name
                allocation.program               = app.program
                allocation.reservation_category  = app.reservation_category
                allocation.email                 = app.email
                allocation.gender                = app.gender
                allocation.allocation_status      = "Not Allocated"

            # Reset / Update preferences in child table
            allocation.set("assigned_preferences", [])
            for idx, pdoc in enumerate(provider_list, start=1):
                allocation.append("assigned_preferences", {
                    "provider": pdoc.name,
                    "center_name": pdoc.center_name,
                    "center_address": pdoc.center_address,
                    "preference_order": idx
                })

            allocation.save(ignore_permissions=True)

            # ✅ Mark child row as "Allocated"
            app.allocation_status = "Allocated"
            created_count += 1

        self.save(ignore_permissions=True)
        frappe.db.commit()

        return created_count


# ─────────────────────────────────────────────────────────────────────────────
# Applicant-facing APIs
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_applicant_preferences(applicant_id, entrance_test_list):
    """
    Returns the preferences from the SINGLE allocation record for this applicant.
    """
    allocation_name = frappe.db.get_value("Entrance Test Seat Allocation", {
        "applicant": applicant_id,
        "entrance_test_list": entrance_test_list
    }, "name")

    if not allocation_name:
        return []

    allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)
    
    # If already allocated, we might just return the chosen one or indicator
    # But for selection, we need the list.
    
    preferences = []
    for p in allocation.assigned_preferences:
        preferences.append({
            "entrance_test_provider": p.provider,
            "center_name": p.center_name,
            "center_address": p.center_address,
            "preference_order": p.preference_order,
            "is_full": _get_remaining_capacity(p.provider) <= 0,
            "allocation_status": allocation.allocation_status,
            "seat_number": allocation.seat_number,
            "room_name": allocation.room_name
        })

    return preferences


@frappe.whitelist()
def confirm_applicant_preference(allocation_name, selected_provider):
    """
    Called when applicant confirms their chosen provider from the SAME record.
    """
    allocation = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)

    if allocation.allocation_status == "Allocated":
        frappe.throw("You have already been allocated a seat.")

    provider = frappe.get_doc("Entrance Test Provider", selected_provider)

    # Find first room with available capacity
    assigned_room = None
    new_reserved  = None
    seat_number   = None

    for room in provider.provider_room:
        if not getattr(room, "active", 1):
            continue
        capacity = room.room_capacity or 0
        reserved = room.room_reserved_seats or 0
        if (capacity - reserved) > 0:
            assigned_room = room
            new_reserved  = reserved + 1
            seat_number   = f"{room.room_name}-{new_reserved:02d}"
            break

    if not assigned_room:
        frappe.throw(
            f"Sorry, '{provider.center_name}' is now full. "
            "Please choose another preference center."
        )

    # Update the SINGLE record
    allocation.entrance_test_provider = selected_provider
    allocation.center_name            = provider.center_name
    allocation.center_address         = provider.center_address
    allocation.room_code              = assigned_room.room_code
    allocation.room_name              = assigned_room.room_name
    allocation.building               = assigned_room.building
    allocation.floor                  = assigned_room.floor
    allocation.seat_number            = seat_number
    allocation.allocation_status      = "Allocated"
    allocation.allocation_date        = now_datetime()
    allocation.allocated_by           = frappe.session.user
    allocation.save(ignore_permissions=True)

    # Update room reserved count on provider
    assigned_room.room_reserved_seats     = new_reserved
    assigned_room.room_available_capacity = (assigned_room.room_capacity or 0) - new_reserved
    provider.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "seat_number":    seat_number,
        "room_name":      assigned_room.room_name,
        "center_name":    provider.center_name,
        "center_address": provider.center_address,
    }


def _get_remaining_capacity(provider_name):
    """Total remaining seats across all active rooms for a provider."""
    try:
        provider = frappe.get_doc("Entrance Test Provider", provider_name)
        total = 0
        for room in provider.provider_room:
            if not getattr(room, "active", 1):
                continue
            capacity = room.room_capacity or 0
            reserved = room.room_reserved_seats or 0
            total   += max(0, capacity - reserved)
        return total
    except Exception:
        return 0