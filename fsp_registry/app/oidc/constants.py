"""Детерминированный набор синтетических личностей FSP ID (20 штук).

По PRD §8.3 часть личностей имеет богатую историю достижений, часть —
404-профиль (распределение задаёт генератор profiles по хэшу fsp_id).
ПДн выдуманные, совпадения случайны; домен почты — .example.
"""

from .schemas import FspIdentity

IDENTITIES: tuple[FspIdentity, ...] = (
    FspIdentity(fsp_id="fsp_001", name="Иван Петров", email="ivan.petrov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_002", name="Мария Соколова", email="maria.sokolova@fsp-id.example"),
    FspIdentity(fsp_id="fsp_003", name="Алексей Смирнов", email="alexey.smirnov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_004", name="Анна Кузнецова", email="anna.kuznetsova@fsp-id.example"),
    FspIdentity(fsp_id="fsp_005", name="Дмитрий Волков", email="dmitry.volkov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_006", name="Елена Морозова", email="elena.morozova@fsp-id.example"),
    FspIdentity(fsp_id="fsp_007", name="Сергей Новиков", email="sergey.novikov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_008", name="Ольга Лебедева", email="olga.lebedeva@fsp-id.example"),
    FspIdentity(fsp_id="fsp_009", name="Никита Орлов", email="nikita.orlov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_010", name="Дарья Захарова", email="darya.zakharova@fsp-id.example"),
    FspIdentity(fsp_id="fsp_011", name="Артём Григорьев", email="artem.grigoriev@fsp-id.example"),
    FspIdentity(fsp_id="fsp_012", name="Полина Ефимова", email="polina.efimova@fsp-id.example"),
    FspIdentity(fsp_id="fsp_013", name="Максим Тарасов", email="maxim.tarasov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_014", name="Софья Белова", email="sofya.belova@fsp-id.example"),
    FspIdentity(fsp_id="fsp_015", name="Кирилл Комаров", email="kirill.komarov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_016", name="Виктория Павлова", email="viktoria.pavlova@fsp-id.example"),
    FspIdentity(fsp_id="fsp_017", name="Роман Семёнов", email="roman.semenov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_018", name="Алина Киселёва", email="alina.kiseleva@fsp-id.example"),
    FspIdentity(fsp_id="fsp_019", name="Егор Макаров", email="egor.makarov@fsp-id.example"),
    FspIdentity(fsp_id="fsp_020", name="Юлия Андреева", email="yulia.andreeva@fsp-id.example"),
)

IDENTITY_BY_ID: dict[str, FspIdentity] = {i.fsp_id: i for i in IDENTITIES}

# демо-пользователь «одним кликом» на форме authorize
DEMO_FSP_ID = "fsp_001"
