from fastapi import APIRouter

from app.payments import PaymentDetails

router = APIRouter(tags=["payments"])


@router.get("/payments", response_model=PaymentDetails)
def payment_details():
    """What to enter in a bank's treasury payment order; the same for every tax."""
    return PaymentDetails()
