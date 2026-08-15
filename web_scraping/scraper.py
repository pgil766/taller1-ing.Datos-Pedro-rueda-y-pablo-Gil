# ============================================================================
# WEB SCRAPING BOOKS TO SCRAPE
# ============================================================================
# Taller 1 
# ============================================================================

import os
import re
from datetime import datetime
from time import sleep
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ============================================================================
# CONFIGURACIÓN GENERAL
# ============================================================================

# sudo apt install chromium-chromedriver

BASE_URL = "https://books.toscrape.com/"


EXTRAIDO_POR = "Pablo y Pedro"


OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


MONEDA_MAP = {"£": "GBP", "$": "USD", "€": "EUR"}


def crear_driver():
    """Crea y configura el navegador Chrome controlado por Selenium."""
    service = Service('/usr/bin/chromedriver')

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized") 

    driver = webdriver.Chrome(service=service, options=options)
    return driver


# ============================================================================
# FUNCIONES DE APOYO PARA EXTRAER INFORMACIÓN DE UN LIBRO
# ============================================================================

def extraer_tabla_producto(soup):
    """
    Recorre la tabla 'table table-striped' de la página de detalle
    (sección Product Information) y la convierte en un diccionario
    {nombre_del_campo: valor}.
    """
    tabla = soup.find('table', class_='table-striped')
    datos = {}
    if tabla:
        for fila in tabla.find_all('tr'):
            th = fila.find('th')
            td = fila.find('td')
            if th and td:
                datos[th.get_text(strip=True)] = td.get_text(strip=True)
    return datos


def extraer_precio_y_moneda(texto_precio):
    """
    Recibe un texto como '£51.77' y devuelve (51.77, 'GBP').
    """
    if not texto_precio:
        return None, None
    match = re.search(r'([^\d.,]+)?([\d.,]+)', texto_precio)
    if not match:
        return None, None
    simbolo = (match.group(1) or "").strip()
    valor = float(match.group(2).replace(',', ''))
    moneda = MONEDA_MAP.get(simbolo, simbolo if simbolo else None)
    return valor, moneda


def extraer_cantidad_stock(texto_disponibilidad):
    """
    Recibe un texto como 'In stock (22 available)' y devuelve 22.
    Si no encuentra un número, devuelve 0.
    """
    if not texto_disponibilidad:
        return 0
    match = re.search(r'(\d+)', texto_disponibilidad)
    return int(match.group(1)) if match else 0


def extraer_calificacion(soup):
    """Busca la etiqueta <p class="star-rating X"> y devuelve el número (1-5)."""
    tag = soup.find('p', class_='star-rating')
    if not tag:
        return None
    clases = tag.get('class', [])
    for clase in clases:
        if clase in RATING_MAP:
            return RATING_MAP[clase]
    return None


def extraer_descripcion(soup):
    """
    La descripción está en un <p> justo después del div#product_description.
    Si el libro no tiene descripción, devuelve cadena vacía.
    """
    ancla = soup.find(id='product_description')
    if not ancla:
        return ""
    parrafo = ancla.find_next_sibling('p')
    return parrafo.get_text(strip=True) if parrafo else ""


def extraer_categoria_breadcrumb(soup, categoria_actual):
    """
    La categoría real del libro se lee del breadcrumb
    (Home > Books > Categoría > Título). Si por algún motivo no se
    encuentra, se usa la categoría desde la que se llegó al libro.
    """
    breadcrumb = soup.find('ul', class_='breadcrumb')
    if breadcrumb:
        enlaces = breadcrumb.find_all('a')
        if len(enlaces) >= 3:
            return enlaces[2].get_text(strip=True)
    return categoria_actual


def scrapear_libro(driver, wait, url_libro, categoria_actual):
    """Entra a la página de detalle de un libro y extrae toda su información."""
    driver.get(url_libro)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product_main")))

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    tabla = extraer_tabla_producto(soup)

    titulo = soup.find('div', class_='product_main').find('h1').get_text(strip=True)
    categoria = extraer_categoria_breadcrumb(soup, categoria_actual)
    descripcion = extraer_descripcion(soup)

    precio_sin_impuesto, moneda = extraer_precio_y_moneda(tabla.get('Price (excl. tax)'))
    precio_con_impuesto, _ = extraer_precio_y_moneda(tabla.get('Price (incl. tax)'))
    impuesto, _ = extraer_precio_y_moneda(tabla.get('Tax'))

    disponibilidad = tabla.get('Availability', '')
    cantidad_stock = extraer_cantidad_stock(disponibilidad)

    imagen_tag = soup.find('div', class_='item active')
    imagen_src = imagen_tag.find('img')['src'] if imagen_tag and imagen_tag.find('img') else None
    url_imagen = urljoin(driver.current_url, imagen_src) if imagen_src else None

    libro = {
        "upc": tabla.get('UPC'),
        "titulo": titulo,
        "categoria": categoria,
        "descripcion": descripcion,
        "tipo_producto": tabla.get('Product Type'),
        "precio_sin_impuesto": precio_sin_impuesto,
        "precio_con_impuesto": precio_con_impuesto,
        "impuesto": impuesto,
        "moneda": moneda,
        "disponibilidad": disponibilidad,
        "cantidad_stock": cantidad_stock,
        "calificacion": extraer_calificacion(soup),
        "cantidad_resenas": int(tabla.get('Number of reviews', 0) or 0),
        "url_libro": driver.current_url,
        "url_imagen": url_imagen,
        "fecha_extraccion": datetime.now().isoformat(timespec='seconds'),
        "extraido_por": EXTRAIDO_POR,
    }
    return libro


# ============================================================================
# FUNCIONES PARA RECORRER CATEGORÍAS Y PÁGINAS DEL CATÁLOGO
# ============================================================================

def obtener_categorias(driver, wait):
    """
    Entra a la página principal y lee del menú lateral todas las
    categorías disponibles junto con su URL. No se escriben nombres
    de categorías manualmente: se extraen del HTML.
    """
    driver.get(BASE_URL)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "side_categories")))

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    contenedor = soup.find('div', class_='side_categories')

    categorias = []
   
    enlaces = contenedor.find('ul').find('li').find('ul').find_all('a')
    for enlace in enlaces:
        nombre = enlace.get_text(strip=True)
        url_categoria = urljoin(BASE_URL, enlace['href'])
        categorias.append({"categoria": nombre, "url_categoria": url_categoria})

    return categorias


def obtener_cantidad_resultados(soup):
    """
    Busca en el texto de la página el patrón 'N results', que indica
    cuántos libros pertenecen a la categoría según el propio sitio.
    """
    texto = soup.get_text(" ", strip=True)
    match = re.search(r'(\d+)\s+results?', texto, re.IGNORECASE)
    return int(match.group(1)) if match else None


def obtener_urls_libros_de_pagina(soup, url_actual):
    """Extrae las URLs de detalle de todos los libros listados en una página."""
    urls = []
    for articulo in soup.find_all('article', class_='product_pod'):
        enlace = articulo.find('h3').find('a')
        urls.append(urljoin(url_actual, enlace['href']))
    return urls


def obtener_url_pagina_siguiente(soup, url_actual):
    """Devuelve la URL de la siguiente página del catálogo, o None si no hay más."""
    siguiente = soup.find('li', class_='next')
    if siguiente and siguiente.find('a'):
        return urljoin(url_actual, siguiente.find('a')['href'])
    return None


def recorrer_categoria(driver, wait, categoria):
    """
    Recorre TODAS las páginas de una categoría (sin asumir cuántas hay:
    se sigue el enlace 'next' hasta que ya no exista) y devuelve la
    lista de libros extraídos junto con la cantidad de libros reportada
    por el sitio para esa categoría.
    """
    libros = []
    cantidad_libros_reportada = None

    url_pagina = categoria["url_categoria"]
    numero_pagina = 1

    while url_pagina:
        print(f"  Página {numero_pagina} -> {url_pagina}")
        driver.get(url_pagina)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product_pod")))
        sleep(0.5)  

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        if cantidad_libros_reportada is None:
            cantidad_libros_reportada = obtener_cantidad_resultados(soup)

        urls_libros = obtener_urls_libros_de_pagina(soup, url_pagina)
        for url_libro in urls_libros:
            try:
                libro = scrapear_libro(driver, wait, url_libro, categoria["categoria"])
                libros.append(libro)
            except Exception as error:
                print(f"    [!] Error extrayendo {url_libro}: {error}")

       
        driver.get(url_pagina)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product_pod")))
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        url_pagina = obtener_url_pagina_siguiente(soup, url_pagina)
        numero_pagina += 1

    return libros, cantidad_libros_reportada


# ============================================================================
# PROGRAMA PRINCIPAL
# ============================================================================

def main():
    driver = crear_driver()
    wait = WebDriverWait(driver, 15)

    categorias_data = []
    libros_data = []

    try:
        categorias = obtener_categorias(driver, wait)
        print(f"Se encontraron {len(categorias)} categorías.\n")

        for categoria in categorias:
            print(f"Procesando categoría: {categoria['categoria']}")
            libros, cantidad_reportada = recorrer_categoria(driver, wait, categoria)
            libros_data.extend(libros)

            categorias_data.append({
                "categoria": categoria["categoria"],
                "url_categoria": categoria["url_categoria"],
                "cantidad_libros": cantidad_reportada,
                "fecha_extraccion": datetime.now().isoformat(timespec='seconds'),
                "extraido_por": EXTRAIDO_POR,
            })
            print(f"  -> {len(libros)} libros extraídos.\n")

    finally:
        driver.quit()
        print("Navegador cerrado correctamente.")

    # ------------------------------------------------------------------
    # Guardar resultados en archivos Parquet
    # ------------------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df_categorias = pd.DataFrame(categorias_data)
    df_libros = pd.DataFrame(libros_data)

    ruta_categorias = os.path.join(OUTPUT_DIR, "categorias.parquet")
    ruta_libros = os.path.join(OUTPUT_DIR, "libros.parquet")

    df_categorias.to_parquet(ruta_categorias, index=False)
    df_libros.to_parquet(ruta_libros, index=False)

    print("\nExtracción completada.")
    print(f"Categorías guardadas en: {ruta_categorias} ({len(df_categorias)} filas)")
    print(f"Libros guardados en: {ruta_libros} ({len(df_libros)} filas)")


if __name__ == "__main__":
    main()