Step 33b – apply AFTER step33 (copy new_app/ and new_src/src/ over the project).
- Reject now asks for a remark in red; a clear message shows if it is empty.
- Owner > Approvals: one card per customer (price, discounted price, customer, ATW, Customer processing) with Approve / Reject. Initial and Final tabs. Old ATW/special requests under "Other requests".
- Journey bar (Enquiry > Follow-ups > Test ride > Quotation > Booking > Initial approval > Payment&docs > Insurance > Final approval > RTO > Invoice > Delivery) with "Now: ... with <department>" on the PBA/CRE lead page, Owner/GM/Admin/RTO file page and Insurance case page.
- Speed: Deal workflow board is paged (25 rows) and filtered in SQL; ~20 database indexes are created automatically on restart (lead, follow-ups, payments, documents...).
Test: reject with empty remark -> red message; reject with remark -> PBA notified; open any customer in Insurance/RTO -> journey bar visible.
