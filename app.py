import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from urllib.parse import urljoin

st.set_page_config(
    page_title="Extractor de Alojamientos",
    page_icon="🏨",
    layout="centered"
)

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

def ejecutar_scraper(sitio, ciudad, limite, barra, estado):
    if sitio == "InterPatagonia":
        base_url = "https://www.interpatagonia.com"
    else:
        base_url = "https://www.welcomeargentina.com"
        
    url_listado = f"{base_url}/{ciudad}/alojamientos.html"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    estado.info(f"Conectando a: {url_listado}...")
    try:
        resp = requests.get(url_listado, headers=headers, timeout=10)
        if resp.status_code != 200:
            st.error("No se pudo entrar a la página. Revisa que la ciudad esté bien escrita.")
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        st.error(f"Error de conexión: {e}")
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
    
    lista_final = list(links_fichas)
    
    if limite > 0:
        lista_final = lista_final[:limite]
    
    total = len(lista_final)
    estado.success(f"¡Encontrados {total} alojamientos! Escaneando detalles...")
    
    datos_finales = []
    
    for i, url_hotel in enumerate(lista_final):
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

st.title("🔎 Buscador de Contactos")
st.markdown("Herramienta interna para **InterPatagonia** y **WelcomeArgentina**.")
st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    sitio_elegido = st.radio("1. Elige el sitio web:", 
                             ["InterPatagonia", "WelcomeArgentina"])
    
    ciudad_input = st.text_input("2. Escribe la ciudad (URL):", 
                                 placeholder="ej: villa-la-angostura")
    
    limite_input = st.number_input("3. Cantidad a buscar (0 = Todos):", 
                                   min_value=0, value=20, step=10)

with col2:
    st.info("💡 **Ayuda:**\n\nLa ciudad debe escribirse igual que en la dirección web.\n\nEjemplo: Si la web es `interpatagonia.com/el-calafate/`, escribe `el-calafate`.")

st.divider()

if st.button("🚀 INICIAR BÚSQUEDA", type="primary", use_container_width=True):
    
    if not ciudad_input:
        st.warning("⚠️ ¡Falta escribir la ciudad!")
    else:
        barra_carga = st.progress(0)
        mensaje_estado = st.empty()
        
        ciudad_clean = ciudad_input.strip().lower().replace(" ", "-")
        
        resultados = ejecutar_scraper(sitio_elegido, ciudad_clean, limite_input, barra_carga, mensaje_estado)
        
        if resultados:
            df = pd.DataFrame(resultados)
            
            st.balloons()
            mensaje_estado.success("¡Proceso Terminado!")
            
            st.subheader("Vista Previa:")
            st.dataframe(df.head())
            
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            
            file_name = f"Datos_{sitio_elegido}_{ciudad_clean}.csv"
            
            st.download_button(
                label=f"📥 DESCARGAR ARCHIVO ({len(resultados)} datos)",
                data=csv,
                file_name=file_name,
                mime="text/csv",
                type="primary"
            )
        else:
            mensaje_estado.error("No se encontraron resultados. ¿Estará bien escrita la ciudad?")