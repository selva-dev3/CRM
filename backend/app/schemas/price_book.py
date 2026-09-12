from pydantic import BaseModel, Field, field_validator, model_validator


class PriceBookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Price book name is required")
        return value.strip()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return value.upper()


class PriceBookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("name", "currency", "is_default", "is_active", mode="before")
    @classmethod
    def reject_null_required_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Price book name is required")
        return value.strip() if value else value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is not None and not value.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return value.upper() if value else value

    @model_validator(mode="after")
    def reject_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one price book field is required")
        return self


class PriceBookResponse(BaseModel):
    id: str
    name: str
    currency: str
    is_default: bool
    is_active: bool
    product_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class PriceBookContextResponse(BaseModel):
    currency: str


class PriceBookEntryUpsert(BaseModel):
    unit_price: float = Field(ge=0, allow_inf_nan=False)
    is_active: bool = True


class PriceBookEntryResponse(BaseModel):
    id: str
    price_book_id: str
    product_id: str
    product_name: str
    product_sku: str
    unit_price: float
    is_active: bool
