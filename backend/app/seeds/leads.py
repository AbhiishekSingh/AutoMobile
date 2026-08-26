"""Seed PBA module lookups + sample leads.  Run:  python -m app.seed_crm
Run app.seed first (creates branches + users)."""
from datetime import datetime, timedelta

from app.core.database import Base, SessionLocal, engine
from app.db import base as _base  # register models
from app.modules.leads import models as m
from app.modules.users.models import AppUser, Branch

ENQUIRY_MODES = ["Hyperlocal", "Digital", "Aggregators", "Dealer Digital",
                 "Cross Sell", "Activity", "MBO", "Tele-In", "Walk-in"]
OPPORTUNITY = ["HOT LEAD", "WARM LEAD", "COLD LEAD", "BOOKING DONE", "BIKE DELIVERED",
               "FUTURE LEAD", "CLOSED LEAD", "DEAD LEAD", "LOST TO CO-DEALER", "LOST TO OTHER BRAND"]
DISPOSITIONS = ["RINGING", "CALL LATER", "PLANNING", "SWITCH OFF", "PLAN CANCEL",
                "TEST RIDE BOOKED", "TEST RIDE COMPLETED", "BOOKING DONE",
                "DELIVERY DONE", "PRODUCT QUALITY ISSUE"]
LOST_REASONS = ["Casual Enquiry", "Incorrect No.", "Out of city", "Stock Issue",
                "Price/Finance concern"]
MODELS = ["DUKE 160 TFT", "DUKE 200 BS VI", "RC 160", "RC 200", "DUKE 250", "DUKE 390",
          "DUKE 390 R", "RC 390", "ADV 250", "ADV 390", "ADV 390 X PLUS", "ADV 390 S",
          "ADV 390 R", "ENDURO 390 R"]

# sample leads: name, phone, model, opportunity, disposition, mode, sla, stage
# SAMPLES = [
#     ("Rahul Sharma", "9800000090", "DUKE 390", "HOT LEAD", "RINGING", "Walk-in", "GREEN", "OPEN"),
#     ("Sneha Verma", "9700000045", "RC 200", "WARM LEAD", "CALL LATER", "Digital", "YELLOW", "OPEN"),
#     ("Vikram Singh", "9900000033", "DUKE 250", "COLD LEAD", "PLANNING", "Hyperlocal", "RED", "OPEN"),
#     ("Karan Patel", "9600000012", "ADV 390", "BOOKING DONE", "BOOKING DONE", "Digital", "GREEN", "BOOKED"),
#     ("Pooja Mehta", "9800000076", "DUKE 160 TFT", "BIKE DELIVERED", "DELIVERY DONE", "Aggregators", "GREEN", "INVOICED"),
#     ("Aditya Rao", "9500000021", "RC 160", "FUTURE LEAD", "CALL LATER", "Walk-in", "YELLOW", "OPEN"),
#     ("Aniket Joshi", "9000000064", "ADV 250", "CLOSED LEAD", "PLAN CANCEL", "Dealer Digital", "RED", "CLOSED"),
#     ("Manish Yadav", "7800000090", "DUKE 200 BS VI", "DEAD LEAD", "SWITCH OFF", "Tele-In", "RED", "CLOSED"),
#     ("Rohit Kumar", "9100000087", "ADV 390 X PLUS", "LOST TO OTHER BRAND", "PRODUCT QUALITY ISSUE", "Hyperlocal", "RED", "CLOSED"),
#     ("Sahil Khan", "9300000009", "ENDURO 390 R", "LOST TO CO-DEALER", "TEST RIDE COMPLETED", "Walk-in", "GREEN", "OPEN"),
# ]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        def seed_lookup(Model, names):
            for n in names:
                if not db.query(Model).filter(Model.name == n).first():
                    db.add(Model(name=n))
            db.commit()

        seed_lookup(m.EnquiryMode, ENQUIRY_MODES)
        seed_lookup(m.OpportunityStatus, OPPORTUNITY)
        seed_lookup(m.Disposition, DISPOSITIONS)
        seed_lookup(m.LostReason, LOST_REASONS)
        seed_lookup(m.BikeModel, MODELS)

        # if db.query(m.Lead).count() > 0:
        #     print("Leads already seeded — skipping sample leads.")
        #     return

        # branch = db.query(Branch).first()
        # pba = db.query(AppUser).filter(AppUser.login_id == "PBA-014").first()

        # def look(Model, name):
        #     return db.query(Model).filter(Model.name == name).first()

        # for i, (name, phone, model, opp, disp, mode, sla, stage) in enumerate(SAMPLES, 1):
        #     cust = m.Customer(phone=phone, full_name=name, city="Thane", pincode="400604")
        #     db.add(cust); db.flush()
        #     enq_at = now_ist() - timedelta(days=i)
        #     lead = m.Lead(
        #         enquiry_no=f"ENQ{125000 + i}", customer_id=cust.customer_id,
        #         branch_id=branch.branch_id if branch else None,
        #         assigned_user_id=pba.user_id if pba else None,
        #         mode_id=look(m.EnquiryMode, mode).id, model_id=look(m.BikeModel, model).id,
        #         color="Blue", sku_code="00JP1D86",
        #         lead_type=m.LeadType.SALES,
        #         source=m.LeadSource.WALKIN if mode == "Walk-in" else m.LeadSource.CSV,
        #         enquiry_stage=m.EnquiryStage(stage),
        #         opportunity_status_id=look(m.OpportunityStatus, opp).id,
        #         current_disposition_id=look(m.Disposition, disp).id,
        #         sla_flag=m.SLAFlag(sla), enquiry_at=enq_at,
        #         first_contact_at=enq_at + timedelta(hours=1) if sla == "GREEN" else None,
        #         ageing_days=i, salesperson_email=pba.email if pba else None,
        #     )
        #     db.add(lead); db.flush()
        #     db.add(m.LeadFollowup(
        #         lead_id=lead.lead_id, user_id=pba.user_id if pba else None,
        #         remark="Initial follow-up", disposition_id=look(m.Disposition, disp).id,
        #         opportunity_status_id=look(m.OpportunityStatus, opp).id,
        #         created_at=enq_at + timedelta(hours=1)))
        #     if disp == "TEST RIDE COMPLETED":
        #         db.add(m.TestRide(lead_id=lead.lead_id, model_id=look(m.BikeModel, model).id,
        #                           color="Blue", status=m.TestRideStatus.COMPLETED,
        #                           completed=True, scheduled_at=enq_at, slot="Evening",
        #                           preferred_location="Showroom"))
        # db.commit()
        # print(f"Seeded {len(SAMPLES)} sample leads + lookups.")

    finally:
        db.close()


if __name__ == "__main__":
    run()