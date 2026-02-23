import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from urllib.parse import urljoin

st.set_page_config(
    page_title="Scraping de Alojamientos",
    page_icon="🏨",
    layout="centered"
)

# Inicializacion de estado
if 'urls_encontradas' not in st.session_state:
    st.session_state.urls_encontradas = []
if 'ciudad_actual' not in st.session_state:
    st.session_state.ciudad_actual = ""
if 'sitio_actual' not in st.session_state:
    st.session_state.sitio_actual = ""
    
def limpiar_y_extraer(texto_completo, soup_objeto):
    # Limpieza basica
    texto_limpio = re.sub(r'200\d\s?[-—]\s?202\d', '', texto_completo) 
    texto_limpio = re.sub(r'©', '', texto_limpio)
    
    # TODO: Mejorar esta regex en el futuro, a veces agarra numeros de CUIT
    patron = r'(?:\+?54|0)?\s?(?:\d{2,4})?[\s.-]?\d{3,4}[\s.-]?\d{3,4}'
    matches = re.findall(patron, texto_limpio)
    
    numeros = set()
    for m in matches:
        solo_digitos = re.sub(r'\D', '', m)
        if len(solo_digitos) >= 9:
            numeros.add(m.strip())

    has_wsp = "No"
    for link in soup_objeto.find_all('a', href=True):
        href = link['href']
        
        if href.startswith('tel:'):
            numeros.add(href.replace('tel:', '').strip())
            
        if 'wa.me' in href or 'api.whatsapp' in href:
            has_wsp = "Sí"

    phones_str = " / ".join(list(numeros)) if numeros else "No encontrado"
    return phones_str, has_wsp

def buscar_enlaces(sitio, ciudad):
    base_url = "https://www.interpatagonia.com" if sitio == "InterPatagonia" else "https://www.welcomeargentina.com"
    url_listado = f"{base_url}/{ciudad}/alojamientos.html"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        resp = requests.get(url_listado, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url_listado}: {e}")
        return []

    links_fichas = set()
    mis_links = soup.find_all('a', href=True)
    
    for link in mis_links:
        href = link['href']
        if (f"/{ciudad}/" in href or href.startswith(f"{ciudad}/")) \
           and href.endswith(".html") \
           and "alojamientos" not in href \
           and "paseos" not in href \
           and "index" not in href:
            
            url_completa = urljoin(url_listado, href)
            links_fichas.add(url_completa)
            
    return list(links_fichas)

def procesar_fichas(lista_urls, sitio, ciudad, barra, estado):
    datos_finales = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    total = len(lista_urls)
    
    for i, url_hotel in enumerate(lista_urls):
        barra.progress((i + 1) / total)
        estado.text(f"Procesando {i+1}/{total}...")
        
        try:
            # Sleep random para no saturar el server y evitar baneos
            time.sleep(random.uniform(0.1, 0.5))
            r_hotel = requests.get(url_hotel, headers=headers, timeout=8)
            s_hotel = BeautifulSoup(r_hotel.text, 'html.parser')
            
            h1 = s_hotel.find('h1')
            nombre = h1.get_text(strip=True) if h1 else "Desconocido"
            
            tels, wsp = limpiar_y_extraer(s_hotel.get_text(), s_hotel)
            
            datos_finales.append({
                'Nombre': nombre,
                'Telefonos': tels,
                'WhatsApp': wsp,
                'Ciudad': ciudad,
                'Web': sitio,
                'Link': url_hotel
            })
        except requests.RequestException as e:
            print(f"Timeout o error de conexion en {url_hotel}")
            continue
        except Exception as e:
            print(f"Error procesando ficha {url_hotel}: {e}")
            continue
            
    return datos_finales

def buscar_enlaces_turismocordoba(ciudad):
    base_url = "https://www.turismocordoba.com.ar"
    ciudad_url = ciudad.replace(' ', '+').title()
    url_buscador = f"{base_url}/buscador/?localidad={ciudad_url}"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        resp = requests.get(url_buscador, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"Error en buscador TurismoCordoba: {e}")
        return []
    
    links_fichas = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        texto_link = link.get_text(strip=True).lower()
        
        if 'más info' in texto_link or 'ms info' in texto_link:
            if href.startswith('http://') or href.startswith('https://'):
                url_limpia = href.split('?')[0]
            elif href.startswith('/'):
                url_limpia = base_url + href.split('?')[0]
            else:
                url_limpia = f"{base_url}/{href}".split('?')[0]
            
            if 'turismocordoba.com.ar' in url_limpia and 'booking.com' not in url_limpia:
                if url_limpia not in links_fichas:
                    links_fichas.append(url_limpia)
    
    return links_fichas

def procesar_fichas_turismocordoba(lista_urls, ciudad, barra, estado):
    datos_finales = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    total = len(lista_urls)
    descartados = 0
    
    # Movemos el diccionario de variaciones afuera del loop para optimizar memoria
    variaciones = {
        'villa carlos paz': ['carlos paz', 'vcp', 'villa carlos'],
        'cordoba': ['córdoba', 'cba', 'cordoba capital'],
        'villa general belgrano': ['v.g.belgrano', 'belgrano', 'vgb'],
        'la cumbre': ['lacumbre'],
        'la cumbrecita': ['lacumbrecita']
    }
    
    for i, url in enumerate(lista_urls):
        barra.progress((i + 1) / total)
        estado.text(f"Procesando {i+1}/{total} (Descartados: {descartados})...")
        
        try:
            time.sleep(random.uniform(0.3, 0.8))
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            texto_completo = soup.get_text()
            
            ciudad_normalizada = ciudad.lower()
            is_valid_city = False
            
            if ciudad_normalizada in texto_completo.lower():
                is_valid_city = True
            elif ciudad_normalizada in variaciones:
                for var in variaciones[ciudad_normalizada]:
                    if var in texto_completo.lower():
                        is_valid_city = True
                        break
            
            if not is_valid_city:
                descartados += 1
                continue
            
            nombre = "Desconocido"
            for tag in ['h1', 'h2', 'h5', 'h3']:
                elemento = soup.find(tag)
                if elemento:
                    nombre = elemento.get_text(strip=True)
                    break
            
            telefonos_encontrados = set()
            for tel_link in soup.find_all('a', href=re.compile(r'^tel:', re.I)):
                tel = tel_link['href'].replace('tel:', '').strip()
                tel = tel.replace(' ', '').replace('-', '')
                if len(tel) >= 7:
                    telefonos_encontrados.add(tel)
            
            tel_matches = re.findall(r'Tel[eé]fono:\s*([0-9\s\-()]+)', texto_completo, re.I)
            for tel in tel_matches:
                tel_limpio = re.sub(r'[^\d]', '', tel)
                if 7 <= len(tel_limpio) <= 15:
                    telefonos_encontrados.add(tel_limpio)
            
            movil_matches = re.findall(r'M[oó]vil:\s*([0-9\s\-()]+)', texto_completo, re.I)
            for mov in movil_matches:
                mov_limpio = re.sub(r'[^\d]', '', mov)
                if 7 <= len(mov_limpio) <= 15:
                    telefonos_encontrados.add(mov_limpio)
            
            has_wsp = "No"
            wsp_number = ""
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                texto = link.get_text(strip=True).lower()
                
                if 'whatsapp' in href or 'whatsapp' in texto:
                    has_wsp = "Sí"
                    num_match = re.search(r'(\d{10,15})', href)
                    if num_match:
                        wsp_number = num_match.group(1)
                    break
            
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', texto_completo)
            email_encontrado = ", ".join(set(emails[:2])) if emails else "No encontrado"
            
            phones_str = " / ".join(sorted(list(telefonos_encontrados))) if telefonos_encontrados else "No encontrado"
            
            if wsp_number and wsp_number not in phones_str:
                if phones_str == "No encontrado":
                    phones_str = f"WhatsApp: {wsp_number}"
                else:
                    phones_str += f" / WhatsApp: {wsp_number}"
            
            datos_finales.append({
                'Nombre': nombre,
                'Telefonos': phones_str,
                'Email': email_encontrado,
                'WhatsApp': has_wsp,
                'Ciudad': ciudad,
                'Web': 'TurismoCordoba',
                'Link': url
            })
            
        except Exception as e:
            print(f"Error procesando {url}: {e}")
            continue
    
    return datos_finales

# --- UI de Streamlit ---

st.title("Buscador de Alojamientos")
st.markdown("Herramienta interna para scraping de directorios turísticos.")
st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    sitio_elegido = st.radio(
        "1. Seleccionar directorio:", 
        ["InterPatagonia", "WelcomeArgentina", "TurismoCordoba"]
    )
    ciudad_input = st.text_input("2. Ciudad (formato URL o texto):", placeholder="Ej: villa carlos paz")

with col2:
    if sitio_elegido == "TurismoCordoba":
        st.info("**TurismoCordoba:** Acepta formato normal con espacios (Ej: Villa Carlos Paz).")
    else:
        st.info("**Inter/Welcome:** Se normalizará sin espacios ni tildes automáticamente.")

if st.button("ANALIZAR CIUDAD", type="secondary", use_container_width=True):
    if not ciudad_input:
        st.warning("Falta ingresar la ciudad.")
    else:
        if sitio_elegido == "TurismoCordoba":
            ciudad_clean = ciudad_input.strip()
        else:
            ciudad_clean = ciudad_input.strip().lower()
            ciudad_clean = ciudad_clean.replace(" ", "").replace("-", "").replace("_", "") 
            reemplazos = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n', 'ü': 'u'}
            for acento, sin_acento in reemplazos.items():
                ciudad_clean = ciudad_clean.replace(acento, sin_acento)
        
        with st.spinner(f"Escaneando {sitio_elegido}..."):
            if sitio_elegido == "TurismoCordoba":
                enlaces = buscar_enlaces_turismocordoba(ciudad_clean)
            else:
                enlaces = buscar_enlaces(sitio_elegido, ciudad_clean)
            
            if enlaces is None:
                st.error("Error de conexión con la página web.")
                st.session_state.urls_encontradas = []
            elif not enlaces:
                st.warning("No se encontraron alojamientos.")
                st.session_state.urls_encontradas = []
            else:
                st.session_state.urls_encontradas = enlaces
                st.session_state.ciudad_actual = ciudad_clean
                st.session_state.sitio_actual = sitio_elegido
                st.success(f"Se encontraron {len(enlaces)} alojamientos.")

if len(st.session_state.urls_encontradas) > 0:
    st.divider()
    st.subheader(f"Resultados para: {st.session_state.ciudad_actual.title()}")
    
    total_disponible = len(st.session_state.urls_encontradas)
    limite = st.slider("Cantidad a extraer:", 1, total_disponible, min(10, total_disponible))
    
    if st.button(f"EXTRAER DATOS ({limite})", type="primary", use_container_width=True):
        
        lista_a_procesar = st.session_state.urls_encontradas[:limite]
        barra_carga = st.progress(0)
        mensaje_estado = st.empty()
        
        if st.session_state.sitio_actual == "TurismoCordoba":
            datos = procesar_fichas_turismocordoba(
                lista_a_procesar, 
                st.session_state.ciudad_actual, 
                barra_carga, 
                mensaje_estado
            )
        else:
            datos = procesar_fichas(
                lista_a_procesar, 
                st.session_state.sitio_actual, 
                st.session_state.ciudad_actual, 
                barra_carga, 
                mensaje_estado
            )
        
        if datos:
            df = pd.DataFrame(datos)
            
            if st.session_state.sitio_actual == "TurismoCordoba":
                descartados = limite - len(datos)
                if descartados > 0:
                    st.warning(f"Se descartaron {descartados} registros fuera de zona.")
            
            mensaje_estado.success(f"Proceso Terminado. {len(datos)} registros extraídos.")
            
            con_telefono = df[df['Telefonos'] != 'No encontrado'].shape[0]
            st.metric("Con Teléfono", f"{con_telefono}/{len(df)}", f"{(con_telefono/len(df)*100) if len(df)>0 else 0:.1f}%")
            
            st.dataframe(df.head(10))
            
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            file_name = f"Datos_{st.session_state.sitio_actual}_{st.session_state.ciudad_actual}.csv"
            
            st.download_button(
                label="DESCARGAR CSV",
                data=csv,
                file_name=file_name,
                mime="text/csv",
                type="primary"
            )
        else:
            st.error("Fallo la extracción de datos.")
