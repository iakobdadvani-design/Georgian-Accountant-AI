"""Facts about a company, as the rules engine sees them (`company.*`)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Employee
from app.rules.engine import Facts


def company_facts(company: Company, db: Session) -> Facts:
    facts: Facts = {
        "company.legal_form": company.legal_form,
        "company.employee_count": db.scalar(select(func.count()).where(Employee.company_id == company.id)),
    }
    if company.tax_profile is not None:
        facts["company.vat_registered"] = company.tax_profile.vat_registered
        facts["company.tax_regime"] = company.tax_profile.tax_regime.value
        facts["company.has_employees"] = company.tax_profile.has_employees or facts["company.employee_count"] > 0
        facts["company.owns_property"] = company.tax_profile.owns_property
    return facts
