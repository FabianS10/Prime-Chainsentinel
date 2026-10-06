from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas import ReportRequest
from app.services.baseline_views import hardware_view, pow_view, summary_view
from app.services.evidence_store import get_result

REPORT_DIR = Path("storage/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _safe(value, fallback="—"):
    return fallback if value in (None, "") else str(value)


def _pct(value):
    try:
        return f"{100 * float(value):.2f}%"
    except (TypeError, ValueError):
        return "—"


def _money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"



def _evidence_es(value):
    return {"MEASURED":"MEDIDO","SURROGATE":"SUSTITUTO","ESTIMATED":"ESTIMADO","CORRECTED":"CORREGIDO","SIMULATED":"SIMULADO","EXPERIMENTAL":"EXPERIMENTAL","MIXED":"MIXTO"}.get(str(value or "").upper(), _safe(value))

def _provider_es(value):
    return {"yahoo":"Yahoo Finance","offline":"Sintético local","mixed":"Mixto"}.get(str(value or "").lower(), _safe(value))

def generate_pdf_report(req: ReportRequest) -> Path:
    """Genera un PDF únicamente a partir de evidencia/resultados ya existentes.

    Esta función no consulta nuevamente el mercado, no ejecuta Monte Carlo y no
    vuelve a correr la comparación de modelos. El reporte representa la sesión.
    """
    filename = f"prime_chainsentinel_reporte_{uuid.uuid4().hex[:8]}.pdf"
    path = REPORT_DIR / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="GoldTitle", parent=styles["Title"], textColor=colors.HexColor("#8B0000"), fontSize=20, leading=24))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Note", parent=styles["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#444444")))
    styles.add(ParagraphStyle(name="Warning", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#8B0000")))

    story = []
    title = req.title or "Prime ChainSentinel — Reporte de evidencia y procedencia"
    story.append(Paragraph(title, styles["GoldTitle"]))
    story.append(Paragraph("Prime ChainSentinel", styles["Heading3"]))
    story.append(Paragraph(f"Generado: {datetime.now(timezone.utc).isoformat()}", styles["Small"]))
    story.append(Spacer(1, 0.20 * inch))
    story.append(Paragraph("Resumen", styles["Heading2"]))
    story.append(Paragraph(
        "Este reporte representa la evidencia y los resultados que ya fueron obtenidos durante la sesión de trabajo. "
        "La generación del PDF no ejecuta nuevas consultas de mercado, simulaciones Monte Carlo ni comparaciones de modelos.",
        styles["BodyText"],
    ))
    if req.notes:
        story.append(Spacer(1, 0.10 * inch))
        story.append(Paragraph(f"Notas: {_safe(req.notes)}", styles["Note"]))

    summary = summary_view()
    hw_payload = hardware_view()
    source = summary.get("source") or {}

    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph("Procedencia de la campaña computacional", styles["Heading2"]))
    if summary.get("available"):
        story.append(_table([
            ["Campo", "Valor"],
            ["Importación", _safe(source.get("import_id"))],
            ["Campaña", _safe(source.get("campaign"))],
            ["Archivo incorporado", _safe(source.get("filename"))],
            ["Fecha de incorporación", _safe(source.get("imported_at"))],
            ["Estado de origen", _safe(source.get("origin_status"))],
            ["SHA-256 del paquete", _safe(source.get("sha256"))],
            ["SHA-256 del manifiesto", _safe(source.get("manifest_sha256"))],
        ], font_size=7))
        story.append(Paragraph(
            "Un SHA-256 coincidente comprueba integridad respecto al digest registrado. Por sí solo no certifica la autenticidad del productor externo ni la veracidad del contenido.",
            styles["Note"],
        ))
    else:
        story.append(Paragraph(
            "No se encontró una campaña computacional importada. Las secciones dependientes de evidencia MI300X no se completan con valores embebidos.",
            styles["Warning"],
        ))

    if hw_payload.get("available"):
        hw = hw_payload.get("hardware", {})
        story.append(Spacer(1, 0.18 * inch))
        story.append(Paragraph("Perfil del entorno", styles["Heading2"]))
        story.append(_table([
            ["Métrica", "Valor"],
            ["GPU", _safe(hw.get("gpu"))],
            ["VRAM", f"{_safe(hw.get('vram_gb'))} GB"],
            ["Backend", _safe(hw.get("backend"))],
            ["CPU", _safe(hw.get("cpu"))],
            ["Núcleos CPU", _safe(hw.get("cores"))],
            ["RAM", f"{_safe(hw.get('ram_gb'))} GB"],
            ["ROCm", _safe(hw.get("rocm"))],
            ["PyTorch", _safe(hw.get("pytorch"))],
            ["Commit", _safe(hw.get("git_commit"))],
        ]))

    if summary.get("available"):
        story.append(Spacer(1, 0.18 * inch))
        story.append(Paragraph("Evidencia computacional incorporada", styles["Heading2"]))
        rows = [["Métrica", "Valor", "Clase"]]
        if summary.get("gpu_synthetic_peak_run1") is not None:
            rows.append(["Pico GPU, ejecución 1", f"{summary['gpu_synthetic_peak_run1']:,.0f} ops/s", "SUSTITUTO"])
        if summary.get("gpu_synthetic_peak_run2") is not None:
            rows.append(["Pico GPU, ejecución 2", f"{summary['gpu_synthetic_peak_run2']:,.0f} ops/s", "SUSTITUTO"])
        if summary.get("gpu_repeatability_error_pct") is not None:
            rows.append(["Diferencia relativa entre ejecuciones GPU", f"{summary['gpu_repeatability_error_pct']:.3f}%", "DERIVADO"])
        for alg, rate in summary.get("best_hash_rates", {}).items():
            rows.append([f"Pico CPU {alg}", f"{rate:,.0f} ops/s", "MEDIDO"])
        if len(rows) > 1:
            story.append(_table(rows))
        story.append(Paragraph(
            "Límite de interpretación: la carga GPU importada se clasifica como SUSTITUTO y no equivale a hashing criptográfico nativo ejecutado en GPU.",
            styles["Warning"],
        ))

    if req.include_blockchain:
        story.append(Spacer(1, 0.18 * inch))
        story.append(Paragraph("Laboratorio blockchain", styles["Heading2"]))
        story.append(Paragraph(
            "Las estimaciones de carga hash y Merkle dependen de líneas base importadas. La prueba de trabajo se mantiene como ejercicio educativo fuera de línea.",
            styles["BodyText"],
        ))
        pow_data = pow_view()
        if pow_data.get("available"):
            story.append(_table([
                ["Dificultad", "Intentos esperados", "Tiempo medio medido", "Tasa medida"],
                *[[
                    str(p["difficulty_bits"]),
                    f"{int(p['expected_trials']):,}",
                    f"{p['mean_ms']:.3f} ms",
                    f"{p['hash_rate']:,.0f} ops/s",
                ] for p in pow_data.get("rows", [])],
            ]))
        else:
            story.append(Paragraph("No se encontró evidencia PoW importada para esta sesión.", styles["Note"]))

    # Flujo financiero: solo se representa lo que ya fue ejecutado en la sesión.
    market = req.market_snapshot or None
    mc_result = get_result(req.monte_carlo_result_id) if req.monte_carlo_result_id else None
    comparison_result = get_result(req.model_comparison_result_id) if req.model_comparison_result_id else None

    story.append(PageBreak())
    story.append(Paragraph("Flujo financiero", styles["Heading2"]))
    story.append(_table([
        ["Etapa", "Estado", "Referencia"],
        ["Consulta de mercado", "EJECUTADA" if market else "NO EJECUTADA", _provider_es((market or {}).get("provider"))],
        ["Simulación Monte Carlo", "EJECUTADA" if mc_result else "NO EJECUTADA", _safe(req.monte_carlo_result_id)],
        ["Comparación de modelos", "EJECUTADA" if comparison_result else "NO EJECUTADA", _safe(req.model_comparison_result_id)],
    ], font_size=7))
    story.append(Paragraph(
        "Las etapas no ejecutadas se señalan como tales y no se generan silenciosamente al exportar el documento.",
        styles["Note"],
    ))

    if market:
        story.append(Spacer(1, 0.18 * inch))
        story.append(Paragraph("Laboratorio de mercado", styles["Heading2"]))
        assets = market.get("assets") or []
        weight_map = {str(a.get("ticker", "")).upper(): a.get("weight", 0) for a in assets}
        market_rows = [["Símbolo", "Peso", "Proveedor", "CAGR", "Volatilidad", "Máx. caída", "Evidencia"]]
        for metric in market.get("metrics") or []:
            ticker = str(metric.get("ticker", "")).upper()
            market_rows.append([
                ticker,
                f"{100 * float(weight_map.get(ticker, 0)):.1f}%",
                _provider_es(metric.get("provider")),
                _pct(metric.get("cagr")),
                _pct(metric.get("annualized_volatility")),
                _pct(metric.get("max_drawdown")),
                f"serie {_evidence_es(metric.get('price_series_label') or market.get('price_series_label'))} / métricas ESTIMADAS",
            ])
        if len(market_rows) > 1:
            story.append(_table(market_rows, font_size=7))
        story.append(Spacer(1, 0.08 * inch))
        story.append(_table([
            ["Parámetro", "Valor"],
            ["Proveedor", _provider_es(market.get("provider"))],
            ["Años consultados", _safe(market.get("years"))],
            ["Clase de la serie", _evidence_es(market.get("price_series_label"))],
            ["Clase de métricas", _evidence_es(market.get("metric_label"))],
            ["Resultados fuente", ", ".join(market.get("dataset_ids") or []) or "—"],
        ], font_size=7))
        for warning in market.get("warnings") or []:
            story.append(Paragraph(str(warning), styles["Warning"]))
    else:
        story.append(Spacer(1, 0.12 * inch))
        story.append(Paragraph("No se realizó una consulta de mercado en la sesión que originó este reporte.", styles["Warning"]))

    if mc_result:
        story.append(Spacer(1, 0.18 * inch))
        story.append(Paragraph("Simulación Monte Carlo", styles["Heading2"]))
        params = mc_result.get("parameters") or {}
        value = mc_result.get("value") or {}
        dist = value.get("final_value_distribution") or {}
        risk = value.get("risk") or {}
        story.append(_table([
            ["Campo", "Valor"],
            ["ID del resultado", mc_result.get("result_id")],
            ["Clase", _evidence_es(mc_result.get("evidence_class"))],
            ["Capital inicial", _money(params.get("initial_capital"))],
            ["Aporte mensual", _money(params.get("monthly_contribution"))],
            ["Horizonte", f"{_safe(params.get('horizon_years'))} años"],
            ["Trayectorias", _safe(params.get("trials"))],
            ["Mediana terminal", _money(dist.get("median"))],
            ["Percentil 10", _money(dist.get("p10"))],
            ["Percentil 90", _money(dist.get("p90"))],
            ["Puntuación de riesgo", _safe(risk.get("risk_score"))],
        ], font_size=7))
        parents = [row.get("parent_result_id") for row in mc_result.get("derived_from") or []]
        story.append(Paragraph(f"Derivado de: {', '.join(parents) if parents else '—'}", styles["Note"]))
        story.append(Paragraph(
            "Los resultados se clasifican como SIMULADO y no representan rentabilidades garantizadas ni recomendaciones de inversión.",
            styles["Warning"],
        ))
    else:
        story.append(Spacer(1, 0.12 * inch))
        story.append(Paragraph("La simulación Monte Carlo no fue ejecutada; el reporte no genera una nueva simulación.", styles["Note"]))

    if comparison_result:
        story.append(PageBreak())
        story.append(Paragraph("Comparación temporal de modelos", styles["Heading2"]))
        params = comparison_result.get("parameters") or {}
        value = comparison_result.get("value") or {}
        summary_rows = value.get("summary") or []
        story.append(_table([
            ["Parámetro", "Valor"],
            ["ID del resultado", comparison_result.get("result_id")],
            ["Clase", _evidence_es(comparison_result.get("evidence_class"))],
            ["Años de historia", _safe(params.get("years"))],
            ["Ventana de entrenamiento", f"{_safe(params.get('rolling_window_months'))} meses"],
            ["Horizonte de evaluación", f"{_safe(params.get('forecast_horizon_months'))} meses"],
            ["Trayectorias por evaluación", _safe(params.get("trials"))],
            ["Ventanas evaluadas", _safe(value.get("evaluation_windows"))],
        ], font_size=7))
        comparison_rows = [["Modelo", "Error cobertura 90 %", "Ancho medio", "Pérdida cuantílica", "CVaR"]]
        for row in summary_rows:
            comparison_rows.append([
                row.get("model"),
                _pct(row.get("coverage_error_90")),
                _pct(row.get("average_interval_width_pct")),
                f"{float(row.get('quantile_loss') or 0):.2f}",
                _pct(row.get("cvar_95_pct")),
            ])
        if len(comparison_rows) > 1:
            story.append(Spacer(1, 0.12 * inch))
            story.append(_table(comparison_rows, font_size=7))
            labels = [row.get("model") or "" for row in summary_rows]
            story.append(Spacer(1, 0.12 * inch))
            story.append(_bar_chart(
                "Error de cobertura del intervalo del 90 %",
                labels,
                [100 * float(row.get("coverage_error_90") or 0) for row in summary_rows],
                colors.HexColor("#D72638"),
            ))
        story.append(Paragraph(
            "La comparación presenta diagnósticos complementarios y no declara un modelo universalmente superior.",
            styles["Note"],
        ))
    else:
        story.append(Spacer(1, 0.12 * inch))
        story.append(Paragraph("La comparación de modelos no fue ejecutada; el reporte no la ejecuta automáticamente.", styles["Note"]))

    story.append(PageBreak())
    story.append(Paragraph("Metadatos de reproducibilidad", styles["Heading2"]))
    metadata_rows = [
        ["Elemento", "Valor"],
        ["Importación computacional", _safe(source.get("import_id"))],
        ["SHA-256 del paquete", _safe(source.get("sha256"))],
        ["Resultados de mercado", ", ".join((market or {}).get("dataset_ids") or []) or "—"],
        ["Resultado Monte Carlo", _safe(req.monte_carlo_result_id)],
        ["Resultado de comparación", _safe(req.model_comparison_result_id)],
    ]
    if mc_result:
        metadata_rows.append(["Semilla Monte Carlo (metadato técnico)", _safe((mc_result.get("parameters") or {}).get("seed"))])
    if comparison_result:
        metadata_rows.append(["Semilla de comparación (metadato técnico)", _safe((comparison_result.get("parameters") or {}).get("seed"))])
    story.append(_table(metadata_rows, font_size=7))
    story.append(Paragraph(
        "La semilla pseudoaleatoria se conserva únicamente como metadato técnico para reproducir procedimientos estocásticos; no constituye una variable de análisis del escenario.",
        styles["Note"],
    ))
    story.append(Paragraph(
        "Prime ChainSentinel conserva la procedencia disponible para interpretar los resultados. Las simulaciones financieras son educativas; no hay negociación en vivo ni minería real.",
        styles["Note"],
    ))
    doc.build(story)
    return path


def _bar_chart(title: str, labels: list[str], values: list[float], color) -> Drawing:
    drawing = Drawing(510, 230)
    drawing.add(String(10, 210, title, fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#8B0000")))
    chart = VerticalBarChart()
    chart.x = 45
    chart.y = 45
    chart.height = 145
    chart.width = 440
    chart.data = [values]
    chart.categoryAxis.categoryNames = [str(label).replace("Monte Carlo", "MC") for label in labels]
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.dy = -10
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    max_value = max(values) if values else 1
    chart.valueAxis.valueMax = max(max_value * 1.2, 1)
    chart.valueAxis.valueStep = chart.valueAxis.valueMax / 5
    chart.bars[0].fillColor = color
    chart.bars[0].strokeColor = color
    drawing.add(chart)
    return drawing


def _table(rows, font_size: int = 8):
    tbl = Table(rows, repeatRows=1, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#11131A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#D4AF37")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BBBBBB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl
