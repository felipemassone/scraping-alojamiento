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

if 'urls_encontradas' not in st.session_state:
    st.session_state.urls_encontradas = []
if 'ciudad_actual' not in st.session_state:
    st.session_state.ciudad_actual = ""
if 'sitio_actual' not in st.session_state:
    st.session_state.sitio_actual = ""

def limpiar_y_extraer(texto_completo, soup_objeto):
    texto_limpio = re.sub(r'200\d\s?[-–]\s?202\d', '', texto_completo) 
    texto_limpio = re.sub(r'©', '', texto_limpio)
    
    patron = r'(?:\+?54|0)?\s?(?:\d{2,4})?[\s.-]?\d{3,4}[\s.-]?\d{3,4}'
    matches = re.findall(patron, texto_limpio)
    
    numeros = set()
    for m in matches:
        solo_digitos = re.sub(r'\D', '', m)
        if len(solo_digitos) >= 9:
            numeros.add(m.strip())

    whatsapp_detectado = "No"
    for link in soup_objeto.find_all('a', href=True):
        href = link['href']
        
        if href.startswith('tel:'):
            numeros.add(href.replace('tel:', '').strip())
            
        if 'wa.me' in href or 'api.whatsapp' in href:
            whatsapp_detectado = "Sí"

    resultado_telefonos = " / ".join(list(numeros)) if numeros else "No encontrado"
    return resultado_telefonos, whatsapp_detectado

def buscar_enlaces(sitio, ciudad):
    if sitio == "InterPatagonia":
        base_url = "https://www.interpatagonia.com"
    else:
        base_url = "https://www.welcomeargentina.com"
        
    url_listado = f"{base_url}/{ciudad}/alojamientos.html"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        resp = requests.get(url_listado, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
    except:
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    total = len(lista_urls)
    
    for i, url_hotel in enumerate(lista_urls):
        progreso = (i + 1) / total
        barra.progress(progreso)
        
        try:
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
        except:
            continue
            
    return datos_finales

st.title("🔎 Buscador de Alojamientos")
st.markdown("Herramienta interna para Scraping de alojamientos.")
st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    sitio_elegido = st.radio("1. Elige el sitio web:", ["InterPatagonia", "WelcomeArgentina"])
    ciudad_input = st.text_input("2. Escribe la ciudad (URL):", placeholder="ej: villa-la-angostura")

with col2:
    st.info("💡 **Ayuda:**\n\nPrimero presiona 'Analizar Ciudad' para ver cuántos alojamientos hay.\n\nLuego selecciona la cantidad y presiona 'Extraer Datos'.")

if st.button("🔍 1. ANALIZAR CIUDAD", type="secondary", use_container_width=True):
    if not ciudad_input:
        st.warning("⚠️ ¡Falta escribir la ciudad!")
    else:
        ciudad_clean = ciudad_input.strip().lower().replace(" ", "-")
        with st.spinner(f"Analizando {sitio_elegido}..."):
            enlaces = buscar_enlaces(sitio_elegido, ciudad_clean)
            
            if enlaces is None:
                st.error("No se pudo entrar a la página. Revisa que la ciudad esté bien escrita.")
                st.session_state.urls_encontradas = []
            elif not enlaces:
                st.warning("Se encontró la página pero no hay alojamientos.")
                st.session_state.urls_encontradas = []
            else:
                st.session_state.urls_encontradas = enlaces
                st.session_state.ciudad_actual = ciudad_clean
                st.session_state.sitio_actual = sitio_elegido
                st.success(f"¡Éxito! Se encontraron {len(enlaces)} alojamientos.")

if len(st.session_state.urls_encontradas) > 0:
    st.divider()
    st.subheader(f"📍 Resultados para: {st.session_state.ciudad_actual}")
    
    total_disponible = len(st.session_state.urls_encontradas)
    limite = st.slider("Selecciona cantidad a extraer:", 1, total_disponible, total_disponible)
    
    if st.button(f"🚀 2. EXTRAER DATOS ({limite})", type="primary", use_container_width=True):
        
        lista_a_procesar = st.session_state.urls_encontradas[:limite]
        
        barra_carga = st.progress(0)
        mensaje_estado = st.empty()
        
        datos = procesar_fichas(lista_a_procesar, 
                                st.session_state.sitio_actual, 
                                st.session_state.ciudad_actual, 
                                barra_carga, 
                                mensaje_estado)
        
        if datos:
            df = pd.DataFrame(datos)
            st.balloons()
            mensaje_estado.success("¡Proceso Terminado!")
            
            st.subheader("Vista Previa:")
            st.dataframe(df.head())
            
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            
            file_name = f"Datos_{st.session_state.sitio_actual}_{st.session_state.ciudad_actual}.csv"
            
            st.download_button(
                label=f"📥 DESCARGAR ARCHIVO ({len(datos)} datos)",
                data=csv,
                file_name=file_name,
                mime="text/csv",
                type="primary"
            )