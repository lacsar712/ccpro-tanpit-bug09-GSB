from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from pits.auth import BearerAuth, make_token
from pits.models import Pit, User, Yard
from pits.rules import RuleError, assert_can_set_status, assert_valid_ph, latest_ph

api = NinjaAPI(title="TanPit", urls_namespace="tanpit")
auth = BearerAuth()


class LoginIn(Schema):
    username: str
    password: str


class SampleIn(Schema):
    ph: float


class StatusIn(Schema):
    status: str


def pit_json(pit: Pit, page: int = 1, page_size: int = 3) -> dict:
    rows = list(pit.samples.order_by("-taken_at", "-id"))
    total = len(rows)
    start = max(0, (page - 1) * page_size)
    slice_rows = rows[start : start + page_size]
    return {
        "id": pit.id,
        "code": pit.code,
        "status": pit.status,
        "row": pit.row,
        "col": pit.col,
        "latestPh": latest_ph(pit),
        "sampleCount": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": max(1, (total + page_size - 1) // page_size) if total else 1,
        "ledger": [
            {"id": s.id, "ph": s.ph, "operator": s.operator, "takenAt": s.taken_at.isoformat()}
            for s in slice_rows
        ],
    }


@api.post("/auth/login")
def login(request, payload: LoginIn):
    user = User.objects.filter(username=payload.username).first()
    if user is None or not user.check_password(payload.password):
        raise HttpError(401, "用户名或密码错误")
    return {"access_token": make_token(user.username), "user": {"username": user.username, "role": user.role}}


@api.get("/auth/me", auth=auth)
def me(request):
    user = request.auth
    return {"username": user.username, "role": user.role}


@api.get("/health")
def health(request):
    return {"status": "ok", "service": "TanPit"}


@api.get("/board", auth=auth)
def board(request):
    yard = Yard.objects.prefetch_related("pits__samples").first()
    if yard is None:
        raise HttpError(404, "尚无鞣场")
    pits = sorted(yard.pits.all(), key=lambda p: (p.row, p.col))
    return {"yard": yard.name, "village": yard.village, "pits": [pit_json(p) for p in pits]}


@api.get("/pits/{pit_id}/samples", auth=auth)
def list_samples(request, pit_id: int, page: int = 1):
    pit = Pit.objects.filter(id=pit_id).prefetch_related("samples").first()
    if pit is None:
        raise HttpError(404, "坑不存在")
    return pit_json(pit, page=page)


@api.post("/pits/{pit_id}/samples", auth=auth)
def add_sample(request, pit_id: int, payload: SampleIn):
    pit = Pit.objects.filter(id=pit_id).first()
    if pit is None:
        raise HttpError(404, "坑不存在")
    try:
        assert_valid_ph(payload.ph)
    except RuleError as exc:
        raise HttpError(400, str(exc))
    pit.samples.create(ph=payload.ph, operator=request.auth.username)
    return pit_json(pit, page=1)


@api.post("/pits/{pit_id}/status", auth=auth)
def set_status(request, pit_id: int, payload: StatusIn):
    pit = Pit.objects.filter(id=pit_id).first()
    if pit is None:
        raise HttpError(404, "坑不存在")
    try:
        assert_can_set_status(pit, payload.status)
    except RuleError as exc:
        raise HttpError(400, str(exc))
    pit.status = payload.status
    pit.save(update_fields=["status"])
    return pit_json(pit)
