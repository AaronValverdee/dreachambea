#!/usr/bin/env python3
"""Regenera index.html a partir de data/opportunities.json y data/research-log.md."""
import base64
import html
import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "opportunities.json"
LOG_FILE = ROOT / "data" / "research-log.md"
OUT = ROOT / "index.html"
PASSWORD_FILE = ROOT / ".page-password"
KDF_ITERATIONS = 120_000

H = html.escape
data = json.loads(DATA.read_text(encoding="utf-8"))
UPDATED = data["updated"]
try:
    UPDATED_DATE = datetime.strptime(UPDATED, "%d/%m/%Y").date()
    UPDATED_ISO = UPDATED_DATE.strftime("%Y-%m-%d")
except ValueError:
    UPDATED_DATE = None
    UPDATED_ISO = UPDATED
NEW_LOOKBACK = timedelta(days=6)

opps = data["opportunities"]
top5 = data["top5"]
radar = data["radar"]
upcoming = data["upcoming"]
intl_block = data["international"]
intl = intl_block["opportunities"]
intl_extra_links = [(item["name"], item["url"]) for item in intl_block["extra_links"]]
intl_watch = intl_block["watch"]
intl_timeline = [("", item["date"], item["event"], item["kind"]) for item in intl_block["timeline"]]
intl_dropped = intl_block["dropped"]


def parse_latest_log():
    """Extrae la entrada más reciente de data/research-log.md y detecta IDs nuevos."""
    if not LOG_FILE.exists():
        return None, set()
    text = LOG_FILE.read_text(encoding="utf-8")
    parts = re.split(r"^##\s+", text, flags=re.MULTILINE)
    if len(parts) < 2:
        return None, set()
    latest = parts[1].strip()
    lines = latest.splitlines()
    header = lines[0].strip()
    body = "\n".join(lines[1:]).strip()

    # Detectar menciones explícitas de fichas nuevas en el log, p.ej. `eag-seguridad`
    new_ids = set(re.findall(r"`([a-z0-9-]+)`", body))

    sections = []
    cur_title = None
    cur_items = []
    intro_lines = []

    for line in lines[1:]:
        s = line.strip()
        if not s:
            continue
        if s.endswith(":") and not s.startswith("-"):
            if cur_title:
                sections.append((cur_title, cur_items))
            cur_title = s[:-1]
            cur_items = []
        elif s.startswith("- "):
            if cur_title is None:
                cur_title = "Notas"
            cur_items.append(s[2:].strip())
        else:
            if cur_title is None:
                intro_lines.append(s)
            else:
                cur_items.append(s)
    if cur_title:
        sections.append((cur_title, cur_items))

    return {"header": header, "intro": " ".join(intro_lines), "sections": sections}, new_ids


latest_log, log_new_ids = parse_latest_log()


def is_new_card(o):
    if o.get("id") in log_new_ids:
        return True
    raw = o.get("first_seen") or o.get("added_on") or ""
    if not raw or not UPDATED_DATE:
        return False
    try:
        seen = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return False
    return UPDATED_DATE - NEW_LOOKBACK <= seen <= UPDATED_DATE


def extract_iso_date(text, fallback_iso=""):
    """Extrae la primera fecha DD/MM/AAAA válida como AAAA-MM-DD para cuentas atrás y calendario."""
    if fallback_iso and re.match(r"^\d{4}-\d{2}-\d{2}$", fallback_iso):
        return fallback_iso
    if not text:
        return ""
    # Evitar tomar "activo hasta 30/06/2027" o "publicada el 24/11/2026" como fecha de cierre urgente
    low = text.lower()
    if "publicada el" in low or "activo hasta" in low or "abiertas desde" in low:
        return ""
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
    return ""


def commute_info(o):
    """Clasifica el desplazamiento desde Madrid/ETSII UPM y el turno horario."""
    loc = o.get("location", "")
    low_loc = loc.lower()
    mod_label = o.get("modality_label", "").lower()
    hrs = o.get("hours", "").lower()
    cav = o.get("caveats", "").lower()

    badges = []
    # Horario de mañana / flexible
    if "mañana" in hrs or "mañana" in mod_label or "09:00" in hrs:
        badges.append(('🌅 Solo mañanas', 'sch-morn', 'Horario de mañana: ideal si las clases del máster son de tarde'))
    elif "adaptado" in hrs or "a elegir" in hrs or "flexible" in hrs:
        badges.append(('🔄 Horario flexible', 'sch-flex', 'Horario adaptable al calendario de clases de la UPM'))

    # Zona / transporte
    if "vehículo" in mod_label or "vehículo" in cav or "edar" in low_loc:
        badges.append(('🚗 Requiere coche', 'loc-car', 'Planta o centro sin acceso directo en transporte público'))
    elif any(k in low_loc for k in ["móstoles", "san sebastián de los reyes", "pozuelo", "alcobendas", "getafe", "leganés", "tres cantos"]):
        badges.append(('🚌 Periferia / Campus ext.', 'loc-sub', 'Fuera de la almendra central; calcular ~40-55 min desde UPM'))
    elif "cantoblanco" in low_loc or "uam" in low_loc:
        badges.append(('🚆 Cercanías Cantoblanco', 'loc-train', 'Conexión rápida en Cercanías C4 desde Nuevos Ministerios / Sol'))
    else:
        badges.append(('🚇 Madrid bien conectado', 'loc-cen', 'Sede en Madrid capital con acceso directo en Metro'))

    dest_query = f"{o['org']}, {loc}, Madrid"
    maps_url = "https://www.google.com/maps/dir/?api=1&origin=" + urllib.parse.quote("ETSII UPM, Calle José Gutiérrez Abascal 2, Madrid") + "&destination=" + urllib.parse.quote(dest_query) + "&travelmode=transit"
    return badges, maps_url


def format_log_item(item_text):
    """Convierte URLs y códigos en enlaces/chips dentro del resumen semanal."""
    escaped = H(item_text)
    escaped = re.sub(r"`([a-z0-9-]+)`", r'<a href="#card-\1" class="log-ref"><code>\1</code></a>', escaped)
    escaped = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" target="_blank" rel="noopener">Ver enlace ↗</a>', escaped)
    return escaped


def render_novedades_box():
    if not latest_log:
        return ""
    sec_icons = {
        "Aplicar esta semana": ("🎯", "sec-apply"),
        "Preguntar antes de aplicar": ("💬", "sec-ask"),
        "Radar o largo plazo": ("🔭", "sec-radar"),
        "Descartadas": ("🗑️", "sec-drop"),
        "No se pudo revisar": ("⚠️", "sec-warn"),
        "Pendiente para el próximo run": ("📌", "sec-next"),
    }
    cols_html = ""
    for title, items in latest_log["sections"]:
        if not items or (len(items) == 1 and items[0].lower().startswith("ninguna")):
            continue
        # Omitimos secciones internas del agente si no aportan a la toma de decisión rápida, o las dejamos plegadas
        if title in ("No se pudo revisar", "Pendiente para el próximo run"):
            continue
        icon, cls = sec_icons.get(title, ("📋", "sec-note"))
        lis = "".join(f"<li>{format_log_item(x)}</li>" for x in items)
        cols_html += f'<div class="nov-box {cls}"><h4>{icon} {H(title)}</h4><ul>{lis}</ul></div>'

    new_count = sum(1 for o in opps if is_new_card(o)) + sum(1 for o in intl if is_new_card(o))
    new_pill = f'<span class="nov-pill">🆕 {new_count} fichas nuevas esta semana</span>' if new_count else ""

    return f'''<details class="novedades" open>
  <summary>
    <div class="nov-title">
      <span class="nov-badge">✨ NOVEDADES DE LA SEMANA</span>
      <strong>Resumen del pase semanal ({H(latest_log["header"])})</strong>
      {new_pill}
    </div>
    <span class="nov-toggle">Mostrar / ocultar ▾</span>
  </summary>
  <div class="nov-body">
    <div class="nov-grid">{cols_html}</div>
  </div>
</details>'''


CAT = {
    "energia": "Energía / renovables",
    "almacenamiento": "Almacenamiento / baterías",
    "nuclear": "Nuclear",
    "investigacion": "I+D / investigación",
    "consultoria": "Consultoría energética",
    "innovacion": "Innovación",
}
MOD = {"hibrido": "Híbrido", "remoto": "Remoto", "presencial": "Presencial", "no_indicado": "Sin indicar"}
modrank = {"hibrido": 0, "remoto": 1, "no_indicado": 2, "presencial": 3}
opps_sorted = sorted(opps, key=lambda o: (-o["fit"], o["status"] != "cumple", modrank[o["modality"]]))


def stars(n):
    return '<span class="stars" aria-label="%d de 5">%s<span class="off">%s</span></span>' % (n, "★" * n, "★" * (5 - n))


def tracker_controls(cid):
    return f'''<div class="trk-bar" data-id="{H(cid)}">
  <div class="trk-row">
    <label class="trk-lbl">Mi estado:</label>
    <select class="trk-sel" data-id="{H(cid)}" aria-label="Estado de la candidatura">
      <option value="none">⚪ Sin marcar</option>
      <option value="mirar">⭐ Por mirar</option>
      <option value="preguntado">📩 Preguntado</option>
      <option value="aplicada">✅ Aplicada</option>
      <option value="descartada">❌ Descartada</option>
    </select>
    <button type="button" class="trk-note-btn" data-id="{H(cid)}" title="Añadir o ver mis notas">📝 Nota</button>
  </div>
  <div class="trk-note-wrap" id="note-wrap-{H(cid)}" style="display:none">
    <textarea class="trk-note" data-id="{H(cid)}" rows="2" placeholder="Escribe aquí tus notas (ej. fecha de solicitud, contacto de RR. HH., respuesta sobre horario...)"></textarea>
  </div>
</div>'''


def card(o, rank=None):
    cid = o["id"]
    is_new = is_new_card(o)
    dl_iso = extract_iso_date(o["deadline"], o.get("deadline_date", ""))
    chips = "".join('<span class="chip cat">%s</span>' % CAT[c] for c in o["categories"])
    st = '<span class="badge ok">Cumple criterios</span>' if o["status"] == "cumple" else '<span class="badge warn">Algún dato por confirmar</span>'
    new_badge = '<span class="badge newb">🆕 Nueva esta semana</span>' if is_new else ""
    dl_badge = f'<span class="badge dl-live" data-dl="{H(dl_iso)}"></span>' if dl_iso else ""
    urgent = " urgent" if "HOY" in o["deadline"] else ""

    comm_badges, maps_url = commute_info(o)
    comm_html = "".join(f'<span class="chip {cls}" title="{H(tip)}">{H(lbl)}</span>' for lbl, cls, tip in comm_badges)

    def val(v, conf):
        return H(v) + ("" if conf else ' <span class="q" title="No confirmado en la oferta">?</span>')

    # Botones de acción rápida: plantilla de consulta, calendario .ics
    extra_btns = []
    if o["status"] == "por_confirmar" or not o["hours_confirmed"] or not o["pay_confirmed"]:
        extra_btns.append(
            f'<button type="button" class="act-btn ask-btn" '
            f'data-org="{H(o["org"])}" data-title="{H(o["title"])}" '
            f'data-hconf="{str(o["hours_confirmed"]).lower()}" data-pconf="{str(o["pay_confirmed"]).lower()}" '
            f'data-cav="{H(o["caveats"])}" data-url="{H(o["url"])}">💬 Copiar consulta</button>'
        )
    if dl_iso:
        extra_btns.append(
            f'<button type="button" class="act-btn ics-btn" '
            f'data-title="Plazo solicitud: {H(o["org"])} – {H(o["title"])}" '
            f'data-date="{H(dl_iso)}" data-url="{H(o["url"])}" '
            f'data-desc="{H(o["fit_reason"])}">📅 Añadir al calendario</button>'
        )
    extra_btns.append(f'<a class="act-btn map-btn" href="{H(maps_url)}" target="_blank" rel="noopener" title="Ruta en transporte público desde ETSII UPM">🗺️ Ruta UPM</a>')
    actions_html = f'<div class="card-actions">{"".join(extra_btns)}</div>'

    card_dom_id = f' id="card-{H(cid)}"' if rank is None else ""
    return f'''<article{card_dom_id} class="card{urgent}" data-id="{H(cid)}" data-mod="{o['modality']}" data-cat="{' '.join(o['categories'])}" data-status="{o['status']}" data-new="{'1' if is_new else '0'}" data-dl="{H(dl_iso)}">
  <header>{'<span class="rank">#%d</span>' % rank if rank else ''}<div><p class="org">{H(o['org'])}</p><h3>{H(o['title'])}</h3></div></header>
  <div class="meta">{new_badge}{dl_badge}{st}<span class="chip mod m-{o['modality']}">{MOD[o['modality']]}</span>{comm_html}{chips}</div>
  <dl>
   <div><dt>📍 Lugar</dt><dd>{H(o['location'])}</dd></div>
   <div><dt>🏠 Modalidad</dt><dd>{H(o['modality_label'])}</dd></div>
   <div><dt>⏱ Horas</dt><dd>{val(o['hours'], o['hours_confirmed'])}</dd></div>
   <div><dt>💶 Remuneración</dt><dd>{val(o['pay'], o['pay_confirmed'])}</dd></div>
   <div><dt>📅 Plazo</dt><dd>{H(o['deadline'])}</dd></div>
   <div><dt>🚀 Inicio</dt><dd>{H(o['start'])}</dd></div>
  </dl>
  <div class="fit"><div class="fitrow"><strong>Encaje</strong> {stars(o['fit'])}</div><p>{H(o['fit_reason'])}</p></div>
  <p class="cav">⚠️ {H(o['caveats'])}</p>
  {actions_html}
  {tracker_controls(cid)}
  <footer><span class="src">Fuente: {H(o['source'])} · verificado {UPDATED}</span><a class="btn" href="{H(o['url'])}" target="_blank" rel="noopener">Ver y aplicar →</a></footer>
</article>'''


n = len(opps)
ncum = sum(o["status"] == "cumple" for o in opps)
nhyb = sum(o["modality"] == "hibrido" for o in opps)
npay = sum(o["pay_confirmed"] for o in opps)
nhrs = sum(o["hours_confirmed"] for o in opps)
top_html = "".join(card(next(o for o in opps if o["id"] == i), k + 1) for k, i in enumerate(top5))
all_html = "".join(card(o) for o in opps_sorted)

radar_html = ""
for r in radar:
    r_dl = extract_iso_date(r["deadline"])
    r_ics = (
        f' <button type="button" class="act-btn ics-btn sm" data-title="Plazo Radar: {H(r["org"])}" '
        f'data-date="{H(r_dl)}" data-url="{H(r["url"])}" data-desc="{H(r["why"])}">📅 .ics</button>'
        if r_dl
        else ""
    )
    r_badge = f' <span class="badge dl-live" data-dl="{H(r_dl)}"></span>' if r_dl else ""
    radar_html += f'<li><a href="{H(r["url"])}" target="_blank" rel="noopener"><strong>{H(r["org"])}</strong>: {H(r["title"])}</a><span>{H(r["why"])}</span><em>Plazo: {H(r["deadline"])}{r_badge}{r_ics}</em></li>'

up_html = "".join(
    f'<li><a href="{H(u["url"])}" target="_blank" rel="noopener"><strong>{H(u["name"])}</strong></a><span>{H(u["detail"])}</span></li>'
    for u in upcoming
)
SI = {"ok": "✅", "parcial": "🟡", "no": "⛔"}
src_html = "".join(
    f'<li><span class="si">{SI[s["status"]]}</span><div><strong>{H(s["name"])}</strong><span>{H(s["detail"])}</span></div></li>'
    for s in data["sources"]
)
crit_html = "".join(f'<span class="crit">{H(c)}</span>' for c in data["criteria"])
catbtn = "".join(f'<button data-f="cat" data-v="{k}">{v}</button>' for k, v in CAT.items())
modbtn = "".join(f'<button data-f="mod" data-v="{k}">{v}</button>' for k, v in MOD.items())

CTRY = {"FR": "🇫🇷 Francia", "CH": "🇨🇭 Suiza", "BE": "🇧🇪 Bélgica", "US": "🇺🇸 EE. UU."}
IST = {"abierta": ("ok", "Abierta"), "proxima": ("warn", "Abre pronto"), "continua": ("cont", "Continua / contacto")}


def icard(o):
    cid = o["id"]
    is_new = is_new_card(o)
    dl_iso = extract_iso_date(o["deadline"], o.get("dl_sort", ""))
    cl, lab = IST[o["status"]]
    flag = CTRY[o["country"]].split(" ")[0]
    new_badge = '<span class="badge newb">🆕 Nueva esta semana</span>' if is_new else ""
    dl_badge = f'<span class="badge dl-live" data-dl="{H(dl_iso)}"></span>' if dl_iso else ""
    default_lang = "fr" if o["country"] == "FR" and o["id"] != "iter" and o["id"] != "oecd-nea" else "en"

    extra_btns = [
        f'<button type="button" class="act-btn tpl-btn" '
        f'data-org="{H(o["org"])}" data-title="{H(o["title"])}" '
        f'data-group="{H(o["group"])}" data-lang="{default_lang}" '
        f'data-why="{H(o["why"])}" data-url="{H(o["url"])}">✉️ Plantilla contacto / carta</button>'
    ]
    if dl_iso:
        extra_btns.append(
            f'<button type="button" class="act-btn ics-btn" '
            f'data-title="Plazo internacional: {H(o["org"])} – {H(o["title"])}" '
            f'data-date="{H(dl_iso)}" data-url="{H(o["url"])}" '
            f'data-desc="{H(o["why"])}">📅 Añadir al calendario</button>'
        )
    actions_html = f'<div class="card-actions">{"".join(extra_btns)}</div>'

    return f"""<article id="card-{H(cid)}" class="card icard" data-id="{H(cid)}" data-country="{o['country']}" data-new="{'1' if is_new else '0'}" data-dl="{H(dl_iso)}">
  <header><div><p class="org">{H(o['org'])}</p><h3>{H(o['title'])}</h3></div></header>
  <div class="meta">{new_badge}{dl_badge}<span class="badge {cl}">{lab}</span><span class="chip ctry">{flag} {H(o['country_label'])}</span></div>
  <dl>
   <div><dt>📍 Lugar</dt><dd>{H(o['location'])}</dd></div>
   <div><dt>📅 Plazo</dt><dd>{H(o['deadline'])}</dd></div>
   <div><dt>🚀 Inicio</dt><dd>{H(o['start'])}</dd></div>
   <div><dt>⌛ Duración</dt><dd>{H(o['duration'])}</dd></div>
   <div><dt>💶 Remuneración</dt><dd>{H(o['pay'])}</dd></div>
   <div><dt>⏱ Horas</dt><dd>{H(o['hours'])}</dd></div>
  </dl>
  <div class="fit"><div class="fitrow"><strong>Encaje</strong> {stars(o['fit'])}</div><p>{H(o['why'])}</p></div>
  <p class="cav">📋 {H(o['req'])}</p>
  {actions_html}
  {tracker_controls(cid)}
  <footer><span class="src">Fuente: {H(o['source'])} · enlace comprobado {UPDATED}</span><a class="btn btn2" href="{H(o['url'])}" target="_blank" rel="noopener">Ver oferta →</a></footer>
</article>"""


GRP = [
    (
        "programa",
        "🎓 Programas estructurados con plazo",
        "Convocatorias oficiales con fechas. Son las primeras que hay que tener en el calendario.",
    ),
    (
        "stage",
        "🇫🇷 Prácticas (stages) en Francia con inicio en 2027",
        "Ofertas concretas de CEA, ASNR, Framatome, EDF y Orano. Casi todas empiezan entre enero y abril de 2027 y duran unos 6 meses. Ordenadas por encaje.",
    ),
    (
        "contacto",
        "✉️ Vía contacto directo",
        "Sin convocatoria: se consigue escribiendo a un laboratorio o profesor con CV y propuesta de TFM.",
    ),
]
intl_groups_html = ""
for g, t, sub in GRP:
    items = sorted([o for o in intl if o["group"] == g], key=lambda o: (-o["fit"], o["dl_sort"] or "9999"))
    extra = ""
    if g == "stage":
        extra = (
            '<p class="more">📚 Más temas en catálogos: '
            + " · ".join(f'<a href="{H(u)}" target="_blank" rel="noopener">{H(n)}</a>' for n, u in intl_extra_links[:2])
            + "</p>"
        )
    if g == "contacto":
        extra = (
            '<p class="more">👤 Perfiles para escribir: '
            + " · ".join(f'<a href="{H(u)}" target="_blank" rel="noopener">{H(n)}</a>' for n, u in intl_extra_links[2:])
            + "</p>"
        )
    intl_groups_html += f'<h3 class="gh">{t} <span class="cnt">{len(items)}</span></h3><p class="sub">{sub}</p><div class="grid">{"".join(icard(o) for o in items)}</div>{extra}'

KIND = {"dl": "⏳", "open": "🟢", "start": "🚀", "info": "ℹ️"}
tl_html = ""
for a, b, c, k in intl_timeline:
    tl_iso = extract_iso_date(b)
    tl_ics = (
        f'<button type="button" class="tl-ics ics-btn" data-title="{H(c)}" data-date="{H(tl_iso)}" data-url="https://AaronValverdee.github.io/dreachambea/#intl" data-desc="Hito del calendario internacional: {H(c)}">📅 Añadir</button>'
        if tl_iso
        else ""
    )
    tl_html += f'<li class="k-{k}" data-dl="{H(tl_iso)}"><span class="tdot">{KIND[k]}</span><div><b>{H(b)}</b><span>{H(c)}</span>{tl_ics}</div></li>'

iw_html = "".join(
    f'<li><a href="{H(u["url"])}" target="_blank" rel="noopener"><strong>{H(u["name"])}</strong></a><span>{H(u["detail"])}</span></li>'
    for u in intl_watch
)
idrop_html = "".join(f"<li>{H(x)}</li>" for x in intl_dropped)
nint = len(intl)
nopen = sum(o["status"] == "abierta" for o in intl)
cbtn = "".join(
    f'<button data-if="country" data-v="{k}">{v} <small>{sum(o["country"] == k for o in intl)}</small></button>'
    for k, v in CTRY.items()
)

# Preparar lista JSON de todos los plazos conocidos para el banner dinámico de urgentes
all_deadlines = []
for o in opps:
    iso = extract_iso_date(o["deadline"], o.get("deadline_date", ""))
    if iso:
        all_deadlines.append({
            "id": o["id"],
            "org": o["org"],
            "title": o["title"],
            "date": iso,
            "label": o["deadline"],
            "scope": "Madrid",
            "caveat": f"{o['hours']} · {o['pay']}",
            "url": f"#card-{o['id']}",
        })
for o in intl:
    iso = extract_iso_date(o["deadline"], o.get("dl_sort", ""))
    if iso:
        all_deadlines.append({
            "id": o["id"],
            "org": o["org"],
            "title": o["title"],
            "date": iso,
            "label": o["deadline"],
            "scope": "Internacional",
            "caveat": o["country_label"],
            "url": f"#card-{o['id']}",
        })
for r in radar:
    iso = extract_iso_date(r["deadline"])
    if iso:
        all_deadlines.append({
            "id": "radar",
            "org": r["org"],
            "title": r["title"],
            "date": iso,
            "label": r["deadline"],
            "scope": "Radar",
            "caveat": "Jornada completa",
            "url": r["url"],
        })
deadlines_json = json.dumps(all_deadlines, ensure_ascii=False)
novedades_html = render_novedades_box()

page = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Prácticas en Madrid · {UPDATED}</title>
<style>
:root{{--bg:#f6f7fb;--card:#fff;--ink:#1d2433;--mut:#5d6779;--line:#e5e8ef;--acc:#0f766e;--acc2:#2563eb;--warn:#b45309;--ok:#15803d;--red:#b91c1c;--purp:#5b21b6}}
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.45}}
.hero{{background:linear-gradient(135deg,#0f766e 0%,#1e40af 100%);color:#fff;padding:38px 20px 64px}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 20px}}
.hero-top{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:14px}}
.hero h1{{margin:0 0 6px;font-size:clamp(26px,4vw,40px);letter-spacing:-.02em}}.hero p{{margin:4px 0;opacity:.92}}
.upd{{display:inline-block;background:rgba(255,255,255,.16);padding:5px 13px;border-radius:99px;font-size:13px}}
.top-tools{{display:flex;gap:8px;flex-wrap:wrap}}
.tool-btn{{background:rgba(255,255,255,.16);color:#fff;border:1px solid rgba(255,255,255,.32);padding:6px 12px;border-radius:99px;font-size:12.5px;cursor:pointer;font-weight:500}}
.tool-btn:hover{{background:rgba(255,255,255,.28)}}
.crits{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}}.crit{{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.3);padding:6px 12px;border-radius:99px;font-size:13.5px}}
.hero-nav{{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}}
.navlink{{display:inline-block;color:#fff;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.35);padding:7px 14px;border-radius:99px;text-decoration:none;font-size:13.5px}}.navlink:hover{{background:rgba(255,255,255,.26)}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-top:-40px}}
.stat{{background:var(--card);border-radius:16px;padding:16px 18px;box-shadow:0 6px 20px rgba(20,30,60,.08)}}.stat b{{font-size:28px;display:block;color:var(--acc)}}.stat span{{color:var(--mut);font-size:13.5px}}
.stat.my-stat b{{color:var(--acc2)}}
.alert-box{{margin:18px 0 0;display:grid;gap:10px}}
.alert{{background:#fef2f2;border:1px solid #fecaca;color:#7f1d1d;border-radius:14px;padding:13px 16px;font-size:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.alert.amber{{background:#fffbeb;border-color:#fde68a;color:#78350f}}
.alert a{{color:inherit;font-weight:700;text-decoration:underline}}

/* Panel de Novedades de la semana */
.novedades{{margin:20px 0 0;background:var(--card);border:1.5px solid #99f6e4;border-radius:18px;box-shadow:0 4px 16px rgba(15,118,110,.07);overflow:hidden}}
.novedades summary{{list-style:none;cursor:pointer;padding:14px 18px;background:linear-gradient(90deg,#f0fdfa 0%,#eff6ff 100%);display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
.novedades summary::-webkit-details-marker{{display:none}}
.nov-title{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:14.5px}}
.nov-badge{{background:var(--acc);color:#fff;font-weight:700;font-size:11.5px;padding:3px 9px;border-radius:99px;letter-spacing:.03em}}
.nov-pill{{background:#dbeafe;color:#1e40af;font-weight:600;font-size:12px;padding:2px 9px;border-radius:99px}}
.nov-toggle{{font-size:12.5px;color:var(--mut);font-weight:500}}
.nov-body{{padding:16px 18px}}
.nov-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}}
.nov-box{{background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
.nov-box h4{{margin:0 0 8px;font-size:13.5px;color:var(--ink)}}
.nov-box ul{{margin:0;padding-left:18px;font-size:13px;color:var(--mut);display:grid;gap:6px}}
.nov-box.sec-apply{{background:#f0fdf4;border-color:#bbf7d0}}.nov-box.sec-apply h4{{color:#166534}}
.nov-box.sec-ask{{background:#fffbeb;border-color:#fde68a}}.nov-box.sec-ask h4{{color:#92400e}}
.nov-box.sec-radar{{background:#f5f3ff;border-color:#ddd6fe}}.nov-box.sec-radar h4{{color:#5b21b6}}
.log-ref{{text-decoration:none}}.log-ref code{{background:#e0f2fe;color:#0369a1;padding:1px 5px;border-radius:5px;font-size:12px}}

h2{{margin:38px 0 6px;font-size:24px;letter-spacing:-.01em}}.sub{{color:var(--mut);margin:0 0 18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 18px 14px;display:flex;flex-direction:column;gap:10px;box-shadow:0 2px 8px rgba(20,30,60,.04);transition:transform .15s,box-shadow .15s,opacity .15s}}
.card:hover{{transform:translateY(-2px);box-shadow:0 10px 24px rgba(20,30,60,.10)}}
.card.urgent{{border:2px solid #f87171}}
.card[data-my="aplicada"]{{border-color:#22c55e;background:linear-gradient(180deg,#f0fdf4 0%,#fff 90px)}}
.card[data-my="preguntado"]{{border-color:#3b82f6;background:linear-gradient(180deg,#eff6ff 0%,#fff 90px)}}
.card[data-my="mirar"]{{border-color:#f59e0b;background:linear-gradient(180deg,#fffbeb 0%,#fff 90px)}}
.card[data-my="descartada"]{{opacity:.55}}
.card header{{display:flex;gap:12px;align-items:flex-start}}.rank{{background:var(--acc);color:#fff;font-weight:700;border-radius:12px;padding:6px 10px;font-size:15px}}
.org{{margin:0;color:var(--acc2);font-weight:600;font-size:13.5px}}.card h3{{margin:2px 0 0;font-size:17px;line-height:1.3}}
.meta{{display:flex;flex-wrap:wrap;gap:6px}}.chip,.badge{{font-size:12px;padding:3px 9px;border-radius:99px;border:1px solid var(--line);background:#f8fafc;color:var(--mut)}}
.badge.ok{{background:#ecfdf5;color:var(--ok);border-color:#a7f3d0}}.badge.warn{{background:#fffbeb;color:var(--warn);border-color:#fde68a}}
.badge.newb{{background:#dbeafe;color:#1e40af;border-color:#93c5fd;font-weight:600}}
.badge.dl-live{{display:none;font-weight:600}}
.badge.dl-live.dl-red{{display:inline-block;background:#fef2f2;color:#b91c1c;border-color:#fecaca}}
.badge.dl-live.dl-amber{{display:inline-block;background:#fffbeb;color:#b45309;border-color:#fde68a}}
.badge.dl-live.dl-ok{{display:inline-block;background:#f0fdf4;color:#15803d;border-color:#bbf7d0}}
.badge.dl-live.dl-past{{display:inline-block;background:#f1f5f9;color:#64748b;border-color:#cbd5e1;text-decoration:line-through}}
.m-hibrido{{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}}.m-presencial{{background:#f5f3ff;color:#6d28d9;border-color:#ddd6fe}}.m-remoto{{background:#ecfeff;color:#0e7490}}
.sch-morn,.sch-flex{{background:#f0fdf4;color:#166534;border-color:#bbf7d0}}
.loc-cen,.loc-train{{background:#f0f9ff;color:#0369a1;border-color:#bae6fd}}
.loc-sub{{background:#fff7ed;color:#9a3412;border-color:#fed7aa}}
.loc-car{{background:#fef2f2;color:#991b1b;border-color:#fecaca}}
dl{{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:8px 14px}}dl div{{min-width:0}}dt{{font-size:12px;color:var(--mut)}}dd{{margin:0;font-size:13.5px}}
.q{{display:inline-block;background:#fde68a;color:#78350f;border-radius:50%;width:16px;height:16px;font-size:11px;text-align:center;line-height:16px;font-weight:700}}
.fit{{background:#f0fdfa;border-radius:12px;padding:10px 12px}}.fit p{{margin:4px 0 0;font-size:13.5px}}.fitrow{{display:flex;gap:8px;align-items:center;font-size:14px}}
.stars{{color:#f59e0b;letter-spacing:2px}}.stars .off{{color:#d6dae3}}
.cav{{margin:0;font-size:13px;color:var(--mut)}}

/* Botones de acción rápida y tracker personal */
.card-actions{{display:flex;flex-wrap:wrap;gap:6px;margin-top:2px}}
.act-btn{{border:1px solid var(--line);background:#f8fafc;color:var(--ink);border-radius:8px;padding:5px 9px;font-size:12px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:4px;font-weight:500}}
.act-btn:hover{{background:#e2e8f0;border-color:#cbd5e1}}
.act-btn.sm{{padding:2px 7px;font-size:11.5px;margin-left:6px}}
.trk-bar{{background:#f8fafc;border:1px solid var(--line);border-radius:11px;padding:7px 10px;display:flex;flex-direction:column;gap:6px}}
.trk-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.trk-lbl{{font-size:12px;color:var(--mut);font-weight:500}}
.trk-sel{{border:1px solid var(--line);background:#fff;border-radius:7px;padding:4px 8px;font-size:12.5px;color:var(--ink);cursor:pointer;font-weight:500}}
.trk-note-btn{{margin-left:auto;border:1px solid var(--line);background:#fff;border-radius:7px;padding:4px 8px;font-size:12px;cursor:pointer;color:var(--mut)}}
.trk-note-btn.has-note{{background:#fef3c7;color:#92400e;border-color:#fcd34d;font-weight:600}}
.trk-note{{width:100%;border:1px solid var(--line);border-radius:7px;padding:6px 8px;font-size:12.5px;font-family:inherit;resize:vertical}}

.card footer{{margin-top:auto;display:flex;justify-content:space-between;align-items:center;gap:10px;border-top:1px dashed var(--line);padding-top:10px}}
.src{{font-size:11.5px;color:var(--mut)}}.btn{{background:var(--acc);color:#fff;text-decoration:none;padding:9px 14px;border-radius:10px;font-weight:600;font-size:14px;white-space:nowrap}}.btn:hover{{background:#115e59}}
.filters{{position:sticky;top:0;z-index:5;background:rgba(246,247,251,.95);backdrop-filter:blur(6px);padding:10px 0;border-bottom:1px solid var(--line);margin-bottom:16px}}
.frow{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:4px 0}}.frow label{{font-size:12.5px;color:var(--mut);min-width:86px;font-weight:500}}
.filters button{{border:1px solid var(--line);background:#fff;border-radius:99px;padding:5px 11px;font-size:12.5px;cursor:pointer;color:var(--ink)}}.filters button.on{{background:var(--ink);color:#fff;border-color:var(--ink)}}
.search-in{{border:1px solid var(--line);background:#fff;border-radius:99px;padding:5px 12px;font-size:12.5px;min-width:210px;color:var(--ink)}}
#count{{font-size:12.5px;color:var(--mut);margin-left:auto}}
.list{{list-style:none;padding:0;margin:0;display:grid;gap:10px}}.list li{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;display:flex;flex-direction:column;gap:3px}}
.list a{{color:var(--ink);text-decoration:none}}.list a:hover{{text-decoration:underline}}.list span{{color:var(--mut);font-size:14px}}.list em{{font-size:13px;color:var(--warn);font-style:normal}}
.srcs li{{flex-direction:row;gap:10px;align-items:flex-start}}.srcs li div{{display:flex;flex-direction:column}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}@media(max-width:820px){{.two{{grid-template-columns:1fr}}dl{{grid-template-columns:1fr}}}}
.legend{{font-size:13px;color:var(--mut)}}footer.page{{color:var(--mut);font-size:13px;text-align:center;padding:40px 20px}}
.intl-hero{{margin:56px 0 0;background:linear-gradient(135deg,#312e81 0%,#6d28d9 100%);color:#fff;border-radius:22px;padding:26px 26px 22px}}
.intl-hero h2{{margin:0 0 6px;color:#fff}}.intl-hero p{{margin:4px 0;opacity:.93}}.lp{{display:inline-block;background:#fde68a;color:#78350f;font-weight:700;font-size:12px;padding:3px 10px;border-radius:99px;margin-bottom:10px;letter-spacing:.03em}}
.ibox{{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}}.ibox span{{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.3);padding:6px 12px;border-radius:99px;font-size:13.5px}}
.timeline{{list-style:none;margin:0;padding:6px 0 6px 0;display:flex;gap:0;overflow-x:auto;scroll-snap-type:x mandatory;border-top:3px solid #c4b5fd;margin-top:18px}}
.timeline li{{flex:0 0 185px;scroll-snap-align:start;padding:10px 14px 4px 0;position:relative}}.timeline .tdot{{position:absolute;top:-16px;left:0;background:#fff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,.15);font-size:14px}}
.timeline li div{{display:flex;flex-direction:column;align-items:flex-start;gap:3px;padding-top:12px}}.timeline b{{font-size:13.5px;color:#4c1d95}}.timeline span{{font-size:12.5px;color:var(--mut)}}.timeline .k-dl b{{color:var(--red)}}
.tl-ics{{margin-top:4px;border:1px solid #ddd6fe;background:#f5f3ff;color:#5b21b6;border-radius:6px;padding:2px 7px;font-size:11px;cursor:pointer}}
.tl-ics:hover{{background:#ede9fe}}
.ifilters{{position:sticky;top:0;z-index:5;background:rgba(246,247,251,.95);backdrop-filter:blur(6px);padding:10px 0;border-bottom:1px solid var(--line);margin:18px 0 6px}}
.ifilters button{{border:1px solid var(--line);background:#fff;border-radius:99px;padding:5px 11px;font-size:12.5px;cursor:pointer;color:var(--ink)}}.ifilters button.on{{background:#4c1d95;color:#fff;border-color:#4c1d95}}.ifilters small{{opacity:.7}}
#icount{{font-size:12.5px;color:var(--mut);margin-left:auto}}
.gh{{margin:30px 0 4px;font-size:20px}}.gh .cnt{{background:#ede9fe;color:#5b21b6;border-radius:99px;font-size:13px;padding:2px 9px;vertical-align:middle}}
.icard{{border-top:4px solid #8b5cf6}}.chip.ctry{{background:#f5f3ff;color:#5b21b6;border-color:#ddd6fe}}.badge.cont{{background:#eef2ff;color:#3730a3;border-color:#c7d2fe}}
.btn2{{background:#5b21b6}}.btn2:hover{{background:#4c1d95}}.more{{font-size:14px;color:var(--mut);margin:12px 0 0}}.more a{{color:#5b21b6}}
.dropped{{columns:2;font-size:13.5px;color:var(--mut);padding-left:18px}}@media(max-width:820px){{.dropped{{columns:1}}}}

/* Modal de plantillas y backup */
.modal-backdrop{{position:fixed;inset:0;background:rgba(15,23,42,.55);z-index:50;display:none;place-items:center;padding:16px}}
.modal-backdrop.open{{display:grid}}
.modal{{background:#fff;border-radius:18px;max-width:620px;width:100%;padding:22px;box-shadow:0 20px 50px rgba(15,23,42,.25);display:flex;flex-direction:column;gap:12px}}
.modal header{{display:flex;justify-content:space-between;align-items:center;gap:10px}}
.modal h3{{margin:0;font-size:18px}}
.modal-close{{border:0;background:#f1f5f9;border-radius:99px;width:30px;height:30px;cursor:pointer;font-size:16px}}
.modal textarea{{width:100%;min-height:190px;border:1px solid var(--line);border-radius:12px;padding:12px;font-family:inherit;font-size:13.5px;line-height:1.45;resize:vertical}}
.modal-tabs{{display:flex;gap:6px;flex-wrap:wrap}}
.modal-tabs button{{border:1px solid var(--line);background:#f8fafc;border-radius:99px;padding:5px 12px;font-size:12.5px;cursor:pointer}}
.modal-tabs button.on{{background:var(--ink);color:#fff;border-color:var(--ink)}}
.modal footer{{display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap}}
.toast{{position:fixed;bottom:20px;right:20px;background:#0f172a;color:#fff;padding:10px 16px;border-radius:12px;font-size:13.5px;box-shadow:0 10px 25px rgba(0,0,0,.2);z-index:60;opacity:0;transform:translateY(10px);transition:all .2s;pointer-events:none}}
.toast.show{{opacity:1;transform:translateY(0)}}
</style></head><body>
<section class="hero"><div class="wrap">
<div class="hero-top">
  <span class="upd">Actualizado el {UPDATED}</span>
  <div class="top-tools">
    <button type="button" class="tool-btn" id="btn-sync" title="Exportar o importar tus estados y notas entre móvil y ordenador">💾 Mis notas / Backup</button>
    <button type="button" class="tool-btn" id="btn-logout" title="Borrar la contraseña guardada en este navegador">🔒 Cerrar sesión</button>
  </div>
</div>
<h1>Prácticas y becas en Madrid</h1>
<p>{H(data['profile'])}.</p>
<p>Ofertas abiertas ahora mismo, compatibles con un máster exigente.</p>
<div class="crits">{crit_html}</div>
<div class="hero-nav">
  <a class="navlink" href="#all-sec">📋 Todas las de Madrid ({n})</a>
  <a class="navlink" href="#intl">🌍 Sección internacional ({nint}) →</a>
</div>
</div></section>
<main class="wrap">
<div class="stats">
<div class="stat"><b>{n}</b><span>oportunidades en Madrid</span></div>
<div class="stat"><b>{ncum}</b><span>cumplen todos los criterios</span></div>
<div class="stat"><b>{nhyb}</b><span>híbridas</span></div>
<div class="stat"><b>{nhrs}</b><span>con horas ≤30 h confirmadas</span></div>
<div class="stat my-stat"><b id="stat-my-applied">0</b><span id="stat-my-label">aplicadas / en seguimiento</span></div>
</div>

<div id="live-alerts" class="alert-box"></div>
{novedades_html}

<h2>⭐ Top 5 para aplicar ya</h2>
<p class="sub">Ordenadas por encaje con su perfil y compatibilidad con el máster. <span class="legend">Un <span class="q">?</span> significa que la oferta no confirma ese dato y conviene preguntarlo (usa el botón <strong>💬 Copiar consulta</strong>).</span></p>
<div class="grid">{top_html}</div>

<h2 id="all-sec">Todas las oportunidades en Madrid</h2>
<div class="filters">
<div class="frow"><label>Modalidad</label><button data-f="mod" data-v="all" class="on">Todas</button>{modbtn}</div>
<div class="frow"><label>Categoría</label><button data-f="cat" data-v="all" class="on">Todas</button>{catbtn}</div>
<div class="frow"><label>Criterios</label><button data-f="st" data-v="all" class="on">Todas</button><button data-f="st" data-v="cumple">Cumplen todo</button><button data-f="st" data-v="por_confirmar">Por confirmar</button><button data-f="st" data-v="new">🆕 Nuevas</button></div>
<div class="frow"><label>Mi estado</label><button data-f="my" data-v="active" class="on">Activas (sin descartadas)</button><button data-f="my" data-v="all">Todas</button><button data-f="my" data-v="mirar">⭐ Por mirar</button><button data-f="my" data-v="preguntado">📩 Preguntado</button><button data-f="my" data-v="aplicada">✅ Aplicadas</button><button data-f="my" data-v="descartada">❌ Descartadas</button><input type="search" id="q-madrid" class="search-in" placeholder="🔎 Buscar empresa, tema, reactor..."><span id="count"></span></div>
</div>
<div class="grid" id="all">{all_html}</div>

<div class="two">
<section><h2>🔭 En el radar (no cumplen todos los criterios)</h2><p class="sub">Interesantes por tema, pero superan las 30 h o piden otro perfil.</p><ul class="list">{radar_html}</ul></section>
<section><h2>📆 Próximas convocatorias a vigilar</h2><p class="sub">Programas con el formato ideal que ahora están cerrados o requieren su acceso.</p><ul class="list">{up_html}</ul></section>
</div>

<section id="intl">
<div class="intl-hero"><span class="lp">LARGO PLAZO · FUERA DE MADRID</span>
<h2>🌍 Internacional (largo plazo)</h2>
<p>Opciones para el periodo de prácticas o el TFM del máster, no para compaginar ahora: casi todas son <strong>a jornada completa y presenciales</strong>, así que no cumplen el criterio de ≤30 h de la parte de Madrid.</p>
<p>Se han vuelto a comprobar todos los enlaces el {UPDATED}. Las ofertas cerradas o retiradas se han quitado (lista al final de la sección).</p>
<div class="ibox"><span><b>{nint}</b> oportunidades</span><span><b>{nopen}</b> abiertas ahora</span><span>Próximo cierre: <b>ITER, 13/12/2026</b></span><span>Luego: <b>CERN Summer, 21/01/2027</b></span></div>
</div>
<h3 class="gh">🗓️ Calendario de plazos</h3>
<ul class="timeline">{tl_html}</ul>
<div class="ifilters">
  <div class="frow"><label>País</label><button data-if="country" data-v="all" class="on">Todos</button>{cbtn}<button data-if="country" data-v="new">🆕 Nuevas</button></div>
  <div class="frow"><label>Mi estado</label><button data-if="my" data-v="active" class="on">Activas (sin descartadas)</button><button data-if="my" data-v="all">Todas</button><button data-if="my" data-v="mirar">⭐ Por mirar</button><button data-if="my" data-v="preguntado">📩 Preguntado</button><button data-if="my" data-v="aplicada">✅ Aplicadas</button><button data-if="my" data-v="descartada">❌ Descartadas</button><input type="search" id="q-intl" class="search-in" placeholder="🔎 Buscar laboratorio, ciudad, tema..."><span id="icount"></span></div>
</div>
{intl_groups_html}
<div class="two">
<section><h2>📆 Convocatorias internacionales a vigilar</h2><p class="sub">Programas cerrados ahora o con una segunda ronda.</p><ul class="list">{iw_html}</ul></section>
<section><h2>🗑️ Descartadas al revisar</h2><p class="sub">Cerradas, retiradas o fuera de su perfil (comprobado el {UPDATED}).</p><ul class="dropped">{idrop_html}</ul></section>
</div>
</section>

<h2>🔎 Fuentes revisadas</h2>
<p class="sub">Todos los enlaces de esta página se comprobaron el {UPDATED}. No se ha inventado ningún dato: lo que la oferta no dice aparece como "no indicado".</p>
<ul class="list srcs">{src_html}</ul>
</main>
<footer class="page">Informe preparado por Dreachambea · {UPDATED}</footer>

<!-- Modal para plantillas y backup -->
<div class="modal-backdrop" id="modal-wrap" role="dialog" aria-modal="true">
  <div class="modal">
    <header>
      <h3 id="modal-title">Plantilla de mensaje</h3>
      <button type="button" class="modal-close" id="modal-close" aria-label="Cerrar">✕</button>
    </header>
    <div class="modal-tabs" id="modal-tabs" style="display:none"></div>
    <p class="sub" id="modal-sub" style="margin:0;font-size:13px"></p>
    <textarea id="modal-text"></textarea>
    <footer id="modal-footer">
      <button type="button" class="act-btn" id="modal-copy" style="background:var(--acc);color:#fff;border-color:var(--acc);padding:8px 14px;font-size:13.5px">📋 Copiar al portapapeles</button>
    </footer>
  </div>
</div>
<div class="toast" id="toast">Copiado al portapapeles</div>

<script>
const DEADLINES = {deadlines_json};
const TRK_KEY = "dreachambea-tracker-v1";
const PW_KEY = "dreachambea-pw";

function showToast(msg) {{
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2400);
}}

/* 1. Tracker personal en localStorage */
function loadTracker() {{
  try {{ return JSON.parse(localStorage.getItem(TRK_KEY) || "{{}}"); }}
  catch(e) {{ return {{}}; }}
}}
function saveTracker(data) {{
  localStorage.setItem(TRK_KEY, JSON.stringify(data));
  syncTrackerUI();
}}
function syncTrackerUI() {{
  const data = loadTracker();
  let applied = 0, tracked = 0;
  Object.values(data).forEach(v => {{
    if (v && v.status === "aplicada") applied++;
    if (v && v.status && v.status !== "none" && v.status !== "descartada") tracked++;
  }});
  const statB = document.getElementById("stat-my-applied");
  const statL = document.getElementById("stat-my-label");
  if (statB && statL) {{
    statB.textContent = applied + " / " + tracked;
    statL.textContent = "aplicadas / en seguimiento";
  }}

  document.querySelectorAll(".card[data-id]").forEach(card => {{
    const id = card.dataset.id;
    const entry = data[id] || {{ status: "none", note: "" }};
    card.dataset.my = entry.status || "none";
    const sel = card.querySelector(".trk-sel");
    if (sel && sel.value !== (entry.status || "none")) sel.value = entry.status || "none";
    const ta = card.querySelector(".trk-note");
    if (ta && document.activeElement !== ta) ta.value = entry.note || "";
    const nbtn = card.querySelector(".trk-note-btn");
    if (nbtn) {{
      const has = Boolean(entry.note && entry.note.trim());
      nbtn.classList.toggle("has-note", has);
      nbtn.textContent = has ? "📝 Nota guardada" : "📝 Nota";
    }}
  }});
  apply();
  iapply();
}}

document.querySelectorAll(".trk-sel").forEach(sel => {{
  sel.addEventListener("change", () => {{
    const id = sel.dataset.id;
    const data = loadTracker();
    data[id] = data[id] || {{ status: "none", note: "" }};
    data[id].status = sel.value;
    saveTracker(data);
    showToast("Estado actualizado");
  }});
}});

document.querySelectorAll(".trk-note-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    const wrap = btn.closest(".trk-bar").querySelector(".trk-note-wrap");
    const open = wrap.style.display === "none";
    wrap.style.display = open ? "block" : "none";
    if (open) wrap.querySelector("textarea").focus();
  }});
}});

document.querySelectorAll(".trk-note").forEach(ta => {{
  ta.addEventListener("input", () => {{
    const id = ta.dataset.id;
    const data = loadTracker();
    data[id] = data[id] || {{ status: "none", note: "" }};
    data[id].note = ta.value;
    localStorage.setItem(TRK_KEY, JSON.stringify(data));
    const nbtn = ta.closest(".trk-bar").querySelector(".trk-note-btn");
    const has = Boolean(ta.value.trim());
    nbtn.classList.toggle("has-note", has);
    nbtn.textContent = has ? "📝 Nota guardada" : "📝 Nota";
  }});
}});

/* 2. Plazos dinámicos y alertas de cuenta atrás */
function initDeadlines() {{
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  document.querySelectorAll(".dl-live[data-dl]").forEach(b => {{
    const iso = b.dataset.dl;
    if (!iso) return;
    const [y, m, d] = iso.split("-").map(Number);
    const target = new Date(y, m - 1, d);
    const diff = Math.round((target - today) / 86400000);
    b.classList.remove("dl-red", "dl-amber", "dl-ok", "dl-past");
    if (diff < 0) {{
      b.textContent = "Plazo cerrado";
      b.classList.add("dl-past");
    }} else if (diff === 0) {{
      b.textContent = "🔥 Cierra HOY";
      b.classList.add("dl-red");
    }} else if (diff <= 7) {{
      b.textContent = `🔥 Cierra en ${{diff}} d`;
      b.classList.add("dl-red");
    }} else if (diff <= 21) {{
      b.textContent = `⏳ Cierra en ${{diff}} d`;
      b.classList.add("dl-amber");
    }} else {{
      b.textContent = `📅 En ${{diff}} d`;
      b.classList.add("dl-ok");
    }}
  }});

  // Generar banner dinámico con plazos <= 21 días
  const alertBox = document.getElementById("live-alerts");
  if (!alertBox) return;
  const upcoming = DEADLINES.map(item => {{
    const [y, m, d] = item.date.split("-").map(Number);
    const diff = Math.round((new Date(y, m - 1, d) - today) / 86400000);
    return {{ ...item, diff }};
  }}).filter(x => x.diff >= 0 && x.diff <= 21).sort((a, b) => a.diff - b.diff);

  alertBox.innerHTML = upcoming.map(u => {{
    const when = u.diff === 0 ? "cierra <strong>HOY</strong>" : `cierra en <strong>${{u.diff}} días</strong> (${{u.date.split("-").reverse().join("/")}})`;
    const cls = u.diff <= 5 ? "alert" : "alert amber";
    const icon = u.diff <= 5 ? "⏰" : "📅";
    return `<div class="${{cls}}"><span>${{icon}} <strong>[${{u.scope}}] ${{u.org}}</strong> — ${{u.title}} ${{when}} · <small>${{u.caveat}}</small></span><a href="${{u.url}}">Ver ficha →</a></div>`;
  }}).join("");
}}

/* 3. Exportador de Calendario (.ics) */
function downloadICS(title, isoDate, url, desc) {{
  const cleanDate = isoDate.replace(/-/g, "");
  const [y, m, d] = isoDate.split("-").map(Number);
  const nextDay = new Date(y, m - 1, d + 1);
  const endDate = nextDay.getFullYear().toString() +
    String(nextDay.getMonth() + 1).padStart(2, "0") +
    String(nextDay.getDate()).padStart(2, "0");
  const stamp = new Date().toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Dreachambea//Practicas//ES",
    "BEGIN:VEVENT",
    `UID:dreachambea-${{cleanDate}}-${{Math.random().toString(36).slice(2,8)}}@dreachambea`,
    `DTSTAMP:${{stamp}}`,
    `DTSTART;VALUE=DATE:${{cleanDate}}`,
    `DTEND;VALUE=DATE:${{endDate}}`,
    `SUMMARY:${{title.replace(/[,;]/g, " ")}}`,
    `DESCRIPTION:${{(desc + " — Enlace: " + url).replace(/\\n/g, " ")}}`,
    `URL:${{url}}`,
    "BEGIN:VALARM",
    "TRIGGER:-P3D",
    "ACTION:DISPLAY",
    "DESCRIPTION:Recordatorio de plazo de solicitud",
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR"
  ].join("\\r\\n");
  const blob = new Blob([ics], {{ type: "text/calendar;charset=utf-8" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `plazo-${{isoDate}}.ics`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast("Evento .ics descargado");
}}

document.querySelectorAll(".ics-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    downloadICS(btn.dataset.title, btn.dataset.date, btn.dataset.url, btn.dataset.desc || "");
  }});
}});

/* 4. Plantillas de consulta (Madrid) y contacto internacional (ES / EN / FR) */
const modalWrap = document.getElementById("modal-wrap");
const modalTitle = document.getElementById("modal-title");
const modalSub = document.getElementById("modal-sub");
const modalText = document.getElementById("modal-text");
const modalTabs = document.getElementById("modal-tabs");
const modalFooter = document.getElementById("modal-footer");

function openModal(title, sub, text, tabs = null, customFooterHtml = null) {{
  modalTitle.textContent = title;
  modalSub.textContent = sub;
  modalText.value = text;
  if (tabs && tabs.length) {{
    modalTabs.style.display = "flex";
    modalTabs.innerHTML = "";
    tabs.forEach(t => {{
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = t.label;
      if (t.active) b.classList.add("on");
      b.addEventListener("click", () => {{
        modalTabs.querySelectorAll("button").forEach(x => x.classList.remove("on"));
        b.classList.add("on");
        modalText.value = t.text;
      }});
      modalTabs.appendChild(b);
    }});
  }} else {{
    modalTabs.style.display = "none";
  }}
  if (customFooterHtml) {{
    modalFooter.innerHTML = customFooterHtml;
  }} else {{
    modalFooter.innerHTML = '<button type="button" class="act-btn" id="modal-copy" style="background:var(--acc);color:#fff;border-color:var(--acc);padding:8px 14px;font-size:13.5px">📋 Copiar al portapapeles</button>';
    document.getElementById("modal-copy").addEventListener("click", () => {{
      navigator.clipboard.writeText(modalText.value);
      showToast("Texto copiado al portapapeles");
    }});
  }}
  modalWrap.classList.add("open");
}}

document.getElementById("modal-close").addEventListener("click", () => modalWrap.classList.remove("open"));
modalWrap.addEventListener("click", e => {{ if (e.target === modalWrap) modalWrap.classList.remove("open"); }});

document.querySelectorAll(".ask-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    const org = btn.dataset.org;
    const title = btn.dataset.title;
    const hconf = btn.dataset.hconf === "true";
    const pconf = btn.dataset.pconf === "true";
    const cav = btn.dataset.cav || "";

    const questions = [];
    if (!hconf) questions.push("si existe la posibilidad de realizar las prácticas en régimen de media jornada (20–30 h/semana, preferiblemente de mañana) para compaginarlas con las clases del máster");
    if (!pconf) questions.push("cuál es la dotación de la bolsa o ayuda al estudio prevista");
    if (org.toLowerCase().includes("repsol")) questions.push("si habría opción de incorporarse en líneas de I+D del Repsol Technology Lab");
    if (org.toLowerCase().includes("eag")) questions.push("cómo indicar en la solicitud la preferencia específica por el Departamento de Seguridad (cálculos radiológicos)");
    if (questions.length === 0) questions.push("los detalles de horario y compatibilidad con el convenio de prácticas de la UPM");

    const qText = questions.length === 1
      ? "Me gustaría consultarles " + questions[0] + "."
      : "Me gustaría consultarles dos detalles que no figuran en el anuncio:\n- " + questions.map(q => q.charAt(0).toUpperCase() + q.slice(1)).join(".\n- ") + ".";

    const msg = `Hola, equipo de Selección de ${{org}}:\n\nSoy Ingeniera Química, cuento con experiencia de investigación en almacenamiento de energía en el ICMM-CSIC y actualmente curso el Máster en Ciencia y Tecnología Nuclear en la Universidad Politécnica de Madrid (UPM), con posibilidad de firmar convenio de prácticas.\n\nEstoy muy interesada en la oferta «${{title}}». ${{qText}}\n\nMuchas gracias de antemano por su tiempo y atención.\n\nUn cordial saludo,\nAndrea`;

    openModal(
      `Consulta para ${{org}}`,
      "Adaptada automáticamente según los datos pendientes de confirmar en esta ficha:",
      msg
    );
  }});
}});

document.querySelectorAll(".tpl-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    const org = btn.dataset.org;
    const title = btn.dataset.title;
    const lang = btn.dataset.lang || "en";

    const en = `Subject: Application / MSc Thesis & Internship Inquiry – ${{title}}\n\nDear Hiring Team at ${{org}},\n\nI am writing to express my strong interest in the "${{title}}" position. I hold a BSc in Chemical Engineering, have research experience in energy storage materials at ICMM-CSIC (Spanish National Research Council), and am currently pursuing an MSc in Nuclear Science and Technology at Universidad Politécnica de Madrid (UPM).\n\nMy background combines chemical engineering fundamentals, materials characterization, and nuclear engineering, which aligns closely with your topic. As a current MSc student at UPM, I can sign an official university internship / Master's Thesis agreement for the 2027 term.\n\nPlease find my CV attached. I would be delighted to discuss how my profile could contribute to your team.\n\nKind regards,\nAndrea`;

    const fr = `Objet : Candidature stage Bac+5 / Projet de fin d'études – ${{title}}\n\nMadame, Monsieur,\n\nIngénieure chimiste diplômée, avec une expérience de recherche sur les matériaux pour le stockage de l'énergie à l'ICMM-CSIC, je poursuis actuellement un Master (Bac+5) en Génie Nucléaire à l'Universidad Politécnica de Madrid (UPM).\n\nVotre offre « ${{title}} » au sein de ${{org}} correspond pleinement à mon parcours à l'interface entre le génie chimique, la science des matériaux et le nucléaire. Inscrite à l'UPM pour l'année universitaire en cours, je peux établir une convention de stage officielle pour un début en 2027.\n\nVous trouverez ci-joint mon CV. Je reste à votre entière disposition pour un entretien afin d'échanger sur ma candidature.\n\nJe vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.\n\nAndrea`;

    const es = `Asunto: Candidatura de prácticas / TFM – ${{title}}\n\nEstimado equipo de ${{org}}:\n\nSoy Ingeniera Química con experiencia de I+D en materiales para almacenamiento de energía (ICMM-CSIC) y actualmente curso el Máster en Ciencia y Tecnología Nuclear en la Universidad Politécnica de Madrid (UPM).\n\nLes escribo por mi gran interés en «${{title}}», ya que combina directamente mi formación química y de materiales con la especialización nuclear. Al estar matriculada en la UPM, puedo formalizar convenio oficial de prácticas o Trabajo Fin de Máster para 2027.\n\nAdjunto mi CV y quedo a su disposición para ampliar cualquier información.\n\nUn cordial saludo,\nAndrea`;

    const tabs = [
      {{ label: "🇫🇷 Français", text: fr, active: lang === "fr" }},
      {{ label: "🇬🇧 English", text: en, active: lang !== "fr" }},
      {{ label: "🇪🇸 Español", text: es, active: false }},
    ];
    const initial = lang === "fr" ? fr : en;
    openModal(`Plantilla de contacto · ${{org}}`, "Puedes cambiar el idioma con las pestañas y editar el texto antes de copiar:", initial, tabs);
  }});
}});

/* 5. Backup / Sincronización de progreso (JSON) */
document.getElementById("btn-sync").addEventListener("click", () => {{
  const current = JSON.stringify(loadTracker(), null, 2);
  const footerHtml = `
    <button type="button" class="act-btn" id="btn-imp-save" style="padding:8px 14px;font-size:13.5px">📥 Importar y guardar</button>
    <button type="button" class="act-btn" id="btn-exp-copy" style="background:var(--acc);color:#fff;border-color:var(--acc);padding:8px 14px;font-size:13.5px">📋 Copiar mi progreso</button>
  `;
  openModal(
    "Mis estados y notas (Backup / Sincronizar)",
    "Copia este JSON para guardarlo o pégalo en otro dispositivo (móvil / portátil) y pulsa «Importar y guardar»:",
    current,
    null,
    footerHtml
  );
  document.getElementById("btn-exp-copy").addEventListener("click", () => {{
    navigator.clipboard.writeText(modalText.value);
    showToast("Backup copiado al portapapeles");
  }});
  document.getElementById("btn-imp-save").addEventListener("click", () => {{
    try {{
      const parsed = JSON.parse(modalText.value || "{{}}");
      saveTracker(parsed);
      modalWrap.classList.remove("open");
      showToast("Progreso importado correctamente");
    }} catch (e) {{
      alert("El formato JSON no es válido.");
    }}
  }});
}});

document.getElementById("btn-logout").addEventListener("click", () => {{
  sessionStorage.removeItem(PW_KEY);
  localStorage.removeItem(PW_KEY);
  location.reload();
}});

/* 6. Filtros de Madrid e Internacional */
const st = {{ mod: 'all', cat: 'all', st: 'all', my: 'active', q: '' }};
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {{
  const f = b.dataset.f;
  st[f] = b.dataset.v;
  document.querySelectorAll(`.filters button[data-f="${{f}}"]`).forEach(x => x.classList.toggle('on', x === b));
  apply();
}}));
document.getElementById('q-madrid').addEventListener('input', e => {{
  st.q = e.target.value.trim().toLowerCase();
  apply();
}});

function matchMy(cardMy, filterMy) {{
  const val = cardMy || 'none';
  if (filterMy === 'all') return true;
  if (filterMy === 'active') return val !== 'descartada';
  return val === filterMy;
}}

function apply() {{
  let n = 0;
  document.querySelectorAll('#all .card').forEach(c => {{
    const stOk = st.st === 'all' || (st.st === 'new' ? c.dataset.new === '1' : c.dataset.status === st.st);
    const qOk = !st.q || c.textContent.toLowerCase().includes(st.q);
    const ok = (st.mod === 'all' || c.dataset.mod === st.mod) &&
               (st.cat === 'all' || c.dataset.cat.split(' ').includes(st.cat)) &&
               stOk &&
               matchMy(c.dataset.my, st.my) &&
               qOk;
    c.style.display = ok ? '' : 'none';
    if (ok) n++;
  }});
  document.getElementById('count').textContent = n + ' de {n} visibles';
}}

const ist = {{ country: 'all', my: 'active', q: '' }};
document.querySelectorAll('.ifilters button').forEach(b => b.addEventListener('click', () => {{
  const f = b.dataset.if;
  ist[f] = b.dataset.v;
  document.querySelectorAll(`.ifilters button[data-if="${{f}}"]`).forEach(x => x.classList.toggle('on', x === b));
  iapply();
}}));
document.getElementById('q-intl').addEventListener('input', e => {{
  ist.q = e.target.value.trim().toLowerCase();
  iapply();
}});

function iapply() {{
  let n = 0;
  document.querySelectorAll('#intl .icard').forEach(c => {{
    const cOk = ist.country === 'all' || (ist.country === 'new' ? c.dataset.new === '1' : c.dataset.country === ist.country);
    const qOk = !ist.q || c.textContent.toLowerCase().includes(ist.q);
    const ok = cOk && matchMy(c.dataset.my, ist.my) && qOk;
    c.style.display = ok ? '' : 'none';
    if (ok) n++;
  }});
  document.querySelectorAll('#intl .gh').forEach(h => {{
    const g = h.nextElementSibling && h.nextElementSibling.nextElementSibling;
    if (g && g.classList.contains('grid')) {{
      const v = [...g.children].some(c => c.style.display !== 'none');
      h.style.display = v ? '' : 'none';
      h.nextElementSibling.style.display = v ? '' : 'none';
    }}
  }});
  document.getElementById('icount').textContent = n + ' de {nint} visibles';
}}

initDeadlines();
syncTrackerUI();
</script></body></html>'''


def locked_page(report_html):
    if not PASSWORD_FILE.exists():
        raise SystemExit("Falta .page-password. No se publica el informe en claro.")
    password = PASSWORD_FILE.read_text(encoding="utf-8").strip()
    if not password:
        raise SystemExit(".page-password está vacío. No se publica el informe en claro.")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    ).derive(password.encode("utf-8"))
    encrypted = AESGCM(key).encrypt(nonce, report_html.encode("utf-8"), None)
    payload = base64.b64encode(salt + nonce + encrypted).decode("ascii")
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Prácticas y becas</title>
<style>
:root{{--bg:#f6f7fb;--ink:#1d2433;--mut:#5d6779;--line:#e5e8ef;--acc:#0f766e}}
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,Helvetica,Arial,sans-serif;background:linear-gradient(135deg,#0f766e 0%,#1e40af 100%);color:var(--ink)}}
form{{width:min(420px,calc(100% - 32px));background:#fff;border-radius:20px;padding:28px 24px;box-shadow:0 16px 40px rgba(15,23,42,.18)}}
h1{{margin:0 0 6px;font-size:22px}}
p{{margin:0 0 18px;color:var(--mut);font-size:14px}}
label.lbl{{display:block;font-size:13px;margin-bottom:6px}}
input[type="password"]{{width:100%;border:1px solid var(--line);border-radius:12px;padding:12px 14px;font-size:16px}}
.rem{{display:flex;align-items:center;gap:8px;margin-top:12px;font-size:13.5px;color:var(--mut);cursor:pointer}}
.rem input{{width:16px;height:16px;accent-color:var(--acc)}}
button{{margin-top:14px;width:100%;border:0;border-radius:12px;background:var(--acc);color:#fff;padding:12px 14px;font-size:15px;cursor:pointer;font-weight:600}}
button:hover{{background:#115e59}}
.err{{min-height:1.2em;margin:10px 0 0;color:#b91c1c;font-size:13px}}
</style></head><body>
<form id="gate">
<h1>Informe privado</h1>
<p>Introduce la contraseña para ver las prácticas y becas.</p>
<label class="lbl" for="pw">Contraseña</label>
<input id="pw" type="password" autocomplete="current-password" autofocus>
<label class="rem"><input id="rem" type="checkbox" checked> Recordarme en este dispositivo</label>
<button type="submit">Entrar</button>
<p class="err" id="err" role="alert"></p>
</form>
<script>
const PAYLOAD="{payload}";
const ITER={KDF_ITERATIONS};
const KEY="dreachambea-pw";
const err=document.getElementById("err");
async function openReport(pw,remember){{
 const raw=Uint8Array.from(atob(PAYLOAD),c=>c.charCodeAt(0));
 const km=await crypto.subtle.importKey("raw",new TextEncoder().encode(pw),"PBKDF2",false,["deriveKey"]);
 const key=await crypto.subtle.deriveKey({{name:"PBKDF2",salt:raw.slice(0,16),iterations:ITER,hash:"SHA-256"}},km,{{name:"AES-GCM",length:256}},false,["decrypt"]);
 const buf=await crypto.subtle.decrypt({{name:"AES-GCM",iv:raw.slice(16,28)}},key,raw.slice(28));
 sessionStorage.setItem(KEY,pw);
 if(remember)localStorage.setItem(KEY,pw);
 document.open();document.write(new TextDecoder().decode(buf));document.close();
}}
async function tryOpen(pw,remember){{
 try{{await openReport(pw,remember);}}catch(e){{sessionStorage.removeItem(KEY);localStorage.removeItem(KEY);err.textContent="Contraseña incorrecta";}}
}}
document.getElementById("gate").addEventListener("submit",e=>{{e.preventDefault();err.textContent="";tryOpen(document.getElementById("pw").value,document.getElementById("rem").checked);}});
const saved=sessionStorage.getItem(KEY)||localStorage.getItem(KEY);if(saved)tryOpen(saved,Boolean(localStorage.getItem(KEY)));
</script></body></html>'''


OUT.write_text(locked_page(page), encoding="utf-8")
print(n, ncum, nhyb, nhrs, npay, "intl", nint, nopen)
