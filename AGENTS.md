# Flujo semanal de dreachambea

Este archivo es el procedimiento del agente que mantiene el informe. Una pasada a la semana. No se rehace la investigación desde cero.

El informe público sale de `data/opportunities.json`. `scripts/build.py` regenera `index.html`. El historial de lo ya mirado está en `data/research-log.md`.

## Qué no hacer

- No inventar horas, sueldo, plazo, modalidad ni sede. Si la oferta no lo dice, escríbelo como «No indicada» y baja `hours_confirmed` o `pay_confirmed`.
- No copiar un plazo que solo aparece en un agregador (Eurojobs, Joinrs, Jobijoba, Indeed, SpainJobs) si la empresa no lo publica.
- No poner como enlace de «Ver y aplicar» una web agregadora. El `url` tiene que ser el portal de la empresa, la universidad o el organismo.
- No crear una ficha nueva si ya existe el mismo `id` o el mismo anuncio.
- No meter en `opportunities` un puesto de más de 30 h/semana. Eso va a `radar` (Madrid, jornada completa) o a `international` (práctica o TFM fuera, a jornada completa).
- No enviar candidaturas, ni escribir a empresas, ni redactar cartas, salvo que Aaron lo pida en ese mensaje.
- No hacer commit ni push salvo que Aaron lo pida.
- No quitar `<meta name="robots" content="noindex, nofollow">`.

## Perfil fijo

Ingeniera Química, máster en Ingeniería Nuclear (UPM), experiencia de I+D en almacenamiento de energía (ICMM-CSIC). Sigue matriculada: las prácticas tienen que poder hacerse por convenio.

Dos bloques, con reglas distintas:

**Madrid, para compaginar con el máster.** Híbrido mejor que remoto, remoto mejor que presencial. Tema: química, energía o investigación. Tope de 30 h/semana. Remunerada. Fuera la ingeniería de procesos pura (diseño de plantas, HYSYS, tuberías, EPC).

**Internacional, para el periodo de prácticas o el TFM.** Aquí sí vale jornada completa y presencial. Prioridad: laboratorio, materiales, radioquímica, combustible, fusión y residuos. Después, análisis nuclear si está pagado y encaja en el calendario. Francia primero; luego Suiza, Bélgica y organismos europeos. Estados Unidos solo si no exigen permiso de trabajo estadounidense.

No abras el perfil. Una oferta de finanzas, personas, datos o ciberseguridad no entra aunque la publique una energética.

## Cada semana, en este orden

Presupuesto: una sesión. Si LinkedIn devuelve 429 o un portal pide captcha, anótalo en el log y sigue. No reintentes.

1. Lee este archivo, la última entrada de `data/research-log.md` y las claves `updated`, `top5`, `radar`, `upcoming` e `international.timeline` del JSON.
2. **Plazos.** Abre cada ficha cuya fecha caiga en los próximos 21 días, y cualquier fila del calendario de abajo que esté en ventana. Si el enlace es 404, la oferta está cerrada o ya no cumple, sácala de la lista activa y escribe una línea en `dropped` o en el log. No dejes una ficha «abierta» con el enlace muerto.
3. **Un solo carril.** Semana ISO módulo 4. Haz ese carril y los pendientes que el log marque para esta semana. No recorras los otros tres.
4. **Puntúa y edita** el JSON con las reglas de más abajo. Fecha `updated` en `DD/MM/AAAA`.
5. Desde la raíz del repo: `python scripts/build.py`. Tiene que terminar sin error.
6. Añade **arriba** del log una entrada nueva con el formato de abajo. En el chat, entrega ese mismo resumen a Aaron.

Carriles (`semana_ISO % 4`):

| Resto | Carril | Qué mirar |
| --- | --- | --- |
| 0 | Tableros de Madrid | LinkedIn, Talentoteca, InfoJobs, Indeed, Euraxess, COIE |
| 1 | Energéticas de Madrid | Portales de empresa de la lista A |
| 2 | Nuclear y laboratorios | Lista B |
| 3 | Internacional | Lista C y los PDF de CEA |

La semana 48 de 2026 (la del 25/11) no hizo el carril 0: hizo un pase de huecos. Si el run cae aún en la semana 48, haz el carril 0 y no repitas ese pase.

## Cómo buscar

En LinkedIn: prácticas, becario o beca, más energía, nuclear, baterías, hidrógeno, I+D o radioquímica, ubicación Madrid, último mes, tipo internship. Unas 15 fichas relevantes o hasta el primer 429. Luego pasa a portales de empresa.

En Talentoteca (`https://www.talentoteca.es/finder`): Madrid, prácticas, química, energía o nuclear. Abre la ficha. Si pone 35 h, 7 h/día o jornada completa, no va a `opportunities`.

En InfoJobs e Indeed: una búsqueda, «prácticas energía Madrid» y otra «beca I+D química Madrid». Una página de resultados. Si hay captcha, log y fuera.

Euraxess: Madrid, chemistry o nuclear, research fellow / internship. Sirve sobre todo para contratos de investigación, que casi nunca cumplen las 30 h: van a `radar` si el tema es muy afín.

COIE de la UPM: hace falta la cuenta de Aaron. Si no hay sesión, escríbelo en «No se pudo revisar». No inventes las ofertas de dentro.

Para una empresa que ya está en el JSON, abre primero el `url` guardado. Solo crea otra ficha si el anuncio es otro puesto.

## Lista A — energéticas (carril 1)

Prioridad, en este orden. La primera pendiente del log manda sobre el orden.

- Repsol. Workday ya enlazado en el JSON. Preguntar siempre por media jornada en Technology Lab, no por data o estrategia.
- Iberdrola. Alumni y prácticas. El JSON ya tiene el anuncio de 2027.
- Naturgy. Impulsa y, aparte, generación renovable. El anuncio de data y renewables (Power BI, Databricks, 20–25 h) es otro puesto: perfil de datos, no de química. No lo subas de `radar` salvo que el trabajo real sea de energía química.
- ACCIONA. Innovación en energía y la beca de I+D en agua. Hay otra de inversiones y estrategia en economía circular: no es laboratorio.
- Moeve, programa Welcome U. Pendiente del 25/11/2026: varios agregadores describen «Analytical Innovation» en el Centro de Innovación de Madrid para ingeniería química (biomasa, biometano, hidrógeno, Py-GC-MS, remunerada, mínimo 6 meses, presencial). No está en el informe porque no apareció en moeve.com y los agregadores no coinciden en el plazo ni dicen las horas. Entra solo con el enlace oficial y las horas leídas ahí.
- Endesa / Enel, `https://jobs.enel.com`. El programa SWING visto el 25/11/2026 es de 35 h o 7 h/día (finanzas, terrenos, medio ambiente) e incluye un máster propio. Radar solo si el tema es químico; si no, ni radar.
- Siemens. WeSTEM ya está en el JSON.
- Redeia. START suele ser jornada completa y, a menudo, de otras titulaciones.
- Enagás, Ignis, Sonnedix, Creara. Ya hubo fichas; reabrir el enlace, no duplicar.
- Segunda tanda, solo si la prioridad cupo en la sesión: Capital Energy, Grenergy, Solaria, Statkraft España, Engie España, EDP España, Fertiberia (hidrógeno), Air Liquide, Carburos Metálicos, Linde, Nippon Gases. Misma criba de horas y de «no es diseño de plantas».

## Lista B — nuclear y laboratorios (carril 2)

- EAG (Empresarios Agrupados – GHESA), `https://empre.teamtailor.com/`. La beca de estudiantes ya está en el JSON. Vigilar si publican sueldo o si separan el Departamento de Seguridad.
- Westinghouse Electric Spain (San Sebastián de los Reyes) y Tecnatom.
- Framatome España (Pozuelo). La de IA que ya está en `radar` era de 35 h.
- ENRESA, `https://www.enresa.es/empleo-trabaja-con-nosotros/`. La práctica de El Cabril de 2026 era de obra civil y ya cerró en julio. Buscar una beca de máster, no reabrir esa.
- ENUSA.
- CSN, `https://www.csn.es/becas`. La última convocatoria colgada es la de 2024 (BOE de abril, cierre en junio). Mirar el BOE en primavera. Mientras no haya extracto nuevo, no hay ficha.
- CIEMAT (Moncloa). Separar prácticas universitarias de las de FP. Las de FP no entran.
- CSIC. JAE Intro en `https://sede.csic.gob.es`. Institutos: ICMM, ICP, IQFR, IEM, CENIM. JAE Intro 2026 cerró del 12/03 al 11/04; la de 2027 se espera hacia marzo, sin fecha oficial.
- IMDEA Energía, IMDEA Materiales (`https://jobs.materials.imdea.org/internship`) e IMDEA Nanociencia. La convocatoria de prácticas de IMDEA Energía 2027 cerró el 07/11/2026; vuelve en otoño.
- UAM, convocatorias conjuntas de investigación, cada mes: `https://www.uam.es/uam/investigacion/ofertas-empleo`. UPM HRS4R. UC3M, UCM, URJC y UAH.
- IDAE.
- Técnicas Reunidas, `https://www.tecnicasreunidas.es/es/empleo/programas-practicas/` y su portal de empleo. IDOM, Sener y GDES. Casi todo es EPC o proceso: radar como mucho, y solo si el texto es nuclear o de I+D, no de tuberías.

ENS A (Maliaño) queda fuera de Madrid. Una práctica de ciberseguridad que apareció en 2026 no es de este perfil.

## Lista C — internacional (carril 3)

Programas con fecha, en el orden del calendario:

- ITER, `https://www.iter.org/public/jobs/internships`. Ola 1 hasta el 13/12/2026. Ola 2 del 01/03 al 28/03/2027.
- PSI Summer Student, `https://www.psi.ch/en/summerstudents/activities`. Abre a mediados de diciembre de 2026. Programa central 02/07–20/08/2027.
- CERN Summer, `https://careers.cern`. Cierra el 21/01/2027 a las 23:59 de Ginebra. El slug de la oferta puede seguir diciendo 2026: lee el título, que es 2027. Inicio ideal 14/06/2027. Hace falta seguir matriculada, no estar en doctorado, y llevar al menos 3 años de carrera.
- CERN Short Term Internship. Abierta el año entero; el ciclo visto cierra el 01/11/2027.
- CERN Technical Studentship. Mirar si hay ronda nueva. La 2027-1 cerró el 16/10/2026.
- F4E, `https://fusionforenergy.europa.eu/traineeships/`. La convocatoria 2026-2027 cerró el 12/05/2026 y la web sigue en «applications are now closed». La siguiente, si repite el patrón, cae en primavera. Barcelona 1.400 €/mes.
- JRC Graduate Trainees, `https://recruitment.jrc.ec.europa.eu/graduate-trainees`. Cerró el 28/10/2026.
- OCDE, prácticas continuas, `https://www.oecd.org/en/about/careers/internships.html`. La NEA y la IEA están en la lista oficial. 1.000 € por mes completo en París, 1–6 meses, 40 h, tiempo parcial solo como excepción (mínimo 20 h). Hace falta matrícula durante toda la estancia. El proceso tarda hasta unos tres meses.
- IAEA, `https://www.iaea.org/about/employment/internships`. No hay una convocatoria anual: cada plaza tiene su cierre en el tablón. 1.450 €/mes a jornada completa, 3–12 meses, dos cartas firmadas. Química, materiales y nuclear entran en los campos habituales. No des por buena una plaza que solo citan Impactpool u otra bolsa.
- SCK CEN, temas de TFM en continuo.
- EPFL LRS y PSI LNM: no hay convocatoria. Solo se anota el contacto; no se escribe un correo salvo que Aaron lo pida.
- CEA. Volver a descargar el catálogo DAM y el PDF de IRESNE que están en `international.extra_links`. No reutilices identificadores de oferta del mes pasado: se retiran sin avisar.
- ASNR, Framatome, EDF (división de combustible y DP2D) y Orano. Andra, sobre todo corrosión y Cigéo.
- newcleo, Jimmy Energy y Stellaria: solo la web de empleo de cada una. Naarea no se busca: liquidación en 2026 y el proyecto XAMR se abandonó.
- EUROfusion, Max-Planck-IPP (Garching), KIT y NRG (Petten).
- UKAEA, `https://careers.ukaea.uk/early-careers/`. El graduate de 2027 cerró en octubre de 2026. FOSTER paga a universidades del Reino Unido para que ellas contraten a estudiantes británicos de grado: no es una solicitud desde la UPM.

## Calendario que sí o sí se comprueba

Ignora la fila si la ventana no está abierta.

| Cuándo | Comprobar |
| --- | --- |
| Hasta el 13/12/2026 | ITER, ola 1, sigue abierta |
| Mediados de diciembre 2026 | PSI Summer 2027 ha abierto |
| 31/12/2026 | La vacante continua de la OCDE se ha republicado |
| Hasta el 21/01/2027 | CERN Summer sigue abierta |
| Febrero 2027 | Catálogos CEA, ASNR, Framatome, EDF y Orano, porque la mayoría de stages empiezan ese mes |
| Febrero y marzo 2027 | JAE Intro en la sede del CSIC, cada semana de esos dos meses |
| 01–28/03/2027 | ITER, ola 2 |
| Primavera | CSN en el BOE, F4E, IMDEA Materiales |
| Otoño | IMDEA Energía, prácticas del año siguiente |
| Todo el año | CERN Short Term, tablón de la IAEA, OCDE, SCK CEN |

## Cómo decidir si entra

Madrid, ficha en `opportunities`, solo si se cumplen las cuatro:

- Sede en Madrid o híbrido con base en Madrid.
- Convenio de estudiante (no pide el máster ya terminado, ni un contrato laboral de jornada completa).
- El trabajo es química, energía de I+D o nuclear. No es diseño de proceso, ni finanzas, ni personas, ni datos, ni informática.
- Las horas publicadas son ≤ 30, o no están publicadas.

Si las horas no están o el sueldo no está, `status` es `por_confirmar`. `cumple` solo cuando horas, sueldo, sede y tema están confirmados y la oferta sigue abierta.

Si las horas publicadas pasan de 30 y el tema es muy afín, va a `radar` con el motivo en una frase. Si es práctica o TFM de 2027 fuera de Madrid, va a `international`.

`fit` de 1 a 5:

- 5. Tema, horas, sueldo y modalidad encajan, y hay un plazo real.
- 4. El tema encaja fuerte y falta un dato importante, o es presencial.
- 3. Es del campo, pero con varias incógnitas o un trabajo adyacente.
- 2. Tema débil o casi seguro a jornada completa.
- 1. No la pongas.

`top5` son cinco `id`. Cambia el orden solo si la ficha nueva tiene `fit` ≥ 4 y las horas confirmadas dentro del tope. Di en el log quién sale y por qué.

En internacional, `group` es `programa`, `stage` o `contacto`. `status` es `abierta`, `proxima` o `continua`. `country` solo puede ser `FR`, `CH`, `BE` o `US`, porque el HTML no tiene más banderas. Otro país se anota en el log y, si de verdad merece ficha, primero se añade su clave en `build.py` (`CTRY`) y en el JSON.

## Campos que no se dejan a medias

Madrid: `id`, `org`, `title`, `location`, `modality` (`hibrido`, `remoto`, `presencial`, `no_indicado`), `modality_label`, `hours`, `hours_confirmed`, `pay`, `pay_confirmed`, `deadline`, `start`, `fit`, `fit_reason`, `caveats`, `categories` (solo `energia`, `almacenamiento`, `nuclear`, `investigacion`, `consultoria`, `innovacion`), `status` (`cumple` o `por_confirmar`), `url`, `source`, `verified_on` (`AAAA-MM-DD`).

Internacional: `id`, `group`, `country`, `country_label`, `org`, `title`, `location`, `deadline`, `dl_sort` (`AAAA-MM-DD` o `continua`), `start`, `duration`, `pay`, `hours`, `fit`, `status`, `why`, `req`, `url`, `source`.

`id` en minúsculas y guiones, estable entre semanas.

Textos del informe en español, como el resto de la página.

## Log

Inserta la entrada nueva al principio de `data/research-log.md`:

```
## AAAA-MM-DD · carril N · semana ISO

Aplicar esta semana:
- Org — puesto — por qué ahora — url

Preguntar antes de aplicar:
- Org — qué falta (horas, sueldo, departamento)

Radar o largo plazo:
- Org — puesto — por qué no va a la lista de Madrid

Descartadas:
- Org — motivo en una frase

No se pudo revisar:
- Fuente — motivo (429, captcha, login)

Pendiente para el próximo run:
- Una acción concreta
```

Si una lista va vacía, pon «Ninguna». No dejes la sección fuera.
