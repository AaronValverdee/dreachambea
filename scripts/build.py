#!/usr/bin/env python3
"""Regenera index.html a partir de data/opportunities.json."""
import base64
import html
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "opportunities.json"
OUT = ROOT / "index.html"
PASSWORD_FILE = ROOT / ".page-password"
KDF_ITERATIONS = 120_000

H = html.escape
data = json.loads(DATA.read_text(encoding="utf-8"))
UPDATED = data["updated"]
# «Nuevo» si first_seen cae en los 7 días naturales que acaban en updated
# (desde updated − 6 días hasta updated, inclusive).
UPDATED_DATE = datetime.strptime(UPDATED, "%d/%m/%Y").date()
NEW_LOOKBACK = timedelta(days=6)

def is_new(entry):
    raw = entry.get("first_seen") or ""
    try:
        seen = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return False
    return UPDATED_DATE - NEW_LOOKBACK <= seen <= UPDATED_DATE

def nuevo_html(entry):
    if not is_new(entry):
        return ""
    return '<span class="badge new">Nuevo</span>'
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

CAT={"energia":"Energía / renovables","almacenamiento":"Almacenamiento / baterías","nuclear":"Nuclear","investigacion":"I+D / investigación","consultoria":"Consultoría energética","innovacion":"Innovación"}
MOD={"hibrido":"Híbrido","remoto":"Remoto","presencial":"Presencial","no_indicado":"Sin indicar"}
modrank={"hibrido":0,"remoto":1,"no_indicado":2,"presencial":3}
opps_sorted=sorted(opps,key=lambda o:(-o["fit"],o["status"]!="cumple",modrank[o["modality"]]))
def stars(n): return '<span class="stars" aria-label="%d de 5">%s<span class="off">%s</span></span>'%(n,"★"*n,"★"*(5-n))
def card(o,rank=None):
    chips="".join('<span class="chip cat">%s</span>'%CAT[c] for c in o["categories"])
    st='<span class="badge ok">Cumple criterios</span>' if o["status"]=="cumple" else '<span class="badge warn">Algún dato por confirmar</span>'
    urgent=' urgent' if 'HOY' in o["deadline"] else ''
    def val(v,conf): return H(v)+('' if conf else ' <span class="q" title="No confirmado en la oferta">?</span>')
    return f'''<article class="card{urgent}" data-mod="{o['modality']}" data-cat="{' '.join(o['categories'])}" data-status="{o['status']}" data-new="{'1' if is_new(o) else '0'}">
  <header>{'<span class="rank">#%d</span>'%rank if rank else ''}<div><p class="org">{H(o['org'])}</p><h3>{H(o['title'])}</h3></div></header>
  <div class="meta">{nuevo_html(o)}{st}<span class="chip mod m-{o['modality']}">{MOD[o['modality']]}</span>{chips}</div>
  <dl>
   <div><dt>📍 Lugar</dt><dd>{H(o['location'])}</dd></div>
   <div><dt>🏠 Modalidad</dt><dd>{H(o['modality_label'])}</dd></div>
   <div><dt>⏱ Horas</dt><dd>{val(o['hours'],o['hours_confirmed'])}</dd></div>
   <div><dt>💶 Remuneración</dt><dd>{val(o['pay'],o['pay_confirmed'])}</dd></div>
   <div><dt>📅 Plazo</dt><dd>{H(o['deadline'])}</dd></div>
   <div><dt>🚀 Inicio</dt><dd>{H(o['start'])}</dd></div>
  </dl>
  <div class="fit"><div class="fitrow"><strong>Encaje</strong> {stars(o['fit'])}</div><p>{H(o['fit_reason'])}</p></div>
  <p class="cav">⚠️ {H(o['caveats'])}</p>
  <footer><span class="src">Fuente: {H(o['source'])} · verificado {UPDATED}</span><a class="btn" href="{H(o['url'])}" target="_blank" rel="noopener">Ver y aplicar →</a></footer>
</article>'''
n=len(opps); ncum=sum(o["status"]=="cumple" for o in opps); nhyb=sum(o["modality"]=="hibrido" for o in opps)
npay=sum(o["pay_confirmed"] for o in opps); nhrs=sum(o["hours_confirmed"] for o in opps)
nnew_madrid=sum(is_new(o) for o in opps); nnew_radar=sum(is_new(r) for r in radar); nnew_intl=sum(is_new(o) for o in intl)
nnew=nnew_madrid+nnew_radar+nnew_intl
top_html="".join(card(next(o for o in opps if o["id"]==i),k+1) for k,i in enumerate(top5))
all_html="".join(card(o) for o in opps_sorted)
radar_html="".join(f'<li data-new="{"1" if is_new(r) else "0"}">{nuevo_html(r)}<a href="{H(r["url"])}" target="_blank" rel="noopener"><strong>{H(r["org"])}</strong>: {H(r["title"])}</a><span>{H(r["why"])}</span><em>Plazo: {H(r["deadline"])}</em></li>' for r in radar)
up_html="".join(f'<li><a href="{H(u["url"])}" target="_blank" rel="noopener"><strong>{H(u["name"])}</strong></a><span>{H(u["detail"])}</span></li>' for u in upcoming)
SI={"ok":"✅","parcial":"🟡","no":"⛔"}
src_html="".join(f'<li><span class="si">{SI[s["status"]]}</span><div><strong>{H(s["name"])}</strong><span>{H(s["detail"])}</span></div></li>' for s in data["sources"])
crit_html="".join(f'<span class="crit">{H(c)}</span>' for c in data["criteria"])
catbtn="".join(f'<button data-f="cat" data-v="{k}">{v}</button>' for k,v in CAT.items())
modbtn="".join(f'<button data-f="mod" data-v="{k}">{v}</button>' for k,v in MOD.items())

CTRY={"FR":"🇫🇷 Francia","CH":"🇨🇭 Suiza","BE":"🇧🇪 Bélgica","US":"🇺🇸 EE. UU."}
IST={"abierta":('ok','Abierta'),"proxima":('warn','Abre pronto'),"continua":('cont','Continua / contacto')}
def icard(o):
    cl,lab=IST[o["status"]]
    flag=CTRY[o["country"]].split(" ")[0]
    return f"""<article class="card icard" data-country="{o['country']}" data-new="{'1' if is_new(o) else '0'}">
  <header><div><p class="org">{H(o['org'])}</p><h3>{H(o['title'])}</h3></div></header>
  <div class="meta">{nuevo_html(o)}<span class="badge {cl}">{lab}</span><span class="chip ctry">{flag} {H(o['country_label'])}</span></div>
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
  <footer><span class="src">Fuente: {H(o['source'])} · enlace comprobado {UPDATED}</span><a class="btn btn2" href="{H(o['url'])}" target="_blank" rel="noopener">Ver oferta →</a></footer>
</article>"""
GRP=[("programa","🎓 Programas estructurados con plazo","Convocatorias oficiales con fechas. Son las primeras que hay que tener en el calendario."),
     ("stage","🇫🇷 Prácticas (stages) en Francia con inicio en 2027","Ofertas concretas de CEA, ASNR, Framatome, EDF y Orano. Casi todas empiezan entre enero y abril de 2027 y duran unos 6 meses. Ordenadas por encaje."),
     ("contacto","✉️ Vía contacto directo","Sin convocatoria: se consigue escribiendo a un laboratorio o profesor con CV y propuesta de TFM.")]
intl_groups_html=""
for g,t,sub in GRP:
    items=sorted([o for o in intl if o["group"]==g],key=lambda o:(-o["fit"],o["dl_sort"] or "9999"))
    extra=""
    if g=="stage":
        extra='<p class="more">📚 Más temas en catálogos: '+" · ".join(f'<a href="{H(u)}" target="_blank" rel="noopener">{H(n)}</a>' for n,u in intl_extra_links[:2])+'</p>'
    if g=="contacto":
        extra='<p class="more">👤 Perfiles para escribir: '+" · ".join(f'<a href="{H(u)}" target="_blank" rel="noopener">{H(n)}</a>' for n,u in intl_extra_links[2:])+'</p>'
    intl_groups_html+=f'<h3 class="gh">{t} <span class="cnt">{len(items)}</span></h3><p class="sub">{sub}</p><div class="grid">{"".join(icard(o) for o in items)}</div>{extra}'
KIND={"dl":"⏳","open":"🟢","start":"🚀","info":"ℹ️"}
tl_html="".join(f'<li class="k-{k}"><span class="tdot">{KIND[k]}</span><div><b>{H(b)}</b><span>{H(c)}</span></div></li>' for a,b,c,k in intl_timeline)
iw_html="".join(f'<li><a href="{H(u["url"])}" target="_blank" rel="noopener"><strong>{H(u["name"])}</strong></a><span>{H(u["detail"])}</span></li>' for u in intl_watch)
idrop_html="".join(f'<li>{H(x)}</li>' for x in intl_dropped)
nint=len(intl); nopen=sum(o["status"]=="abierta" for o in intl)
cbtn="".join(f'<button data-c="{k}">{v} <small>{sum(o["country"]==k for o in intl)}</small></button>' for k,v in CTRY.items())
page=f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Prácticas en Madrid · {UPDATED}</title>
<style>
:root{{--bg:#f6f7fb;--card:#fff;--ink:#1d2433;--mut:#5d6779;--line:#e5e8ef;--acc:#0f766e;--acc2:#2563eb;--warn:#b45309;--ok:#15803d;--red:#b91c1c}}
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.45}}
.hero{{background:linear-gradient(135deg,#0f766e 0%,#1e40af 100%);color:#fff;padding:42px 20px 64px}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 20px}}
.hero h1{{margin:0 0 6px;font-size:clamp(26px,4vw,40px);letter-spacing:-.02em}}.hero p{{margin:4px 0;opacity:.92}}
.upd{{display:inline-block;background:rgba(255,255,255,.16);padding:4px 12px;border-radius:99px;font-size:13px;margin-bottom:14px}}
.crits{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}}.crit{{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.3);padding:6px 12px;border-radius:99px;font-size:13.5px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-top:-40px}}
.stat{{background:var(--card);border-radius:16px;padding:18px;box-shadow:0 6px 20px rgba(20,30,60,.08)}}.stat b{{font-size:30px;display:block;color:var(--acc)}}.stat span{{color:var(--mut);font-size:14px}}
.alert{{margin:22px 0 0;background:#fef2f2;border:1px solid #fecaca;color:#7f1d1d;border-radius:14px;padding:14px 18px}}
h2{{margin:42px 0 6px;font-size:24px;letter-spacing:-.01em}}.sub{{color:var(--mut);margin:0 0 18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 18px 14px;display:flex;flex-direction:column;gap:10px;box-shadow:0 2px 8px rgba(20,30,60,.04);transition:transform .15s,box-shadow .15s}}
.card:hover{{transform:translateY(-2px);box-shadow:0 10px 24px rgba(20,30,60,.10)}}.card.urgent{{border:2px solid #f87171}}
.card header{{display:flex;gap:12px;align-items:flex-start}}.rank{{background:var(--acc);color:#fff;font-weight:700;border-radius:12px;padding:6px 10px;font-size:15px}}
.org{{margin:0;color:var(--acc2);font-weight:600;font-size:13.5px}}.card h3{{margin:2px 0 0;font-size:17px;line-height:1.3}}
.meta{{display:flex;flex-wrap:wrap;gap:6px}}.chip,.badge{{font-size:12px;padding:3px 9px;border-radius:99px;border:1px solid var(--line);background:#f8fafc;color:var(--mut)}}
.badge.ok{{background:#ecfdf5;color:var(--ok);border-color:#a7f3d0}}.badge.warn{{background:#fffbeb;color:var(--warn);border-color:#fde68a}}
.badge.new{{background:#fff7ed;color:#c2410c;border-color:#fdba74;font-weight:700}}
.mini-filters{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px}}
.mini-filters button{{border:1px solid var(--line);background:#fff;border-radius:99px;padding:6px 12px;font-size:13px;cursor:pointer;color:var(--ink)}}
.mini-filters button.on{{background:var(--ink);color:#fff;border-color:var(--ink)}}
.m-hibrido{{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}}.m-presencial{{background:#f5f3ff;color:#6d28d9;border-color:#ddd6fe}}.m-remoto{{background:#ecfeff;color:#0e7490}}
dl{{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:8px 14px}}dl div{{min-width:0}}dt{{font-size:12px;color:var(--mut)}}dd{{margin:0;font-size:14px}}
.q{{display:inline-block;background:#fde68a;color:#78350f;border-radius:50%;width:16px;height:16px;font-size:11px;text-align:center;line-height:16px;font-weight:700}}
.fit{{background:#f0fdfa;border-radius:12px;padding:10px 12px}}.fit p{{margin:4px 0 0;font-size:13.5px}}.fitrow{{display:flex;gap:8px;align-items:center;font-size:14px}}
.stars{{color:#f59e0b;letter-spacing:2px}}.stars .off{{color:#d6dae3}}
.cav{{margin:0;font-size:13px;color:var(--mut)}}
.card footer{{margin-top:auto;display:flex;justify-content:space-between;align-items:center;gap:10px;border-top:1px dashed var(--line);padding-top:10px}}
.src{{font-size:11.5px;color:var(--mut)}}.btn{{background:var(--acc);color:#fff;text-decoration:none;padding:9px 14px;border-radius:10px;font-weight:600;font-size:14px;white-space:nowrap}}.btn:hover{{background:#115e59}}
.filters{{position:sticky;top:0;z-index:5;background:rgba(246,247,251,.94);backdrop-filter:blur(6px);padding:12px 0;border-bottom:1px solid var(--line);margin-bottom:16px}}
.frow{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:4px 0}}.frow label{{font-size:13px;color:var(--mut);min-width:86px}}
.filters button{{border:1px solid var(--line);background:#fff;border-radius:99px;padding:6px 12px;font-size:13px;cursor:pointer;color:var(--ink)}}.filters button.on{{background:var(--ink);color:#fff;border-color:var(--ink)}}
#count{{font-size:13px;color:var(--mut);margin-left:auto}}
.list{{list-style:none;padding:0;margin:0;display:grid;gap:10px}}.list li{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;display:flex;flex-direction:column;gap:3px}}
.list a{{color:var(--ink);text-decoration:none}}.list a:hover{{text-decoration:underline}}.list span{{color:var(--mut);font-size:14px}}.list em{{font-size:13px;color:var(--warn);font-style:normal}}
.srcs li{{flex-direction:row;gap:10px;align-items:flex-start}}.srcs li div{{display:flex;flex-direction:column}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}@media(max-width:820px){{.two{{grid-template-columns:1fr}}dl{{grid-template-columns:1fr}}}}
.legend{{font-size:13px;color:var(--mut)}}footer.page{{color:var(--mut);font-size:13px;text-align:center;padding:40px 20px}}
.navlink{{display:inline-block;margin-top:14px;color:#fff;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.35);padding:7px 14px;border-radius:99px;text-decoration:none;font-size:14px}}.navlink:hover{{background:rgba(255,255,255,.26)}}
.intl-hero{{margin:56px 0 0;background:linear-gradient(135deg,#312e81 0%,#6d28d9 100%);color:#fff;border-radius:22px;padding:26px 26px 22px}}
.intl-hero h2{{margin:0 0 6px;color:#fff}}.intl-hero p{{margin:4px 0;opacity:.93}}.lp{{display:inline-block;background:#fde68a;color:#78350f;font-weight:700;font-size:12px;padding:3px 10px;border-radius:99px;margin-bottom:10px;letter-spacing:.03em}}
.ibox{{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}}.ibox span{{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.3);padding:6px 12px;border-radius:99px;font-size:13.5px}}
.timeline{{list-style:none;margin:0;padding:6px 0 0 0;display:flex;gap:0;overflow-x:auto;scroll-snap-type:x mandatory;border-top:3px solid #c4b5fd;margin-top:18px}}
.timeline li{{flex:0 0 170px;scroll-snap-align:start;padding:10px 12px 4px 0;position:relative}}.timeline .tdot{{position:absolute;top:-16px;left:0;background:#fff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,.15);font-size:14px}}
.timeline li div{{display:flex;flex-direction:column;padding-top:12px}}.timeline b{{font-size:14px;color:#4c1d95}}.timeline span{{font-size:13px;color:var(--mut)}}.timeline .k-dl b{{color:var(--red)}}
.ifilters{{position:sticky;top:0;z-index:5;background:rgba(246,247,251,.94);backdrop-filter:blur(6px);padding:12px 0;border-bottom:1px solid var(--line);margin:18px 0 6px}}
.ifilters button{{border:1px solid var(--line);background:#fff;border-radius:99px;padding:6px 12px;font-size:13px;cursor:pointer;color:var(--ink)}}.ifilters button.on{{background:#4c1d95;color:#fff;border-color:#4c1d95}}.ifilters small{{opacity:.7}}
#icount{{font-size:13px;color:var(--mut);margin-left:auto}}
.gh{{margin:30px 0 4px;font-size:20px}}.gh .cnt{{background:#ede9fe;color:#5b21b6;border-radius:99px;font-size:13px;padding:2px 9px;vertical-align:middle}}
.icard{{border-top:4px solid #8b5cf6}}.chip.ctry{{background:#f5f3ff;color:#5b21b6;border-color:#ddd6fe}}.badge.cont{{background:#eef2ff;color:#3730a3;border-color:#c7d2fe}}
.btn2{{background:#5b21b6}}.btn2:hover{{background:#4c1d95}}.more{{font-size:14px;color:var(--mut);margin:12px 0 0}}.more a{{color:#5b21b6}}
.dropped{{columns:2;font-size:13.5px;color:var(--mut);padding-left:18px}}@media(max-width:820px){{.dropped{{columns:1}}}}
</style></head><body>
<section class="hero"><div class="wrap">
<span class="upd">Actualizado el {UPDATED}</span>
<h1>Prácticas y becas en Madrid</h1>
<p>{H(data['profile'])}.</p>
<p>Ofertas abiertas ahora mismo, compatibles con un máster exigente.</p>
<div class="crits">{crit_html}</div>
<a class="navlink" href="#intl">🌍 Más abajo: sección internacional (largo plazo) →</a>
</div></section>
<main class="wrap">
<div class="stats">
<div class="stat"><b>{n}</b><span>oportunidades verificadas</span></div>
<div class="stat"><b>{ncum}</b><span>cumplen todos los criterios confirmados</span></div>
<div class="stat"><b>{nhyb}</b><span>híbridas</span></div>
<div class="stat"><b>{nhrs}</b><span>con horas ≤30 h confirmadas</span></div>
<div class="stat"><b>{npay}</b><span>con remuneración confirmada</span></div>
<div class="stat"><b>{nnew}</b><span>nuevas en Madrid, radar e internacional</span></div>
</div>
<div class="alert">⏰ <strong>Urgente:</strong> la plaza de baterías de ion-Na de la UAM (10 h/semana, 600 €/mes) cierra <strong>hoy, 25/11</strong>. Exige tener ya un Máster terminado.</div>

<h2>⭐ Top 5 para aplicar ya</h2>
<p class="sub">Ordenadas por encaje con su perfil y compatibilidad con el máster. <span class="legend">Un <span class="q">?</span> significa que la oferta no confirma ese dato y conviene preguntarlo.</span></p>
<div class="grid">{top_html}</div>

<h2>Todas las oportunidades</h2>
<div class="filters">
<div class="frow"><label>Modalidad</label><button data-f="mod" data-v="all" class="on">Todas</button>{modbtn}</div>
<div class="frow"><label>Categoría</label><button data-f="cat" data-v="all" class="on">Todas</button>{catbtn}</div>
<div class="frow"><label>Criterios</label><button data-f="st" data-v="all" class="on">Todas</button><button data-f="st" data-v="cumple">Cumplen todo</button><button data-f="st" data-v="por_confirmar">Con datos por confirmar</button><span id="count"></span></div>
<div class="frow"><label>Novedad</label><button data-f="nw" data-v="all" class="on">Todas</button><button data-f="nw" data-v="new">Solo nuevas</button></div>
</div>
<div class="grid" id="all">{all_html}</div>

<div class="two">
<section><h2>🔭 En el radar (no cumplen todos los criterios)</h2><p class="sub">Interesantes por tema, pero superan las 30 h o piden otro perfil. <span class="legend">{nnew_radar} nuevas.</span></p><div class="mini-filters" id="radar-filters"><button data-r="all" class="on">Todas</button><button data-r="new">Solo nuevas</button></div><ul class="list" id="radar">{radar_html}</ul></section>
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
<div class="ifilters"><div class="frow"><label>País</label><button data-c="all" class="on">Todos</button>{cbtn}<span id="icount"></span></div><div class="frow"><label>Novedad</label><button data-n="all" class="on">Todas</button><button data-n="new">Solo nuevas</button></div></div>
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
<script>
const st={{mod:'all',cat:'all',st:'all',nw:'all'}};
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{{
 const f=b.dataset.f;st[f]=b.dataset.v;document.querySelectorAll(`.filters button[data-f="${{f}}"]`).forEach(x=>x.classList.toggle('on',x===b));apply();}}));
function apply(){{let n=0;document.querySelectorAll('#all .card').forEach(c=>{{
 const ok=(st.mod==='all'||c.dataset.mod===st.mod)&&(st.cat==='all'||c.dataset.cat.split(' ').includes(st.cat))&&(st.st==='all'||c.dataset.status===st.st)&&(st.nw==='all'||c.dataset.new==='1');
 c.style.display=ok?'':'none';if(ok)n++;}});document.getElementById('count').textContent=n+' de {n} visibles';}}
apply();
document.querySelectorAll('#radar-filters button').forEach(b=>b.addEventListener('click',()=>{{
 document.querySelectorAll('#radar-filters button').forEach(x=>x.classList.toggle('on',x===b));
 const only=b.dataset.r==='new';
 document.querySelectorAll('#radar li').forEach(li=>{{li.style.display=!only||li.dataset.new==='1'?'':'none';}});
}}));
let ic='all', inew='all';
document.querySelectorAll('.ifilters button[data-c]').forEach(b=>b.addEventListener('click',()=>{{ic=b.dataset.c;document.querySelectorAll('.ifilters button[data-c]').forEach(x=>x.classList.toggle('on',x===b));iapply();}}));
document.querySelectorAll('.ifilters button[data-n]').forEach(b=>b.addEventListener('click',()=>{{inew=b.dataset.n;document.querySelectorAll('.ifilters button[data-n]').forEach(x=>x.classList.toggle('on',x===b));iapply();}}));
function iapply(){{let n=0;document.querySelectorAll('#intl .icard').forEach(c=>{{const ok=(ic==='all'||c.dataset.country===ic)&&(inew==='all'||c.dataset.new==='1');c.style.display=ok?'':'none';if(ok)n++;}});
document.querySelectorAll('#intl .gh').forEach(h=>{{const g=h.nextElementSibling&&h.nextElementSibling.nextElementSibling;if(g&&g.classList.contains('grid')){{const v=[...g.children].some(c=>c.style.display!=='none');h.style.display=v?'':'none';h.nextElementSibling.style.display=v?'':'none';}}}});
document.getElementById('icount').textContent=n+' de {nint} visibles';}}
iapply();
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
label{{display:block;font-size:13px;margin-bottom:6px}}
input{{width:100%;border:1px solid var(--line);border-radius:12px;padding:12px 14px;font-size:16px}}
button{{margin-top:14px;width:100%;border:0;border-radius:12px;background:var(--acc);color:#fff;padding:12px 14px;font-size:15px;cursor:pointer}}
button:hover{{background:#115e59}}
.err{{min-height:1.2em;margin:10px 0 0;color:#b91c1c;font-size:13px}}
</style></head><body>
<form id="gate">
<h1>Informe privado</h1>
<p>Introduce la contraseña para ver las prácticas y becas.</p>
<label for="pw">Contraseña</label>
<input id="pw" type="password" autocomplete="current-password" autofocus>
<button type="submit">Entrar</button>
<p class="err" id="err" role="alert"></p>
</form>
<script>
const PAYLOAD="{payload}";
const ITER={KDF_ITERATIONS};
const KEY="dreachambea-pw";
const err=document.getElementById("err");
async function openReport(pw){{
 const raw=Uint8Array.from(atob(PAYLOAD),c=>c.charCodeAt(0));
 const km=await crypto.subtle.importKey("raw",new TextEncoder().encode(pw),"PBKDF2",false,["deriveKey"]);
 const key=await crypto.subtle.deriveKey({{name:"PBKDF2",salt:raw.slice(0,16),iterations:ITER,hash:"SHA-256"}},km,{{name:"AES-GCM",length:256}},false,["decrypt"]);
 const buf=await crypto.subtle.decrypt({{name:"AES-GCM",iv:raw.slice(16,28)}},key,raw.slice(28));
 sessionStorage.setItem(KEY,pw);
 document.open();document.write(new TextDecoder().decode(buf));document.close();
}}
async function tryOpen(pw){{
 try{{await openReport(pw);}}catch(e){{sessionStorage.removeItem(KEY);err.textContent="Contraseña incorrecta";}}
}}
document.getElementById("gate").addEventListener("submit",e=>{{e.preventDefault();err.textContent="";tryOpen(document.getElementById("pw").value);}});
const saved=sessionStorage.getItem(KEY);if(saved)tryOpen(saved);
</script></body></html>'''

OUT.write_text(locked_page(page), encoding="utf-8")
print(n, ncum, nhyb, nhrs, npay, "intl", nint, nopen, "nuevas", nnew, nnew_madrid, nnew_radar, nnew_intl)
