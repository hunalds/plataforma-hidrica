"""Evaluación de alertas tempranas (M9).

Disparadores (sección 5, M9):
  1. OBSERVADA: la última cota medida cruza un umbral (bajo o alto).
  2. PROYECTADA: la predicción indica que se cruzará un umbral en los próximos 30 días.
Severidades: informativa, alerta, crítica. Sentidos: escasez e inundación/alivio.
Sin duplicados: una alerta por (embalse, tipo, umbral) mientras siga activa; si cambia se actualiza
y, si sube de severidad, se vuelve a notificar. Cuando la condición desaparece se resuelve.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import utcnow
from app.models.alert import SEVERITIES, Alert, AlertDelivery, AlertRecipient
from app.models.measurement import DailyMeasurement
from app.models.reservoir import Reservoir
from app.services.notifications import NotificationChannel

log = get_logger(__name__)
RANK = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass(frozen=True)
class Condition:
    kind: str  # observada | proyectada
    direction: str
    severity: str
    threshold: str
    threshold_level: float
    title: str
    message: str
    value: float | None
    event_day: date
    horizon_days: int | None = None
    probability: float | None = None

    @property
    def key_suffix(self) -> str:
        return f"{self.kind}:{self.direction}"


def _fmt(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def thresholds_for(r: Reservoir) -> dict[str, float]:
    """Umbrales del Ingeniero; si faltan, los oficiales (volumen muerto y nivel normal)."""
    t = r.thresholds
    out = {
        "low_critical": t.low_critical if t and t.low_critical is not None else r.dead_level,
        "spill_level": t.spill_level if t and t.spill_level is not None else r.normal_level,
    }
    if t and t.low_alert is not None:
        out["low_alert"] = t.low_alert
    if t and t.high_alert is not None:
        out["high_alert"] = t.high_alert
    return out


def observed_conditions(session: Session, r: Reservoir) -> list[Condition]:
    last = session.scalars(
        select(DailyMeasurement)
        .where(DailyMeasurement.reservoir_code == r.code)
        .order_by(DailyMeasurement.day.desc())
        .limit(1)
    ).first()
    if last is None:
        return []
    th, lvl = thresholds_for(r), last.level_m
    when = last.day.strftime("%d/%m/%Y")
    if lvl <= th["low_critical"]:
        return [Condition("observada", "escasez", "critica", "low_critical", th["low_critical"], "Nivel bajo crítico alcanzado",
                          f"La cota del {when} es {_fmt(lvl)} m, igual o menor al nivel crítico ({_fmt(th['low_critical'])} m). "
                          "Se recomienda aplicar las maniobras de restricción previstas.", lvl, last.day)]  # fmt: skip
    if "low_alert" in th and lvl <= th["low_alert"]:
        return [Condition("observada", "escasez", "alerta", "low_alert", th["low_alert"], "Nivel bajo de alerta alcanzado",
                          f"La cota del {when} es {_fmt(lvl)} m, igual o menor al nivel de alerta ({_fmt(th['low_alert'])} m).",
                          lvl, last.day)]  # fmt: skip
    if lvl > th["spill_level"]:
        return [Condition("observada", "inundacion_alivio", "critica", "spill_level", th["spill_level"], "El embalse está aliviando",
                          f"La cota del {when} es {_fmt(lvl)} m, por encima del nivel de alivio ({_fmt(th['spill_level'])} m). "
                          "Vigile el control de crecidas aguas abajo.", lvl, last.day)]  # fmt: skip
    if "high_alert" in th and lvl >= th["high_alert"]:
        return [Condition("observada", "inundacion_alivio", "alerta", "high_alert", th["high_alert"], "Nivel alto de alerta alcanzado",
                          f"La cota del {when} es {_fmt(lvl)} m, igual o mayor al nivel alto de alerta ({_fmt(th['high_alert'])} m).",
                          lvl, last.day)]  # fmt: skip
    return []


def projected_conditions(forecast: dict, settings: Settings) -> list[Condition]:
    """A partir de la proyección (probabilidad de cruzar cada umbral a 30 días)."""
    h = settings.alert_projection_days
    p_min = settings.alert_probability
    origin = date.fromisoformat(forecast["origin"])
    probs = {(p["threshold"], p["horizon_days"]): p for p in forecast["probabilities"]}
    horizon = next((x for x in forecast["horizons"] if x["horizon_days"] == h), None)
    out: list[Condition] = []

    def pct(p: float) -> str:
        return f"{round(p * 100)} %"

    # Escasez: el umbral más grave con probabilidad suficiente
    for key, severity, label in (
        ("low_critical", "critica", "nivel bajo crítico"),
        ("dead_level", "critica", "volumen muerto"),
        ("low_alert", "alerta", "nivel bajo de alerta"),
    ):
        p = probs.get((key, h))
        if p and p["probability"] >= p_min:
            out.append(Condition("proyectada", "escasez", severity, key, p["level"], f"Se proyecta {label} en {h} días",
                                 f"El modelo estima {pct(p['probability'])} de probabilidad de que la cota baje de {_fmt(p['level'])} m "
                                 f"antes del {(origin + timedelta(days=h)).strftime('%d/%m/%Y')}. Alerta temprana para planificar maniobras.",
                                 p["probability"], origin + timedelta(days=h), h, p["probability"]))  # fmt: skip
            break
    else:
        p = probs.get(("low_alert", h)) or probs.get(("low_critical", h))
        if p and p["probability"] >= 0.2:
            out.append(Condition("proyectada", "escasez", "informativa", p["threshold"], p["level"], f"Riesgo de nivel bajo en {h} días",
                                 f"Probabilidad de {pct(p['probability'])} de bajar de {_fmt(p['level'])} m en {h} días. Seguimiento recomendado.",
                                 p["probability"], origin + timedelta(days=h), h, p["probability"]))  # fmt: skip
    # Alivio / inundación
    if horizon and horizon["spill_probability"] >= p_min:
        out.append(Condition("proyectada", "inundacion_alivio", "alerta", "spill_level", forecast["normal_level"], f"Se proyecta alivio en {h} días",
                             f"Probabilidad de {pct(horizon['spill_probability'])} de que el embalse alivie en los próximos {h} días. "
                             "Prepare el control de crecidas.", horizon["spill_probability"], origin + timedelta(days=h), h,
                             horizon["spill_probability"]))  # fmt: skip
    return out


def _recipients(session: Session, code: str, severity: str) -> list[AlertRecipient]:
    rows = session.scalars(select(AlertRecipient).where(AlertRecipient.active.is_(True))).all()
    return [
        r
        for r in rows
        if (r.reservoir_code in (None, code)) and RANK[severity] >= RANK.get(r.min_severity, 1)
    ]


def notify(
    session: Session, alert: Alert, reservoir_name: str, channels: dict[str, NotificationChannel]
) -> int:
    sent = 0
    for rec in _recipients(session, alert.reservoir_code, alert.severity):
        channel = channels.get(rec.channel)
        if channel is None:
            continue
        result = channel.send(alert, reservoir_name, rec.target)
        session.add(
            AlertDelivery(
                alert_id=alert.id,
                channel=rec.channel,
                recipient=f"{rec.name} <{rec.target}>",
                status=result.status,
                detail=result.detail,
                severity=alert.severity,
            )
        )
        sent += result.status == "enviada"
    return sent


def evaluate(
    session: Session,
    settings: Settings,
    codes: list[str],
    channels: dict[str, NotificationChannel],
    forecast_fn: Callable[[str], dict] | None = None,
) -> dict[str, dict[str, int]]:
    """Evalúa los embalses, crea/actualiza/resuelve alertas y notifica. Devuelve conteos por embalse."""
    summary: dict[str, dict[str, int]] = {}
    for code in codes:
        r = session.get(Reservoir, code)
        if r is None:
            continue
        conditions = observed_conditions(session, r)
        if forecast_fn is not None:
            try:
                conditions += projected_conditions(forecast_fn(code), settings)
            except Exception as exc:  # noqa: BLE001 — sin modelo o sin datos: solo alertas observadas
                log.info("alerts_no_forecast", reservoir=code, reason=str(exc)[:120])
        active = {
            a.dedup_key: a
            for a in session.scalars(
                select(Alert).where(Alert.reservoir_code == code, Alert.resolved_at.is_(None))
            )
        }
        stats = {"nuevas": 0, "actualizadas": 0, "resueltas": 0, "notificaciones": 0}
        seen = set()
        for c in conditions:
            key = f"{code}:{c.key_suffix}"
            seen.add(key)
            existing = active.get(key)
            if existing is None:
                a = Alert(reservoir_code=code, dedup_key=key, kind=c.kind, direction=c.direction, severity=c.severity, threshold=c.threshold,
                          threshold_level=c.threshold_level, title=c.title, message=c.message, value=c.value, horizon_days=c.horizon_days,
                          probability=c.probability, event_day=c.event_day)  # fmt: skip
                session.add(a)
                session.flush()
                stats["nuevas"] += 1
                stats["notificaciones"] += notify(session, a, r.name, channels)
            else:
                escalated = RANK[c.severity] > RANK[existing.severity]
                for field in (
                    "severity",
                    "threshold",
                    "threshold_level",
                    "title",
                    "message",
                    "value",
                    "horizon_days",
                    "probability",
                    "event_day",
                ):
                    setattr(existing, field, getattr(c, field))
                existing.updated_at = utcnow()
                stats["actualizadas"] += 1
                if escalated:
                    stats["notificaciones"] += notify(session, existing, r.name, channels)
        for key, a in active.items():
            if key not in seen:
                a.resolved_at = utcnow()
                stats["resueltas"] += 1
        session.commit()
        summary[code] = stats
    return summary
