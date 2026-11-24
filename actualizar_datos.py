# Baja de Yahoo Finance los precios y las opciones de la lista de empresas
# y escribe datos.js, que la página carga al abrir.
# Lo corre GitHub Actions cada día hábil (.github/workflows/actualizar-datos.yml);
# también se puede correr a mano:  python actualizar_datos.py
#
# Para agregar o quitar empresas solo se edita la lista EMPRESAS.
import json, os, re, sys, datetime as dt
import pandas as pd
import yfinance as yf

EMPRESAS = {
    # ticker: (nombre, descripción corta)
    'SPY':   ('ETF S&P 500', 'El mercado completo'),
    'QQQ':   ('ETF Nasdaq 100', 'Las 100 tecnológicas'),
    'AAPL':  ('Apple', 'Tecnológica grande'),
    'MSFT':  ('Microsoft', 'Software y nube'),
    'NVDA':  ('Nvidia', 'Chips para IA'),
    'AMZN':  ('Amazon', 'Comercio y nube'),
    'GOOGL': ('Alphabet', 'Google'),
    'META':  ('Meta', 'Facebook e Instagram'),
    'TSLA':  ('Tesla', 'Muy volátil'),
    'AMD':   ('AMD', 'Chips, muy volátil'),
    'NFLX':  ('Netflix', 'Streaming'),
    'JPM':   ('JPMorgan', 'Banco'),
    'KO':    ('Coca-Cola', 'Consumo estable'),
    'PEP':   ('PepsiCo', 'Consumo estable'),
    'WMT':   ('Walmart', 'Supermercados'),
    'DIS':   ('Disney', 'Entretenimiento'),
    'KOF':   ('Coca-Cola FEMSA', 'Mexicana (ADR), pocas opciones'),
}
PLAZOS = {'1M': 30, '3M': 91, '6M': 182, '12M': 365}   # días objetivo de cada plazo
MAX_STRIKES = 17
AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, 'datos.js')
SECTOR = {'Technology': 'Tecnología', 'Communication Services': 'Comunicaciones', 'Consumer Cyclical': 'Consumo cíclico',
          'Consumer Defensive': 'Consumo básico', 'Financial Services': 'Servicios financieros', 'Healthcare': 'Salud',
          'Industrials': 'Industria', 'Energy': 'Energía', 'Basic Materials': 'Materiales', 'Real Estate': 'Bienes raíces',
          'Utilities': 'Servicios públicos'}
BOLSA = {'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NCM': 'NASDAQ', 'NYQ': 'NYSE', 'PCX': 'NYSE Arca', 'ASE': 'NYSE American', 'BTS': 'Cboe'}


def ficha(t):
    """Datos de la empresa para el panel del buscador. Si Yahoo no los da, quedan vacíos (no rompe nada)."""
    try:
        i = yf.Ticker(t).info
    except Exception:
        return {}
    num = lambda k: (float(i[k]) if isinstance(i.get(k), (int, float)) else None)
    etf = i.get('quoteType') == 'ETF'
    return {'long': i.get('longName') or i.get('shortName'), 'kind': 'ETF' if etf else 'Acción',
            'exch': BOLSA.get(i.get('exchange'), i.get('fullExchangeName')),
            'sector': (i.get('category') if etf else SECTOR.get(i.get('sector'), i.get('sector'))),
            'industry': i.get('industry'), 'mcap': num('marketCap'), 'assets': num('totalAssets'),
            'pe': num('trailingPE'), 'beta': num('beta'), 'div': num('dividendYield')}


def leer_anterior():
    try:
        txt = open(SALIDA, encoding='utf-8').read()
        return json.loads(re.search(r'window\.DATA\s*=\s*(\{.*\});?\s*$', txt, re.S).group(1))
    except Exception:
        return None


def velas(t):
    h = yf.Ticker(t).history(period='5y', auto_adjust=True).dropna()
    ny = pd.Timestamp.now(tz='America/New_York')
    if len(h) and h.index[-1].date() == ny.date() and (ny.hour, ny.minute) < (16, 15):
        h = h.iloc[:-1]  # con el mercado abierto la vela de hoy no está completa
    rows = [[i.strftime('%Y-%m-%d'), round(r.Open, 3), round(r.High, 3), round(r.Low, 3), round(r.Close, 3), int(r.Volume)]
            for i, r in h.iterrows()]
    if len(rows) < 300:
        raise ValueError(f'{t}: muy pocas velas ({len(rows)})')
    return rows


def lado(df, S):
    """Strikes con cotización real entre 70% y 130% del precio; máximo 17, repartidos parejo."""
    out = []
    for _, c in df.iterrows():
        K, bid, ask, iv = float(c.strike), float(c.bid or 0), float(c.ask or 0), float(c.impliedVolatility or 0)
        if not (0.7 * S <= K <= 1.3 * S) or ask <= 0 or not (0.01 < iv < 3):
            continue
        last = float(c.lastPrice or 0)
        oi = 0 if c.openInterest != c.openInterest or c.openInterest is None else int(c.openInterest)
        out.append({'K': K, 'bid': round(bid, 2), 'ask': round(ask, 2), 'last': round(last, 2), 'iv': round(iv, 4), 'oi': oi})
    out.sort(key=lambda c: c['K'])
    if len(out) > MAX_STRIKES:
        lo, hi = out[0]['K'], out[-1]['K']
        metas = [lo + i * (hi - lo) / (MAX_STRIKES - 1) for i in range(MAX_STRIKES)] + [S]  # parejo en precio y el del dinero
        idx = sorted({min(range(len(out)), key=lambda i: abs(out[i]['K'] - m)) for m in metas})
        out = [out[i] for i in idx]
    return out


def opciones(t, S, hoy):
    tk = yf.Ticker(t)
    fechas = [(f, (dt.date.fromisoformat(f) - hoy).days) for f in tk.options]
    fechas = [(f, d) for f, d in fechas if d >= 7]
    mercado, usadas = {}, set()
    for plazo, objetivo in PLAZOS.items():
        cand = [(f, d) for f, d in fechas if f not in usadas and abs(d - objetivo) <= objetivo * 0.5]
        # se prefieren los vencimientos mensuales (tercer viernes), que son los que más se operan
        mensual = lambda f: dt.date.fromisoformat(f).weekday() == 4 and 15 <= dt.date.fromisoformat(f).day <= 21
        cand.sort(key=lambda x: (not mensual(x[0]), abs(x[1] - objetivo)))
        for f, d in cand[:3]:
            ch = tk.option_chain(f)
            call, put = lado(ch.calls, S), lado(ch.puts, S)
            if len(call) >= 3 and len(put) >= 3:
                mercado[plazo] = {'expiry': f, 'days': d, 'call': call, 'put': put}
                usadas.add(f)
                break
    if not mercado:
        raise ValueError(f'{t}: sin cadenas de opciones útiles')
    return mercado


def escribir_resumen(data):
    """resumen.js: lo poquito que usa la landing (carsama197-cloud.github.io), para que no cargue todo datos.js."""
    res = {'updated': data['updated'], 'rf': data['rf']['value'], 'q': {}}
    for t, a in data['assets'].items():
        o, m = data['ohlc'][t], data['market'][t]
        S = o[-1][4]
        ch = m.get('1M') or next(iter(m.values()))
        puts = {p['K']: p for p in ch['put']}
        c = min((c for c in ch['call'] if c['K'] in puts and c['bid'] > 0), key=lambda c: abs(c['K'] - S), default=None)
        q = {'name': a['name'], 'S': S, 'prev': o[-2][4], 'expiry': ch['expiry'], 'days': ch['days']}
        if c:
            p = puts[c['K']]
            q.update({'K': c['K'], 'c': [c['bid'], c['ask']], 'p': [p['bid'], p['ask']]})
        res['q'][t] = q
    with open(os.path.join(AQUI, 'resumen.js'), 'w', encoding='utf-8') as f:
        f.write('// Generado por actualizar_datos.py; lo usa la landing.\nwindow.RESUMEN=')
        json.dump(res, f, separators=(',', ':'), ensure_ascii=False)
        f.write(';\n')


def main():
    ant = leer_anterior() or {}
    hoy = dt.date.today()
    data = {'assets': {}, 'ohlc': {}, 'market': {}}
    fallas = []
    for t, (nombre, desc) in EMPRESAS.items():
        try:
            o = velas(t)
            S = o[-1][4]
            m = opciones(t, S, dt.date.fromisoformat(o[-1][0]))
            data['ohlc'][t], data['market'][t] = o, m
            data['assets'][t] = {'name': nombre, 'desc': desc, 'date': o[-1][0], **ficha(t)}
            print(f'{t}: {len(o)} velas, cierre {S}, plazos {list(m)}')
        except Exception as e:
            fallas.append(t)
            if t in ant.get('ohlc', {}):  # si Yahoo falla, se queda la foto anterior de esa empresa
                for k in ('ohlc', 'market', 'assets'):
                    data[k][t] = ant[k][t]
                print(f'{t}: FALLÓ ({e}); se conserva la foto del {ant["assets"][t]["date"]}')
            else:
                print(f'{t}: FALLÓ ({e}); se omite')
    data['updated_tmp'] = max(a['date'] for a in data['assets'].values()) if data['assets'] else '9999'
    try:
        irx = yf.Ticker('^IRX').history(period='10d').dropna()
        if irx.index[-1].strftime('%Y-%m-%d') > data['updated_tmp']:
            irx = irx.iloc[:-1]  # misma fecha que los cierres
        data['rf'] = {'date': irx.index[-1].strftime('%Y-%m-%d'), 'value': round(float(irx.Close.iloc[-1]) / 100, 5),
                      'source': '^IRX (T-bill 13 semanas)'}
    except Exception as e:
        data['rf'] = ant['rf']; fallas.append('^IRX'); print('^IRX FALLÓ', e)
    try:
        v = yf.Ticker('^VIX').history(period='5y').dropna()
        data['vix'] = [[i.strftime('%Y-%m-%d'), round(float(r.Close), 2)] for i, r in v.iterrows()]
    except Exception as e:
        data['vix'] = ant['vix']; fallas.append('^VIX'); print('^VIX FALLÓ', e)

    if 'SPY' not in data['ohlc'] or len(data['ohlc']) < 4:
        sys.exit('Muy pocas empresas con datos; no se escribe nada para no romper la página.')
    data['updated'] = data.pop('updated_tmp')
    with open(SALIDA, 'w', encoding='utf-8') as f:
        f.write('// Generado por actualizar_datos.py; no editar a mano.\nwindow.DATA=')
        json.dump(data, f, separators=(',', ':'), ensure_ascii=False)
        f.write(';\n')
    escribir_resumen(data)
    print(f'datos.js: {os.path.getsize(SALIDA) // 1024} KB, {len(data["ohlc"])} empresas, al {data["updated"]}'
          + (f'; fallaron: {fallas}' if fallas else ''))


if __name__ == '__main__':
    main()
