"""Customer Out of MH (outside Maharashtra): the lead is taken out of the working lists.

Requirement: "Cust Out of MH - remove lead from system". The lead is not deleted (history, CRE counts and the audit
trail stay): it is CLOSED with a reason, its follow-up date and call-back reminder are cleared, so it no longer
appears in anyone's follow-up queues. Reopening it by hand (Open) puts it back.
"""
from fastapi import HTTPException

from app.modules.leads.models import EnquiryStage
from app.modules.leads.stages import change_stage

OUT_OF_MH = "OUT OF MH"


def is_out_of_mh(lead) -> bool:
    opp = getattr(lead, "opportunity", None)
    return bool(opp and (opp.name or "").strip().upper() == OUT_OF_MH)


def guard(lead):
    """Call before saving: a booked / later customer can't be marked Out of MH."""
    stage = lead.enquiry_stage or EnquiryStage.OPEN
    if stage not in (EnquiryStage.OPEN, EnquiryStage.CLOSED):
        raise HTTPException(400, "This customer is already booked, so it can't be marked Out of MH")


def apply(db, lead, actor_user_id) -> bool:
    if not is_out_of_mh(lead):
        return False
    guard(lead)
    lead.next_followup_at = None
    lead.callback_remind_at = None
    if (lead.enquiry_stage or EnquiryStage.OPEN) == EnquiryStage.OPEN:
        change_stage(db, lead, EnquiryStage.CLOSED, actor_user_id=actor_user_id,
                     reason="Customer is outside Maharashtra (Out of MH) - removed from the working list")
    return True
