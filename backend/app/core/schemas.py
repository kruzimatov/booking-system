from datetime import date, datetime
from typing import Annotated, Any, ClassVar, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    StringConstraints,
    model_validator,
)

# Dates far outside this range are never valid here, and near date.max the timezone and
# day arithmetic would overflow into a 500. Checked on the calendar year before any maths.
EARLIEST_YEAR, LATEST_YEAR = 2000, 2100


def _within_supported_years[DateT: (date, datetime)](value: DateT) -> DateT:
    if not EARLIEST_YEAR <= value.year <= LATEST_YEAR:
        raise ValueError(f"Year must be between {EARLIEST_YEAR} and {LATEST_YEAR}")
    return value


BoundedDatetime = Annotated[AwareDatetime, AfterValidator(_within_supported_years)]
BoundedDate = Annotated[date, AfterValidator(_within_supported_years)]

NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]
NameText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
PhoneText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=32)]


class RequestSchema(BaseModel):
    # Unknown fields are rejected, so clients cannot send role, price or other server-owned values.
    model_config = ConfigDict(extra="forbid")


class PatchSchema(RequestSchema):
    """Partial update: only the fields sent are changed."""

    # Fields backed by NOT NULL columns: they may be omitted, but not set to null.
    NOT_NULL: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> Self:
        nulls = sorted(
            name
            for name in self.NOT_NULL
            if name in self.model_fields_set and getattr(self, name) is None
        )
        if nulls:
            raise ValueError(f"These fields cannot be null: {', '.join(nulls)}")
        return self

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class ResponseSchema(BaseModel):
    # Fields with defaults are still always present in responses, so mark them required in
    # the OpenAPI schema; the generated TypeScript types then need no undefined checks.
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


class Page[ItemT](BaseModel):
    items: list[ItemT]
    total: int
    page: int
    size: int
