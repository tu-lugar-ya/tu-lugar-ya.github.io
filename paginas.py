"""Páginas por inmueble para Tu Lugar Ya (las genera GitHub Actions en cada publicación).

Crea sitio/i/<CÓDIGO>/index.html: la misma página del catálogo, pero con título, descripción
y foto del inmueble en las etiquetas que leen WhatsApp, Facebook y Google; al abrirla muestra
la ficha de ese inmueble. También crea sitemap.xml, robots.txt y 404.html (los links de un
inmueble recién publicado abren su ficha aunque la página todavía no exista).
Uso: python3 paginas.py [carpeta_del_sitio]
"""
import html, json, os, re, sys

SITIO = sys.argv[1] if len(sys.argv) > 1 else 'sitio'
URL = 'https://tu-lugar-ya.github.io/'
COD = re.compile(r'^[A-Z]+-\d+$')


def cop(n):
    return '$' + f'{int(round(n)):,}'.replace(',', '.')


def num(n):
    n = float(n)
    return str(int(n)) if n == int(n) else str(round(n, 1)).replace('.', ',')


def esV(i):
    return 'Venta' in (i.get('n') or '')


def esA(i):
    return 'rriendo' in (i.get('n') or '')


def precio(i):
    if esV(i) and i.get('pv') and esA(i) and i.get('pc'):
        return cop(i['pv']) + ' o ' + cop(i['pc']) + ' al mes'
    if esV(i) and i.get('pv'):
        return cop(i['pv'])
    if esA(i) and i.get('pc'):
        return cop(i['pc']) + ' al mes'
    return ''


def titulo(i):
    lugar = ', '.join(x for x in [i.get('b'), i.get('ci')] if x)
    tipo = i.get('t') or 'Inmueble'
    if i.get('e') in ('Vendido', 'Arrendado'):
        return tipo + (f' en {lugar}' if lugar else '') + (' · Ya se vendió' if i['e'] == 'Vendido' else ' · Ya se arrendó')
    neg = 'en venta o arriendo' if esV(i) and esA(i) else 'en venta' if esV(i) else 'en arriendo'
    return f'{tipo} {neg}' + (f' en {lugar}' if lugar else '')


def datos(i):
    l = []
    if i.get('a'): l.append(num(i['a']) + ' m²')
    if i.get('h'): l.append(f"{i['h']} hab.")
    if i.get('ba'): l.append(f"{i['ba']} baños")
    if i.get('pq'): l.append(f"{i['pq']} parq.")
    if i.get('es'): l.append(f"estrato {i['es']}")
    return ' · '.join(l)


def limpiar(d):
    """Igual que en la página: quita el renglón de título y los renglones de precio."""
    l = [x.strip() for x in str(d or '').split('\n')]
    while l and not l[0]:
        l.pop(0)
    if len(l) > 1 and ' | ' in l[0]:
        l.pop(0)
    l = [x for x in l if not re.match(r'^(💰|🏷|🛋|🏠|📩|💵|🏢)', x) and not re.match(r'^Tu Lugar Ya\s*\|', x, re.I)
         and not re.match(r'^(Canon( de arrendamiento)?|Precio( de venta)?|Administración)\s*:', x, re.I)]
    return '\n'.join(l).strip()


def resumen(i, n=170):
    d = re.sub(r'\s+', ' ', limpiar(i.get('d'))).strip()
    if len(d) > n:
        d = d[:n].rsplit(' ', 1)[0].rstrip(',.;:') + '…'
    return d


def foto(i, w=1200, h=630):
    f = i.get('f') or []
    # -rj: siempre JPEG (las fotos PNG pesan más de 1 MB y WhatsApp no muestra la vista previa)
    return f'https://lh3.googleusercontent.com/d/{f[0]}=w{w}-h{h}-c-rj' if f else URL + 'og.jpg'


def meta(s, prop, valor, attr='property'):
    """Reemplaza el content de una etiqueta <meta> existente."""
    pat = re.compile(r'(<meta\s+' + attr + r'="' + re.escape(prop) + r'"\s+content=")[^"]*(")')
    return pat.sub(lambda m: m.group(1) + valor + m.group(2), s, count=1)


def pagina(plantilla, i):
    c = i['c']
    url = f'{URL}i/{c}/'
    p = precio(i)
    t = titulo(i) + (f' · {p}' if p and i.get('e') not in ('Vendido', 'Arrendado') else '')
    desc = ' · '.join(x for x in [datos(i), resumen(i)] if x) or 'Fotos, ficha completa y precio. Solicita tu visita por WhatsApp.'
    T, D = html.escape(t + ' | Tu Lugar Ya'), html.escape(desc)
    s = plantilla
    # Primero en <head>: rutas relativas desde la raíz y abrir la ficha de este inmueble
    s = s.replace('<head>', '<head>\n<base href="/">\n<script>if(!location.hash)history.replaceState(null,"","/#' + c + '")</script>', 1)
    s = re.sub(r'<title>[^<]*</title>', '<title>' + T + '</title>', s, count=1)
    s = meta(s, 'description', D, 'name')
    s = meta(s, 'og:title', html.escape(t))
    s = meta(s, 'og:description', D)
    s = meta(s, 'og:url', url)
    s = meta(s, 'og:image', html.escape(foto(i)))
    s = re.sub(r'<link rel="canonical" href="[^"]*">', '<link rel="canonical" href="' + url + '">', s, count=1)
    ld = {'@context': 'https://schema.org', '@type': 'Offer', 'name': t, 'url': url, 'image': foto(i, 1600, 1200),
          'description': resumen(i, 400), 'priceCurrency': 'COP',
          'availability': 'https://schema.org/SoldOut' if i.get('e') in ('Vendido', 'Arrendado') else 'https://schema.org/InStock',
          'seller': {'@type': 'RealEstateAgent', 'name': 'Tu Lugar Ya', 'url': URL}}
    pr = i.get('pv') if esV(i) and i.get('pv') else i.get('pc')
    if pr: ld['price'] = pr
    s = s.replace('</head>', '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace('</', '<\\/') + '</script>\n</head>', 1)
    # Texto para quien no ejecuta JavaScript
    s = s.replace('<body>', '<body>\n<noscript><h1>' + html.escape(t) + '</h1><p>' + D + '</p><p><a href="/#' + c + '">Ver la ficha completa</a></p></noscript>', 1)
    return s


def main():
    plantilla = open(os.path.join(SITIO, 'index.html'), encoding='utf8').read()
    d = json.load(open(os.path.join(SITIO, 'catalogo.json'), encoding='utf8'))
    lista = [i for i in d.get('inmuebles') or [] if COD.match(str(i.get('c') or ''))]
    urls = [URL]
    for i in lista:
        carpeta = os.path.join(SITIO, 'i', i['c'])
        os.makedirs(carpeta, exist_ok=True)
        open(os.path.join(carpeta, 'index.html'), 'w', encoding='utf8').write(pagina(plantilla, i))
        urls.append(f"{URL}i/{i['c']}/")
    hoy = (d.get('_t') or d.get('actualizado') or '')[:10]
    open(os.path.join(SITIO, 'sitemap.xml'), 'w', encoding='utf8').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        ''.join(f'  <url><loc>{u}</loc>' + (f'<lastmod>{hoy}</lastmod>' if hoy else '') + '</url>\n' for u in urls) + '</urlset>\n')
    open(os.path.join(SITIO, 'robots.txt'), 'w', encoding='utf8').write('User-agent: *\nAllow: /\nSitemap: ' + URL + 'sitemap.xml\n')
    open(os.path.join(SITIO, '404.html'), 'w', encoding='utf8').write(
        '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="robots" content="noindex">'
        '<title>Tu Lugar Ya</title><script>var m=location.pathname.match(/\\/i\\/([A-Za-z]+-\\d+)/);'
        'location.replace("/"+(m?"#"+m[1].toUpperCase():""));</script></head>'
        '<body style="font-family:sans-serif;background:#01352E;color:#fff;padding:40px">'
        '<a href="/" style="color:#06F2D4">Ir al catálogo de Tu Lugar Ya</a></body></html>\n')
    print(len(lista), 'páginas de inmueble')


if __name__ == '__main__':
    main()
