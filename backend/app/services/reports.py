"""Reportes (M10): datos tabulares + exportación a PDF, Excel, CSV, PNG, GeoJSON y KML.

Cada reporte se construye como un `Report` (título, subtítulo, tablas, gráfica opcional y notas);
los renderizadores lo convierten al formato pedido. Así todos los formatos muestran lo mismo.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.measurements import _book, _status
from app.models.alert import Alert
from app.models.measurement import DailyMeasurement
from app.models.reservoir import Reservoir
from app.services.curves import CurveRangeError
from app.services.hydro_calcs import M3S_TO_HM3_PER_DAY

LIGHT_LABEL = {"verde": "Normal", "amarillo": "Alerta", "rojo": "Crítico / alivio", "gris": "Sin datos"}
FORMATS = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "png": "image/png",
    "geojson": "application/geo+json",
    "kml": "application/vnd.google-earth.kml+xml",
}


@dataclass
class Report:
    title: str
    subtitle: str
    tables: list[tuple[str, pd.DataFrame]]
    chart: Callable[[], bytes] | None = None  # PNG
    notes: list[str] = field(default_factory=list)
    geo: dict | None = None  # FeatureCollection para GeoJSON/KML
    filename: str = "reporte"


class ReportError(ValueError):
    pass


# ------------------------------------------------------------------ utilidades


def _series(session: Session, r: Reservoir, start: date, end: date) -> pd.DataFrame:
    """Serie diaria con cálculos M12 (cota, volumen, útil, disponibilidad, reserva)."""
    rows = session.scalars(
        select(DailyMeasurement)
        .where(
            DailyMeasurement.reservoir_code == r.code,
            DailyMeasurement.day >= start,
            DailyMeasurement.day <= end,
        )
        .order_by(DailyMeasurement.day)
    ).all()
    book = _book(session, r.code)
    out = []
    for m in rows:
        rec = {
            "Fecha": m.day,
            "Cota (m)": m.level_m,
            "Volumen (hm³)": m.volume_hm3,
            "Entrada (m³/s)": m.inflow_m3s,
            "Salida (m³/s)": m.outflow_m3s,
            "Gasto ecológico (m³/s)": m.eco_flow_m3s,
        }
        curve = book.for_day(m.day)
        if curve:
            _, interp = curve
            try:
                dead, normal = interp.volume_at(r.dead_level), interp.volume_at(r.normal_level)
                v = m.volume_hm3 if m.volume_hm3 is not None else interp.volume_at(m.level_m)
                useful = max(0.0, v - dead)
                daily_out = ((m.outflow_m3s or 0) + (m.eco_flow_m3s or 0)) * M3S_TO_HM3_PER_DAY
                rec.update(
                    {
                        "Volumen útil (hm³)": round(useful, 3),
                        "Disponibilidad (%)": round(useful / (normal - dead) * 100, 1),
                        "Días de reserva": round(useful / daily_out) if daily_out else None,
                    }
                )
            except CurveRangeError:
                pass
        out.append(rec)
    return pd.DataFrame(out)


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return buf.getvalue()


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _visible(session: Session, codes: set[str] | None) -> list[Reservoir]:
    stmt = select(Reservoir).order_by(Reservoir.name)
    if codes is not None:
        stmt = stmt.where(Reservoir.code.in_(codes))
    return list(session.scalars(stmt))


# ------------------------------------------------------------------ reportes


def bulletin(session: Session, visible: set[str] | None, day: date | None = None) -> Report:
    """Boletín diario de estado (inspirado en el Balance Hídrico diario de MINAGUAS)."""
    rows, features = [], []
    ref_day = day or session.scalar(select(func.max(DailyMeasurement.day))) or date.today()
    for r in _visible(session, visible):
        st = _status(session, r, ref_day)
        prev = session.scalar(
            select(DailyMeasurement.level_m).where(
                DailyMeasurement.reservoir_code == r.code,
                DailyMeasurement.day == (st.last_day or ref_day) - timedelta(days=1),
            )
        )
        rows.append(
            {
                "Embalse": r.name,
                "Fecha del dato": st.last_day,
                "Cota (m)": st.level_m,
                "Cambio 24 h (m)": round(st.level_m - prev, 2)
                if st.level_m is not None and prev is not None
                else None,
                "Volumen (hm³)": st.volume_hm3,
                "Volumen útil (hm³)": st.useful_volume_hm3,
                "Disponibilidad (%)": st.availability_pct,
                "Días de reserva": st.reserve_days,
                "Entrada (m³/s)": st.inflow_m3s,
                "Salida (m³/s)": st.outflow_m3s,
                "Gasto ecológico (m³/s)": st.eco_flow_m3s,
                "Alivio (hm³)": st.spill_hm3,
                "Estado": LIGHT_LABEL.get(st.light, st.light),
            }
        )
        geom = session.scalar(select(func.ST_AsGeoJSON(Reservoir.geom, 6)).where(Reservoir.code == r.code))
        if geom:
            props = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in rows[-1].items()}
            features.append(
                {"type": "Feature", "properties": {"codigo": r.code, **props}, "geometry": json.loads(geom)}
            )
    df = pd.DataFrame(rows)
    totals = df[["Volumen (hm³)", "Volumen útil (hm³)"]].sum(numeric_only=True)
    notes = [
        f"Volumen total almacenado: {totals.get('Volumen (hm³)', 0):.1f} hm³ · volumen útil total: {totals.get('Volumen útil (hm³)', 0):.1f} hm³.",
        "Disponibilidad = volumen útil / capacidad útil. Días de reserva = volumen útil / (extracción + gasto ecológico). Fórmulas por validar (P-09 a P-11).",
    ]

    def chart() -> bytes:
        plt = _plt()
        fig, ax = plt.subplots(figsize=(7, 3))
        d = df.dropna(subset=["Disponibilidad (%)"])
        ax.barh(d["Embalse"], d["Disponibilidad (%)"], color="#2a78d6")
        ax.axvline(100, color="#52514e", ls="--", lw=1)
        ax.set_xlabel("Disponibilidad (%)")
        ax.set_title("Disponibilidad por embalse")
        for y, v in enumerate(d["Disponibilidad (%)"]):
            ax.text(v + 1, y, f"{v:.1f} %", va="center", fontsize=9)
        return _png(fig)

    return Report(
        title="Boletín diario de embalses",
        subtitle=f"Balance hídrico · estado al {ref_day.strftime('%d/%m/%Y')}",
        tables=[("Estado por embalse", df)],
        chart=chart,
        notes=notes,
        geo={"type": "FeatureCollection", "features": features},
        filename=f"boletin_{ref_day.isoformat()}",
    )


def prediction(session: Session, forecast: dict, reservoir: Reservoir) -> Report:
    h = pd.DataFrame(
        [
            {
                "Horizonte (días)": x["horizon_days"],
                "Fecha": x["date"],
                "Cota esperada (m)": x["level_p50"],
                "Cota mínima probable (m)": x["level_p10"],
                "Cota máxima probable (m)": x["level_p90"],
                "Volumen útil (hm³)": x["useful_volume_p50"],
                "Disponibilidad (%)": x["availability_pct_p50"],
                "Días de reserva": x["reserve_days_p50"],
                "Prob. de alivio (%)": round(x["spill_probability"] * 100),
            }
            for x in forecast["horizons"]
        ]
    )
    probs = pd.DataFrame(
        [
            {
                "Umbral": p["label"],
                "Cota (m)": p["level"],
                "Sentido": p["direction"],
                "Horizonte (días)": p["horizon_days"],
                "Probabilidad (%)": round(p["probability"] * 100),
            }
            for p in forecast["probabilities"]
        ]
    )
    daily = pd.DataFrame(forecast["days"]).rename(
        columns={
            "day": "Fecha",
            "level_p10": "Cota p10 (m)",
            "level_p50": "Cota p50 (m)",
            "level_p90": "Cota p90 (m)",
            "volume_p10": "Volumen p10",
            "volume_p50": "Volumen p50",
            "volume_p90": "Volumen p90",
        }
    )

    def chart() -> bytes:
        plt = _plt()
        hist = _series(
            session,
            reservoir,
            date.fromisoformat(forecast["origin"]) - timedelta(days=180),
            date.fromisoformat(forecast["origin"]),
        )
        fig, ax = plt.subplots(figsize=(8, 3.6))
        if len(hist):
            ax.plot(
                pd.to_datetime(hist["Fecha"]), hist["Cota (m)"], color="#2a78d6", lw=2, label="Cota observada"
            )
        d = pd.to_datetime(daily["Fecha"])
        ax.fill_between(
            d, daily["Cota p10 (m)"], daily["Cota p90 (m)"], color="#eb6834", alpha=0.2, label="Banda 80 %"
        )
        ax.plot(d, daily["Cota p50 (m)"], color="#eb6834", lw=2, ls="--", label="Proyección")
        for label, lvl in forecast["thresholds"].items():
            ax.axhline(lvl, color="#52514e", ls=":", lw=1)
            ax.text(d.iloc[-1], lvl, f" {label}", va="center", fontsize=7, color="#52514e")
        ax.set_ylabel("Cota (m.s.n.m.)")
        ax.legend(loc="lower left", fontsize=8)
        ax.set_title(f"Proyección a 90 días · {reservoir.name}")
        return _png(fig)

    return Report(
        title=f"Predicción · Embalse {reservoir.name}",
        subtitle=f"Desde el {forecast['origin']} · modelo {forecast['model']['kind']} (error medio {forecast['model']['score_mae_hm3']} hm³)",
        tables=[
            ("Resumen por horizonte", h),
            ("Probabilidad de cruzar umbrales", probs),
            ("Trayectoria diaria", daily),
        ],
        chart=chart,
        notes=[
            f"Fuente de datos del modelo: {forecast['model']['data_source']}.",
            "La banda contiene el valor real 8 de cada 10 veces según el backtesting.",
        ],
        filename=f"prediccion_{reservoir.code.lower()}_{forecast['origin']}",
    )


def historical(session: Session, r: Reservoir, a: tuple[date, date], b: tuple[date, date]) -> Report:
    """Histórico comparativo entre dos períodos de un embalse."""
    sa, sb = _series(session, r, *a), _series(session, r, *b)
    if sa.empty or sb.empty:
        raise ReportError("Uno de los períodos no tiene datos.")

    def stats(s: pd.DataFrame, label: str) -> dict:
        return {
            "Período": label,
            "Días con dato": len(s),
            "Cota media (m)": round(s["Cota (m)"].mean(), 2),
            "Cota mínima (m)": s["Cota (m)"].min(),
            "Cota máxima (m)": s["Cota (m)"].max(),
            "Disponibilidad media (%)": round(s["Disponibilidad (%)"].mean(), 1)
            if "Disponibilidad (%)" in s
            else None,
            "Entrada media (m³/s)": round(s["Entrada (m³/s)"].mean(), 2),
            "Salida media (m³/s)": round(s["Salida (m³/s)"].mean(), 2),
        }

    la, lb = f"{a[0]} a {a[1]}", f"{b[0]} a {b[1]}"
    summary = pd.DataFrame([stats(sa, la), stats(sb, lb)])

    def chart() -> bytes:
        plt = _plt()
        fig, ax = plt.subplots(figsize=(8, 3.4))
        ax.plot(range(len(sa)), sa["Cota (m)"], color="#2a78d6", lw=2, label=la)
        ax.plot(range(len(sb)), sb["Cota (m)"], color="#eb6834", lw=2, label=lb)
        ax.set_xlabel("Día del período")
        ax.set_ylabel("Cota (m.s.n.m.)")
        ax.legend(fontsize=8)
        ax.set_title(f"Comparación de períodos · {r.name}")
        return _png(fig)

    return Report(
        title=f"Histórico comparativo · Embalse {r.name}",
        subtitle=f"{la} frente a {lb}",
        tables=[("Resumen", summary), (f"Serie {la}", sa), (f"Serie {lb}", sb)],
        chart=chart,
        filename=f"historico_{r.code.lower()}",
    )


def between(session: Session, visible: set[str] | None, start: date, end: date) -> Report:
    """Comparativo entre embalses en un período."""
    frames, rows = {}, []
    for r in _visible(session, visible):
        s = _series(session, r, start, end)
        if s.empty:
            continue
        frames[r.name] = s
        rows.append(
            {
                "Embalse": r.name,
                "Cota inicial (m)": s["Cota (m)"].iloc[0],
                "Cota final (m)": s["Cota (m)"].iloc[-1],
                "Cambio (m)": round(s["Cota (m)"].iloc[-1] - s["Cota (m)"].iloc[0], 2),
                "Disponibilidad final (%)": s["Disponibilidad (%)"].iloc[-1]
                if "Disponibilidad (%)" in s
                else None,
                "Disponibilidad media (%)": round(s["Disponibilidad (%)"].mean(), 1)
                if "Disponibilidad (%)" in s
                else None,
                "Entrada media (m³/s)": round(s["Entrada (m³/s)"].mean(), 2),
                "Salida media (m³/s)": round(s["Salida (m³/s)"].mean(), 2),
            }
        )
    if not rows:
        raise ReportError("No hay datos en el período elegido.")
    colors = ["#2a78d6", "#eb6834", "#1baf7a"]

    def chart() -> bytes:
        plt = _plt()
        fig, ax = plt.subplots(figsize=(8, 3.4))
        for (name, s), c in zip(frames.items(), colors, strict=False):
            if "Disponibilidad (%)" in s:
                ax.plot(pd.to_datetime(s["Fecha"]), s["Disponibilidad (%)"], color=c, lw=2, label=name)
        ax.axhline(100, color="#52514e", ls="--", lw=1)
        ax.set_ylabel("Disponibilidad (%)")
        ax.legend(fontsize=8)
        ax.set_title("Disponibilidad comparada")
        return _png(fig)

    return Report(
        title="Comparativo entre embalses",
        subtitle=f"Del {start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}",
        tables=[("Resumen", pd.DataFrame(rows))] + [(f"Serie {n}", s) for n, s in frames.items()],
        chart=chart,
        filename=f"comparativo_{start.isoformat()}_{end.isoformat()}",
    )


def alerts_log(session: Session, visible: set[str] | None, start: date, end: date) -> Report:
    stmt = select(Alert).where(
        Alert.created_at >= datetime.combine(start, datetime.min.time()),
        Alert.created_at <= datetime.combine(end, datetime.max.time()),
    )
    if visible is not None:
        stmt = stmt.where(Alert.reservoir_code.in_(visible))
    names = dict(session.execute(select(Reservoir.code, Reservoir.name)).all())
    rows = [
        {
            "Fecha": a.created_at.strftime("%Y-%m-%d %H:%M"),
            "Embalse": names.get(a.reservoir_code, a.reservoir_code),
            "Severidad": a.severity,
            "Tipo": a.kind,
            "Sentido": a.direction,
            "Alerta": a.title,
            "Resuelta": a.resolved_at.strftime("%Y-%m-%d %H:%M") if a.resolved_at else "Activa",
            "Acuses": ", ".join(k.user_email for k in a.acknowledgements) or "—",
            "Envíos": ", ".join(f"{d.channel}:{d.status}" for d in a.deliveries) or "—",
        }
        for a in session.scalars(stmt.order_by(Alert.created_at.desc()))
    ]
    return Report(
        title="Registro de alertas",
        subtitle=f"Del {start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')} · {len(rows)} alertas",
        tables=[
            (
                "Alertas",
                pd.DataFrame(
                    rows,
                    columns=[
                        "Fecha",
                        "Embalse",
                        "Severidad",
                        "Tipo",
                        "Sentido",
                        "Alerta",
                        "Resuelta",
                        "Acuses",
                        "Envíos",
                    ],
                ),
            )
        ],
        filename=f"alertas_{start.isoformat()}_{end.isoformat()}",
    )


# ------------------------------------------------------------------ renderizadores


def render(report: Report, fmt: str) -> bytes:
    if fmt == "csv":
        name, df = (
            report.tables[0]
            if len(report.tables) == 1
            else ("", pd.concat([t.assign(Tabla=n) for n, t in report.tables], ignore_index=True))
        )
        return df.to_csv(index=False).encode("utf-8-sig")  # BOM: Excel en español lo abre bien
    if fmt == "xlsx":
        return _xlsx(report)
    if fmt == "png":
        if report.chart is None:
            raise ReportError("Este reporte no tiene gráfica.")
        return report.chart()
    if fmt == "pdf":
        return _pdf(report)
    if fmt in ("geojson", "kml"):
        if not report.geo:
            raise ReportError("Este reporte no tiene información geográfica (usa el boletín diario).")
        return (
            json.dumps(report.geo, ensure_ascii=False, default=str).encode("utf-8")
            if fmt == "geojson"
            else _kml(report.geo)
        )
    raise ReportError(f"Formato no soportado: {fmt}")


def _xlsx(report: Report) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    wb.remove(wb.active)
    for name, df in report.tables:
        ws = wb.create_sheet(name[:31].replace("/", "-"))
        ws.append([report.title])
        ws["A1"].font = Font(bold=True, size=13)
        ws.append([report.subtitle])
        ws.append([])
        ws.append(list(df.columns))
        for cell in ws[4]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="0C4A6E")
        for row in df.itertuples(index=False):
            ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in row])
        for i, col in enumerate(df.columns, start=1):
            ws.column_dimensions[ws.cell(4, i).column_letter].width = max(12, min(40, len(str(col)) + 2))
    if report.notes:
        ws = wb.create_sheet("Notas")
        for n in report.notes:
            ws.append([n])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pdf(report: Report) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=report.title,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Plataforma Hídrica Zulia · MINAGUAS", styles["Normal"]),
        Paragraph(report.title, styles["Title"]),
        Paragraph(report.subtitle, styles["Heading3"]),
        Spacer(1, 0.3 * cm),
    ]
    if report.chart is not None:
        story += [
            Image(io.BytesIO(report.chart()), width=22 * cm, height=9 * cm, kind="proportional"),
            Spacer(1, 0.3 * cm),
        ]
    small = styles["BodyText"].clone("small", fontSize=7, leading=8)
    for name, df in report.tables:
        if len(df) > 120:  # tablas diarias largas: en el PDF solo el inicio; completas en Excel/CSV
            df = df.head(120)
            name += " (primeras 120 filas; completa en Excel o CSV)"
        story.append(Paragraph(name, styles["Heading4"]))

        def cell(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "—"
            if isinstance(v, float):
                return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return Paragraph(str(v), small)

        data = [[Paragraph(f"<b>{c}</b>", small) for c in df.columns]] + [
            [cell(v) for v in row] for row in df.itertuples(index=False)
        ]
        t = Table(data, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8ecf1")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story += [t, Spacer(1, 0.4 * cm)]
    for n in report.notes:
        story.append(Paragraph(n, small))
    story.append(
        Paragraph(
            f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} por la Plataforma Hídrica Zulia.", small
        )
    )
    doc.build(story)
    return buf.getvalue()


def _kml(fc: dict) -> bytes:
    import simplekml

    kml = simplekml.Kml(name="Embalses del Zulia")
    color = {
        "Normal": "ff3d8015",
        "Alerta": "ff078aca",
        "Crítico / alivio": "ff1c1cb9",
        "Sin datos": "ff8b7564",
    }  # aabbggrr
    for f in fc["features"]:
        p = f["properties"]
        geoms = (
            f["geometry"]["coordinates"]
            if f["geometry"]["type"] == "MultiPolygon"
            else [f["geometry"]["coordinates"]]
        )
        for poly in geoms:
            pol = kml.newpolygon(
                name=p.get("Embalse", p.get("codigo")), outerboundaryis=[tuple(c) for c in poly[0]]
            )
            if len(poly) > 1:
                pol.innerboundaryis = [[tuple(c) for c in ring] for ring in poly[1:]]
            pol.description = "<br/>".join(f"{k}: {v}" for k, v in p.items() if v is not None)
            pol.style.polystyle.color = color.get(p.get("Estado"), "ff8b7564")
            pol.style.linestyle.width = 2
    return kml.kml().encode("utf-8")
