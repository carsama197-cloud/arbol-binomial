# Árbol binomial animado

Página interactiva para aprender el árbol binomial, Black-Scholes y Montecarlo con datos reales de 17 empresas y ETF (SPY, QQQ, AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AMD, NFLX, JPM, KO, PEP, WMT, DIS y KOF). Se elige la empresa con un buscador.

Ver en línea: https://carsama197-cloud.github.io/arbol-binomial/

## Datos
- `datos.js` tiene precios diarios de 5 años, cadenas de opciones, VIX y la tasa ^IRX, bajados de Yahoo Finance.
- `actualizar_datos.py` los vuelve a bajar. Para agregar o quitar empresas se edita la lista `EMPRESAS`.
- `.github/workflows/actualizar-datos.yml` lo corre solo cada día hábil después del cierre y sube `datos.js`. También se puede correr a mano desde la pestaña **Actions → Actualizar datos de mercado → Run workflow**.
