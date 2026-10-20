"""Cabinet-address completeness used by the activation checklist."""
import pytest

from app.services.addresses import has_house_number


@pytest.mark.parametrize(
    "address",
    [
        "Москва, ул. Ленина, 5",
        "Москва, ул. Ленина 5",
        "Москва, ул. Ленина, 5А",
        "Москва, ул. Ленина, 5/1",
        "Москва, ул. Ленина, 5-7",
        "Москва, ул. Ленина, д. 5",
        "г Москва, ул Тверская, д 5",
        "Москва, ул. Ленина, вл. 5",
        "Москва, ул. Ленина, 5 стр. 2",
        "Москва, ул. Ленина, 5, кв. 3",
        "Санкт-Петербург, Невский проспект, 10",
    ],
)
def test_address_with_house_is_complete(address):
    assert has_house_number(address) is True


@pytest.mark.parametrize(
    "address",
    [
        None,
        "",
        "   ",
        "Москва",
        "Москва, ул. Ленина",
        "Москва, ул. 1-я Тверская-Ямская",
        "Москва, ул. 1-я Тверская-Ямская, кв. 3",
        "Москва, ул. Ленина, кв. 3",
    ],
)
def test_address_without_house_is_incomplete(address):
    assert has_house_number(address) is False
