from typing import Dict
from profiles.models import UserProfile


def build_profile_response(profile: UserProfile) -> Dict:
    """
    Constructs a full profile JSON response from a UserProfile instance.
    SAFE:
    - Does not fabricate empty values
    - Handles missing related objects cleanly
    """

    # --------------------------------------------------
    # PERSONAL
    # --------------------------------------------------
    personal = getattr(profile, "personal", None)

    personal_data = {
        "fullName": personal.full_name if personal and personal.full_name else None,
        "nickname": personal.nickname if personal and personal.nickname else None,
        "gender": personal.gender if personal and personal.gender else None,
        "dob": personal.dob.strftime("%Y-%m-%d") if personal and personal.dob else None,
        "email": personal.email if personal and personal.email else None,
        "country_code": personal.country_code if personal and personal.country_code else None,
        "phone": personal.phone if personal and personal.phone else None,
        "address": personal.address if personal and personal.address else None,
        "nativePlace": personal.native_place if personal and personal.native_place else None,
        "currentCity": personal.current_city if personal and personal.current_city else None,
        "profileImage": personal.profile_image if personal and personal.profile_image else None,
        "community": personal.community if personal and personal.community else None,
         # 🔥 ADD STATUS HERE
        "status": personal.status if personal and personal.status else None,
    }

    # --------------------------------------------------
    # EDUCATION  ✅ FIXED (OneToOne safe access)
    # --------------------------------------------------
    try:
        edu = profile.education
    except Exception:
        edu = None

    education_data = {
        "qualification": edu.qualification if edu else None,
        "institution": edu.institution if edu else None,
        "field": edu.field if edu else None,
        "startYear": edu.start_year if edu else None,
        "endYear": edu.end_year if edu else None,
        "currentlyStudying": edu.currently_studying if edu else False,
    }

    # --------------------------------------------------
    # JOB
    # --------------------------------------------------
    job = getattr(profile, "job", None)

    job_data = {
        "occupationType": job.occupation_type if job and job.occupation_type else None,
        "companyName": job.company_name if job and job.company_name else None,
        "role": job.role if job and job.role else None,
        "industry": job.industry if job and job.industry else None,
        "startDate": job.start_date.strftime("%Y-%m-%d") if job and job.start_date else None,
        "incomeRange": job.income_range if job and job.income_range else None,
    }

    # --------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------
    return {
        "selectedRole": profile.registration_role or "member",
        "personal": personal_data,
        "education": education_data,
        "job": job_data,
    }
