from pydantic import BaseModel, ConfigDict


class RequestSchema(BaseModel):
    # Unknown fields are rejected, so clients cannot send role, price or other server-owned values.
    model_config = ConfigDict(extra="forbid")


class ResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
