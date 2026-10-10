"""Canonical seeding helpers - single source of truth for dev/prod scripts.

Replaces 5 divergent copies of geography data/logic (seed_cities,
seed_test_data.seed_geography, fix_production_db.fix_geography,
create_minimal_reviews.ensure_geography, seed_production wrapper)
and 2 copies of review seeding (seed_production.seed_reviews_only,
create_minimal_reviews.ensure_reviews).

Rule: scripts in backend/ root are thin CLI wrappers (deploy calls them
by name); all row-level logic lives here. Every function is idempotent
(safe to re-run on every deploy).
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.city import City
from app.models.client_profile import ClientProfile
from app.models.country import Country
from app.models.review import Review
from app.models.user import User


# --- Canonical geography data (moved from seed_cities.py) ---

COUNTRIES = [
    {"code": "RU", "name_ru": "Россия", "name_en": "Russia", "phone_prefix": "+7"},
    {"code": "BY", "name_ru": "Беларусь", "name_en": "Belarus", "phone_prefix": "+375"},
    {"code": "KZ", "name_ru": "Казахстан", "name_en": "Kazakhstan", "phone_prefix": "+7"},
    {"code": "UZ", "name_ru": "Узбекистан", "name_en": "Uzbekistan", "phone_prefix": "+998"},
    {"code": "AM", "name_ru": "Армения", "name_en": "Armenia", "phone_prefix": "+374"},
    {"code": "AZ", "name_ru": "Азербайджан", "name_en": "Azerbaijan", "phone_prefix": "+994"},
    {"code": "GE", "name_ru": "Грузия", "name_en": "Georgia", "phone_prefix": "+995"},
]

CITIES_BY_COUNTRY = {
    "RU": [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
        "Нижний Новгород", "Челябинск", "Самара", "Омск", "Ростов-на-Дону",
        "Уфа", "Красноярск", "Воронеж", "Пермь", "Волгоград",
        "Краснодар", "Саратов", "Тюмень", "Сочи", "Астрахань",
        "Тольятти", "Ижевск", "Барнаул", "Иркутск", "Хабаровск",
        "Ярославль", "Владивосток", "Махачкала", "Томск", "Оренбург",
        "Кемерово", "Новокузнецк", "Рязань", "Тольятти", "Тула",
        "Киров", "Чебоксары", "Калининград", "Ульяновск", "Орёл",
        "Севастополь", "Курск", "Смоленск", "Тверь", "Белгород",
        "Стерлитамак", "Магнитогорск", "Липецк", "Саранск", "Тамбов",
        "Пенза", "Ставрополь", "Улан-Удэ", "Калуга", "Петрозаводск",
        "Кострома", "Вологда", "Великий Новгород", "Мурманск", "Абакан",
        "Нальчик", "Братск", "Дербент", "Псков", "Каспийск",
        "Йошкар-Ола", "Южно-Сахалинск", "Элиста", "Черкесск", "Анадырь",
        "Грозный", "Магас", "Кызыл", "Петропавловск-Камчатский",
        "Биробиджан", "Салехард", "Иоакимо-Орловск", "Нарьян-Мар",
        "Горно-Алтайск", "Элиста", "Благовещенск", "Нарьян-Мар",
        "Ханты-Мансийск", "Чита", "Якутск", "Югорск", "Нефтеюганск",
        "Невинномысск", "Балашиха", "Коммунар", "Люберцы", "Подольск",
        "Королёв", "Мытищи", "Химки", "Долгопрудный", "Жуковский",
        "Коломна", "Серпухов", "Одинцово", "Солнечногорск", "Домодедово",
        "Видное", "Щёлково", "Красногорск", "Бронницы", "Ногинск",
        "Раменское", "Истра", "Руза", "Волоколамск", "Лотошино",
        "Луховицы", "Пушкино", "Дзержинский", "Куровское", "Электросталь",
        "Ликино-Дулёво", "Дрезна", "Орехово-Зуево", "Шатура", "Клин",
        "Зеленоград", "Талдом", "Яхрома", "Ивантеевка", "Реутов",
        "Белоозёрский", "Котельники", "Железнодорожный", "Сычёво",
        "Дубна", "Тверь", "Конаково", "Калининград", "Светлогорск",
        "Пионерский", "Зеленоградск", "Светлый", "Гвардейск", "Черняховск",
        "Правдинск", "Гусев", "Нестеров", "Озёрск", "Кравино",
        "Славск", "Мамонтовка", "Балтийск", "Приморск", "Уст-Камчатск",
        "Александров", "Арзамас", "Ардатов", "Богородск", "Бор",
        "Ветлуга", "Володарск", "Вознесенское", "Выкса", "Городец",
        "Дивеево", "Дзержинск", "Заволжье", "Знаменка", "Иванаево",
        "Кстово", "Лысково", "Макарьев", "Маркс", "Муром",
        "Навашино", "Нижние Серги", "Новомосковск", "Первомайск", "Перевоз",
        "Пильна", "Починки", "Саров", "Сеченово", "Сокольники",
        "Тонкино", "Урень", "Чкаловск", "Шахунья", "Александровск",
        "Алексеевка", "Артемовский", "Асбест", "Березовский", "Бисерть",
        "Верхнеуральск", "Верхняя Пышма", "Верхняя Салда", "Верхняя Тура", "Волчанск",
        "Далматово", "Дегтярск", "Евдокимово", "Заречный", "Златоуст",
        "Ивдель", "Ирбит", "Камышлов", "Карпинск", "Качканар",
        "Краснотурьинск", "Красноуфимск", "Кувшиново", "Кушва", "Кыштым",
        "Лесной", "Магнитогорск", "Миасс", "Миньяр", "Невинномысск",
        "Новолялинск", "Новоуральск", "Озерск", "Октябрьский", "Отрадный",
        "Полковниково", "Пыталово", "Сатка", "Свердловск", "Серов",
        "Сим", "Слободской", "Сосновка", "Спецохрана", "Старобинск",
        "Суерка", "Тавда", "Талица", "Талицы", "Таганай",
        "Троицк", "Тура", "Туринск", "Уктус", "Упорово",
        "Уральск", "Усть-Катав", "Усть-Кым", "Фершампенуаз", "Харабали",
        "Харовск", "Хасавюрт", "Хилок", "Чердынь", "Черняховск",
        "Чусовой", "Шадринск", "Шахты", "Шарья", "Шарыпово",
        "Шарыпово", "Шатура", "Шебекино", "Шемышейка", "Шенкурск",
        "Шилка", "Шуя", "Щигры", "Щучье", "Энгельс",
        "Юрья", "Ядрин", "Якиманка", "Янаул", "Ярцево",
        "Ярославль", "Яхрома",
        # --- Batch 2: райцентры и города 50k+, пропущенные в первой версии ---
        # (тамбовский кластер + крупные пропуски; дубликаты сид пропускает сам)
        "Мичуринск", "Рассказово", "Моршанск", "Котовск", "Уварово",
        "Ковров", "Гусь-Хрустальный", "Кольчугино", "Вязники", "Собинка",
        "Димитровград", "Инза", "Сенгилей",
        "Нефтекамск", "Октябрьский", "Туймазы", "Белорецк", "Ишимбай",
        "Кумертау", "Сибай", "Бирск", "Учалы", "Дюртюли",
        "Батайск", "Новочеркасск", "Таганрог", "Азов", "Каменск-Шахтинский",
        "Гуково", "Донецк", "Миллерово", "Морозовск", "Сальск",
        "Ангарск", "Усолье-Сибирское", "Черемхово", "Шелехов", "Тулун",
        "Северск", "Бийск", "Рубцовск", "Новоалтайск", "Заринск",
        "Ленинск-Кузнецкий", "Междуреченск", "Прокопьевск", "Киселёвск",
        "Юрга", "Анжеро-Судженск", "Белово", "Осинники", "Мыски",
        "Минусинск", "Черногорск", "Саяногорск", "Назарово", "Канск",
        "Лесосибирск", "Ачинск", "Железногорск", "Зеленогорск", "Норильск",
        "Артём", "Находка", "Уссурийск", "Спасск-Дальний", "Партизанск",
        "Сергиев Посад", "Елец", "Ливны", "Мценск",
        "Зеленодольск", "Альметьевск", "Нижнекамск", "Бугульма", "Чистополь",
        "Елабуга", "Лениногорск", "Нурлат", "Менделеевск",
        "Салават", "Орск", "Новотроицк", "Бузулук", "Медногорск",
        "Кинешма", "Тейково", "Вичуга", "Фурманов", "Кохма",
        "Новомосковск", "Щёкино", "Донской", "Узловая", "Ефремов",
        "Чапаевск", "Отрадный", "Похвистнево", "Жигулёвск", "Кинель",
    ],
    "BY": [
        "Минск", "Гомель", "Могилёв", "Витебск", "Гродно", "Брест",
        "Бобруйск", "Барановичи", "Борисов", "Пинск", "Орша",
        "Речица", "Солигорск", "Слуцк", "Мозырь", "Новополоцк",
        "Костюковичи", "Волковыск", "Жлобин", "Смолевичи", "Калинковичи",
    ],
    "KZ": [
        "Алматы", "Астана", "Шымкент", "Караганда", "Актау",
        "Атырау", "Павлодар", "Усть-Каменогорск", "Туркестан", "Петропавл",
        "Костанай", "Кызылорда", "Темиртау", "Талдыкорган", "Рудный",
        "Кокшетау", "Семей", "Жезказган", "Экибастуз", "Туркестан",
    ],
    "UZ": [
        "Ташкент", "Самарканд", "Андижан", "Бухара", "Наманган",
        "Навои", "Коканд", "Фергана", "Маргилан", "Туркестан",
        "Чирчик", "Хива", "Ургенч", "Кашкадарья", "Джизак",
        "Худжанд", "Пенджикент", "Термез", "Гулистан", "Бухара",
    ],
    "AM": [
        "Ереван", "Гюмри", "Ванадзор", "Дилижан", "Армавир",
        "Арташат", "Ошакан", "Храздан", "Масис", "Апаран",
    ],
    "AZ": [
        "Баку", "Гянджа", "Сумгаит", "Мингечаур", "Ленкорань",
        "Шеки", "Ширван", "Нахичевань", "Хырдыран", "Сабунчи",
        "Сиязань", "Агджабеди", "Агдам", "Агдаш", "Али Байрамлы",
    ],
    "GE": [
        "Тбилиси", "Батуми", "Кутаиси", "Поти", "Рустави",
        "Зугдиди", "Гори", "Хашури", "Ахалцихе", "Ахалкалаки",
        "Озургети", "Сенаки", "Чиатура", "Телави", "Казбеги",
    ],
}


# ─── Main ─────────────────────────────────────────────────────────────

REVIEW_COMMENTS = [
        "Отличный мастер! Рекомендую!",
        "Очень довольна результатом",
        "Буду приходить ещё",
        "Профессиональный подход",
        "Всё понравилось, спасибо!",
        "Хороший сервис, приятная атмосфера",
        "Мастер — золото!",
        "Быстро и качественно",
]


async def ensure_geography(session: AsyncSession) -> tuple:
    """Idempotent top-up of countries/cities. Returns (new_countries, new_cities)."""
    new_countries = 0
    for c_data in COUNTRIES:
        existing = await session.execute(
            select(Country).where(Country.code == c_data["code"])
        )
        if existing.scalar_one_or_none():
            continue
        session.add(Country(**c_data))
        new_countries += 1
    await session.commit()

    result = await session.execute(select(Country))
    country_map = {c.code: c for c in result.scalars().all()}

    new_cities = 0
    for code, city_names in CITIES_BY_COUNTRY.items():
        country = country_map.get(code)
        if not country:
            print(f"  Country {code} not found, skipping cities")
            continue
        for name in city_names:
            slug = name.lower().replace(" ", "-").replace("'", "")
            existing = await session.execute(
                select(City).where(
                    City.country_id == country.id,
                    City.slug == slug,
                )
            )
            if existing.scalar_one_or_none():
                continue
            session.add(City(
                country_id=country.id,
                name_ru=name,
                name_en=name,  # fallback
                slug=slug,
            ))
            new_cities += 1
    await session.commit()
    print(f"  Geography ready: +{new_countries} countries, +{new_cities} cities")
    return new_countries, new_cities


async def ensure_reviews(session: AsyncSession, seed: int = 42) -> int:
    """Create reviews for completed appointments (idempotent). Returns count.

    Fixed version of the two old copies: no lazy relationship access
    (appt.client_profile.user_id raised MissingGreenlet under async),
    explicit joins instead; raw text('count(*)') replaced with func.count.
    """
    random.seed(seed)
    now = datetime.now(timezone.utc)

    count = (await session.execute(select(func.count(Review.id)))).scalar() or 0
    if count:
        print(f"  Reviews already exist ({count} records). Skipping.")
        return 0

    rows = (await session.execute(
        select(Appointment, User.name, User.phone)
        .join(ClientProfile, Appointment.client_id == ClientProfile.id)
        .join(User, ClientProfile.user_id == User.id)
        .where(Appointment.status == "completed")
        .order_by(Appointment.id)
    )).all()

    if not rows:
        print("  No completed appointments found. Skipping reviews.")
        return 0

    made = 0
    for appt, client_name, client_phone in rows:
        if random.random() > 0.3:  # 70% of completed get reviews
            review = Review(
                appointment_id=appt.id,
                master_id=appt.master_id,
                client_name=client_name or "\u0410\u043d\u043e\u043d\u0438\u043c",
                client_phone=client_phone or "+7***",
                rating=random.choices([4, 5], weights=[0.3, 0.7])[0],
                comment=random.choice(REVIEW_COMMENTS),
                is_published=True,
                created_at=appt.appointment_date + timedelta(days=random.randint(1, 7)),
            )
            session.add(review)
            made += 1

    await session.commit()
    print(f"  Created {made} reviews")
    return made
