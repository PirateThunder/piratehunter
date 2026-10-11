"""CRUD потребностей работодателя + LLM-парсинг («мы поняли так») +
подборка (shortlist)."""

from fastapi import APIRouter, HTTPException

from ..auth.dependencies import EmployerUser
from ..companies import service as companies_service
from ..core_client.client import CoreDep, CoreError
from ..database import DbDep
from . import service
from .schemas import NeedIn, NeedOut, NeedParseIn, NeedParseOut, ShortlistOut

router = APIRouter(tags=["employer"])


@router.post(
    "/employer/needs/parse",
    response_model=NeedParseOut,
    summary="Распарсить потребность из свободного текста",
    description="LLM-парсинг raw_text в структуру (spec, grade, стек) "
    "через core-api — экран «мы поняли так» (§7.3, §7.5.1). "
    "Работодатель подтверждает/правит результат и создаёт потребность.",
)
async def parse_need(body: NeedParseIn, user: EmployerUser, core: CoreDep) -> NeedParseOut:
    try:
        parsed = await core.llm_parse_need(body.raw_text)
    except CoreError as e:
        raise HTTPException(502, f"core-api: {e}") from e
    return NeedParseOut.model_validate(parsed)


@router.post(
    "/employer/needs",
    response_model=NeedOut,
    status_code=201,
    summary="Создать потребность",
    description="Если spec_slug не указан — raw_text авто-парсится в core "
    "(best-effort), распознанные spec/grade/stack подставляются; "
    "raw результат парсинга сохраняется в parsed для UI «мы поняли так».",
)
async def create_need(
    body: NeedIn, user: EmployerUser, session: DbDep, core: CoreDep
) -> NeedOut:
    await companies_service.get_company_or_404(session, user.id)
    need = await service.create(session, core, user.id, body)
    return NeedOut.model_validate(need)


@router.get(
    "/employer/needs",
    response_model=list[NeedOut],
    summary="Мои потребности",
)
async def list_needs(user: EmployerUser, session: DbDep) -> list[NeedOut]:
    needs = await service.list_own(session, user.id)
    return [NeedOut.model_validate(n) for n in needs]


@router.get(
    "/employer/needs/{need_id}",
    response_model=NeedOut,
    summary="Потребность по id",
)
async def get_need(
    need_id: str, user: EmployerUser, session: DbDep
) -> NeedOut:
    need = await service.get_own(session, user.id, need_id)
    return NeedOut.model_validate(need)


@router.put(
    "/employer/needs/{need_id}",
    response_model=NeedOut,
    summary="Заменить потребность",
)
async def update_need(
    need_id: str, body: NeedIn, user: EmployerUser, session: DbDep
) -> NeedOut:
    need = await service.update(session, user.id, need_id, body)
    return NeedOut.model_validate(need)


@router.delete(
    "/employer/needs/{need_id}",
    status_code=204,
    summary="Удалить потребность",
)
async def delete_need(
    need_id: str, user: EmployerUser, session: DbDep
) -> None:
    await service.delete(session, user.id, need_id)


@router.get(
    "/employer/needs/{need_id}/shortlist",
    response_model=ShortlistOut,
    summary="Подборка по потребности (с explanation)",
)
async def get_shortlist(
    need_id: str, user: EmployerUser, session: DbDep, core: CoreDep
) -> ShortlistOut:
    """core match → карточки кандидатов (контакты скрыты до accept,
    §7.6) + панель «Почему в подборке» у каждого (§7.5.3)."""
    need, items = await service.shortlist(session, core, user.id, need_id)
    return ShortlistOut(need_id=need.id, results=items)
