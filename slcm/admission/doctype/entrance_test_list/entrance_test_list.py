# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now_datetime

class EntranceTestList(Document):
    @frappe.whitelist()
    def allocate_seats(self, provider, selected_applicants):
        # selected_applicants will be a list of child table names (e.g., "etvubarv4e")
        if isinstance(selected_applicants, str):
            selected_applicants = json.loads(selected_applicants)
            
        if not selected_applicants:
            frappe.throw("No applicants selected for allocation.")

        # Build lookup map for applicants in the child table
        applicant_map = {app.name: app for app in self.entrance_test_applicant}
        
        provider_doc = frappe.get_doc("Entrance Test Provider", provider)
        allocated_count = 0
        allocated_applicants_docs = []
        
        # Map selected applicants names to their actual objects
        to_allocate = []
        for name in selected_applicants:
            if name in applicant_map:
                to_allocate.append(applicant_map[name])

        student_idx = 0
        for room in provider_doc.provider_room:
            if not getattr(room, "active", 1):
                continue
                
            capacity = room.room_capacity or 0
            reserved = room.room_reserved_seats or 0
            
            while student_idx < len(to_allocate) and (capacity - reserved) > 0:
                app = to_allocate[student_idx]
                
                # Check status safely
                if getattr(app, "allocation_status", "Not Allocated") == "Allocated":
                    student_idx += 1
                    continue

                # 1. Create Seat Allocation Record
                allocation = frappe.new_doc("Entrance Test Seat Allocation")
                allocation.entrance_test_list = self.name
                allocation.academic_year = self.academic_year
                allocation.admission_cycle = self.admission_cycle
                allocation.campus = self.campus
                allocation.program_level = self.program_level
                
                allocation.applicant = app.applicant_id
                allocation.candidate_name = app.candidate_name
                allocation.program = app.program
                allocation.reservation_category = app.reservation_category
                allocation.email = app.email
                allocation.gender = app.gender
                
                allocation.entrance_test_provider = provider_doc.name
                allocation.center_name = provider_doc.center_name
                allocation.center_address = provider_doc.center_address
                
                allocation.room_code = room.room_code
                allocation.room_name = room.room_name
                allocation.building = room.building
                allocation.floor = room.floor
                
                next_seat_num = reserved + 1
                allocation.seat_number = f"{room.room_name}-{next_seat_num:02d}"
                
                allocation.allocation_status = "Allocated"
                allocation.allocation_date = now_datetime()
                allocation.allocated_by = frappe.session.user
                
                allocation.insert(ignore_permissions=True)
                
                # 2. Update Room Counts
                reserved += 1
                room.room_reserved_seats = reserved
                room.room_available_capacity = capacity - reserved
                
                # 3. Mark for removal from child table
                allocated_applicants_docs.append(app)
                
                student_idx += 1
                allocated_count += 1

        if allocated_count == 0:
            frappe.throw("No seats could be allocated. The selected provider is currently full.")

        # Remove allocated applicants from the child table
        for app_doc in allocated_applicants_docs:
            self.remove(app_doc)

        # Save provider to update total reserved/available seats
        provider_doc.save(ignore_permissions=True)
        
        # Save self to reflect removal of applicants
        self.save(ignore_permissions=True)
        frappe.db.commit()

        # Provide detailed feedback
        if allocated_count < len(to_allocate):
            frappe.msgprint(
                f"<b>Partial Allocation:</b> Allocated {allocated_count} seats. "
                f"{len(to_allocate) - allocated_count} students could not be allocated due to reaching provider capacity.",
                indicator="orange"
            )
        
        return allocated_count
