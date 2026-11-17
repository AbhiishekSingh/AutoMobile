# Step 33 – Owner Portal workflow
Copy new_app/ over your app/ and new_src/src/ over your src/ (same as earlier steps). No new packages. New table is created automatically on restart.

Flow: Booking DONE -> Initial Owner approval (discounted price + Customer Processing YES/NO + ATW YES/NO) -> PBA records DP/full payment + uploads required documents -> file moves to Insurance AUTOMATICALLY -> Insurance uploads policy PDF -> Final Owner approval -> RTO (and Delivery Challan enabled for PBA) -> delivery.

Test
1. PBA: set a lead to BOOKING DONE. Owner gets a notification; lead page shows "Owner approval workflow". Insurance must NOT exist yet.
2. Owner (Deal workflow / lead file): Approve without YES/NO -> error. Reject without remark -> error. Reject with remark -> PBA notified, "Send to Owner again" appears for PBA. Approve with price, Customer processing YES, ATW YES/NO.
3. PBA: record payment (cash: full amount; EMI: down payment) and upload Aadhaar, PAN, electricity bill/rent agreement. The moment both are complete, Insurance + CRE are notified and the file appears in the Insurance list. (Before that, Insurance cannot see it.)
4. Insurance: complete the case and upload policy PDF -> Owner gets "Final approval needed"; RTO sees nothing yet.
5. Owner: review (prices, payment, finance, documents, policy PDF, ATW) -> Reject needs a remark and notifies PBA; PBA resubmits; Owner approves -> RTO case created, RTO + PBA notified, Delivery Challan stage shows ENABLED.
6. PBA enters invoice details, then Generate delivery receipt (blocked before final approval).
7. GM: "Deal workflow" board and lead file are view-only. PBA sees own deals only.
Notes: Delivery no longer waits for RTO "Registered" (as per the new requirement: challan opens when the file reaches RTO). Old PBA "special request" approval still exists as optional. Frontend/Postgres not run in my sandbox - please report any error.
