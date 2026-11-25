# dreachambea

Informe estático de prácticas y becas (Madrid e internacional) para publicarlo con GitHub Pages desde la raíz de `main`.

## Archivos

- `index.html` — informe listo para servir.
- `data/opportunities.json` — datos de las ofertas.
- `scripts/build.py` — regenera `index.html` a partir del JSON.
- `robots.txt` — pide a los buscadores que no rastreen el sitio.
- `.nojekyll` — GitHub Pages sirve los archivos tal cual, sin procesarlos con Jekyll.

La página lleva `<meta name="robots" content="noindex, nofollow">`. El script lo vuelve a escribir cada vez que regenera el HTML.

## Regenerar el informe

Desde la raíz del repositorio, con Python 3:

```bash
python3 scripts/build.py
```

Lee `data/opportunities.json` y sobrescribe `index.html`. Edita el JSON (fecha, ofertas, textos) y vuelve a ejecutar el script.
