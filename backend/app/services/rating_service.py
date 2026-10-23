# File: backend/app/services/rating_service.py
from sqlalchemy.orm import Session


def create_rating(db: Session, rater, booking_id, data):
    """Stage 3. Booking must be completed; rater must be requester or resource owner;
    rated_user = the other party; one rating per rater per booking (409)."""
    raise NotImplementedError


def recalc_trust_score(db: Session, user_id):
    """Stage 3. Update users.trust_score and rating_count after a new rating.
    Suggested: Bayesian average so one 5-star doesn't equal a 5.0 trust score."""
    raise NotImplementedError