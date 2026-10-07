"""鞣坑规则。

- 浸液酸碱度登记：只允许有限数值且落在 0～14，非法值禁止入库。
- 放液门槛：最近一次浸液酸碱度须在 3.5～5.0。
"""

import math

from pits.models import Pit

MIN_PH = 3.5
MAX_PH = 5.0

SAMPLE_MIN_PH = 0.0
SAMPLE_MAX_PH = 14.0


class RuleError(ValueError):
    pass


def assert_valid_sample_ph(ph: float) -> None:
    if not isinstance(ph, (int, float)) or isinstance(ph, bool) or not math.isfinite(ph):
        raise RuleError("酸碱度须为有限数值")
    if ph < SAMPLE_MIN_PH or ph > SAMPLE_MAX_PH:
        raise RuleError(f"酸碱度 {ph} 不合法，须在 {SAMPLE_MIN_PH:g}～{SAMPLE_MAX_PH:g}")


def latest_ph(pit: Pit) -> float | None:
    sample = pit.samples.order_by("-taken_at", "-id").first()
    return None if sample is None else sample.ph


def assert_can_set_status(pit: Pit, new_status: str) -> None:
    allowed = {Pit.STATUS_FILL, Pit.STATUS_TANNING, Pit.STATUS_DRAINED}
    if new_status not in allowed:
        raise RuleError(f"无效状态：{new_status}")
    if new_status != Pit.STATUS_DRAINED:
        return
    ph = latest_ph(pit)
    if ph is None:
        raise RuleError("该坑尚无浸液酸碱记录，不能放液")
    if ph < MIN_PH or ph > MAX_PH:
        raise RuleError(f"最近酸碱度 {ph} 不在 {MIN_PH}～{MAX_PH}，不能放液")
