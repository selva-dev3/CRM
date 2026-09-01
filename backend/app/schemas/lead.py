from pydantic import BaseModel, EmailStr


class LeadBase(BaseModel):
    title: str
    company: str
    contact_name: str
    email: EmailStr
    phone: str | None = None
    status: str = "New"


class LeadCreate(LeadBase):
    pass


class LeadResponse(LeadBase):
    id: str
    score: float
    organization_id: str

    class Config:
        from_attributes = True
