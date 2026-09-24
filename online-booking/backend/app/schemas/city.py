from pydantic import BaseModel, ConfigDict


class CityBase(BaseModel):
    country_id: int
    name_ru: str
    name_en: str | None = None
    slug: str
    is_active: bool = True


class CityCreate(CityBase):
    pass


class CityUpdate(BaseModel):
    name_ru: str | None = None
    name_en: str | None = None
    slug: str | None = None
    is_active: bool | None = None


class CityResponse(CityBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
