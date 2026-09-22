from pydantic import BaseModel, ConfigDict


class CountryBase(BaseModel):
    code: str
    name_ru: str
    name_en: str
    phone_prefix: str
    is_active: bool = True


class CountryCreate(CountryBase):
    pass


class CountryUpdate(BaseModel):
    name_ru: str | None = None
    name_en: str | None = None
    phone_prefix: str | None = None
    is_active: bool | None = None


class CountryResponse(CountryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
