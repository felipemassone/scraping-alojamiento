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

# ============================================
# SESSION STATE
# ============================================
if 'urls_encontradas' not in st.session_state:
    st.session_state.urls_encontradas = []
if 'ciudad_actual' not in st.session_state:
    st.session_state.ciudad_actual = ""
if 'sitio_actual' not in st.session_state:
    st.session_state.sitio_actual = ""

# ============================================
# FUNCIONES PARA INTERPATAGONIA Y WELCOMEARGENTINA
# ============================================

def limpiar_y_extraer(texto_completo, soup_objeto):
    texto_limpio = re.sub(r'200\d\s?[-—]\s?202\d', '', texto_completo) 
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
        estado.text(f"Procesando {i+1}/{total}...")
        
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

# ============================================
# FUNCIONES PARA TURISMOCORDOBA
# ============================================

def buscar_enlaces_turismocordoba(ciudad):
    """
    Busca enlaces de alojamientos en turismocordoba.com.ar
    """
    base_url = "https://www.turismocordoba.com.ar"
    
    # Formatear ciudad para URL
    ciudad_url = ciudad.replace(' ', '+').title()
    url_buscador = f"{base_url}/buscador/?localidad={ciudad_url}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        resp = requests.get(url_buscador, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
    except:
        return []
    
    links_fichas = []
    
    # Buscar enlaces que apuntan a "Más Info"
    for link in soup.find_all('a', href=True):
        href = link['href']
        texto_link = link.get_text(strip=True).lower()
        
        if 'más info' in texto_link or 'm�s info' in texto_link:
            # Limpiar la URL
            if href.startswith('http://') or href.startswith('https://'):
                url_limpia = href.split('?')[0]
            elif href.startswith('/'):
                url_limpia = base_url + href.split('?')[0]
            else:
                url_limpia = f"{base_url}/{href}".split('?')[0]
            
            # Verificar que sea de turismocordoba y no externa
            if 'turismocordoba.com.ar' in url_limpia and 'booking.com' not in url_limpia:
                if url_limpia not in links_fichas:
                    links_fichas.append(url_limpia)
    
    return links_fichas

def procesar_fichas_turismocordoba(lista_urls, ciudad, barra, estado):
    """
    Procesa fichas individuales de turismocordoba.com.ar
    """
    datos_finales = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    total = len(lista_urls)
    descartados = 0
    
    for i, url in enumerate(lista_urls):
        progreso = (i + 1) / total
        barra.progress(progreso)
        estado.text(f"Procesando {i+1}/{total} (Descartados: {descartados})...")
        
        try:
            time.sleep(random.uniform(0.3, 0.8))
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            texto_completo = soup.get_text()
            
            # VALIDACIÓN: Verificar que mencione la ciudad
            ciudad_normalizada = ciudad.lower()
            ciudad_valida = False
            
            if ciudad_normalizada in texto_completo.lower():
                ciudad_valida = True
            else:
                # Verificar variaciones comunes
                variaciones = {
                    'villa carlos paz': ['carlos paz', 'vcp', 'villa carlos'],
                    'cordoba': ['córdoba', 'cba', 'cordoba capital'],
                    'villa general belgrano': ['v.g.belgrano', 'belgrano', 'vgb'],
                    'la cumbre': ['lacumbre'],
                    'la cumbrecita': ['lacumbrecita']
                }
                
                if ciudad_normalizada in variaciones:
                    for variacion in variaciones[ciudad_normalizada]:
                        if variacion in texto_completo.lower():
                            ciudad_valida = True
                            break
            
            if not ciudad_valida:
                descartados += 1
                continue
            
            # Extraer nombre
            nombre = "Desconocido"
            for tag in ['h1', 'h2', 'h5', 'h3']:
                elemento = soup.find(tag)
                if elemento:
                    nombre = elemento.get_text(strip=True)
                    break
            
            # Extraer teléfonos de enlaces tel:
            telefonos_encontrados = set()
            for tel_link in soup.find_all('a', href=re.compile(r'^tel:', re.I)):
                tel = tel_link['href'].replace('tel:', '').strip()
                tel = tel.replace(' ', '').replace('-', '')
                if len(tel) >= 7:
                    telefonos_encontrados.add(tel)
            
            # Buscar "Teléfono:" y "Móvil:" en el texto
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
            
            # Buscar WhatsApp
            whatsapp_detectado = "No"
            wsp_number = ""
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                texto = link.get_text(strip=True).lower()
                
                if 'whatsapp' in href or 'whatsapp' in texto:
                    whatsapp_detectado = "Sí"
                    num_match = re.search(r'(\d{10,15})', href)
                    if num_match:
                        wsp_number = num_match.group(1)
                    break
            
            # Buscar email
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', texto_completo)
            email_encontrado = ", ".join(set(emails[:2])) if emails else "No encontrado"
            
            # Formatear teléfonos
            if telefonos_encontrados:
                resultado_telefonos = " / ".join(sorted(list(telefonos_encontrados)))
            else:
                resultado_telefonos = "No encontrado"
            
            if wsp_number and wsp_number not in resultado_telefonos:
                if resultado_telefonos == "No encontrado":
                    resultado_telefonos = f"WhatsApp: {wsp_number}"
                else:
                    resultado_telefonos += f" / WhatsApp: {wsp_number}"
            
            datos_finales.append({
                'Nombre': nombre,
                'Telefonos': resultado_telefonos,
                'Email': email_encontrado,
                'WhatsApp': whatsapp_detectado,
                'Ciudad': ciudad,
                'Web': 'TurismoCordoba',
                'Link': url
            })
            
        except Exception as e:
            continue
    
    return datos_finales

# ============================================
# INTERFAZ STREAMLIT
# ============================================

st.title("🔎 Buscador de Alojamientos")
st.markdown("Herramienta interna para Scraping de alojamientos.")
st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    sitio_elegido = st.radio(
        "1. Elige el sitio web:", 
        ["InterPatagonia", "WelcomeArgentina", "TurismoCordoba"]
    )
    ciudad_input = st.text_input("2. Escribe la ciudad (URL):", placeholder="ej: bariloche")

with col2:
    if sitio_elegido == "TurismoCordoba":
        st.info("""
        💡 **INSTRUCCIONES - TurismoCordoba**
        
        Escribe el nombre de la ciudad como quieras:
        
        * `Villa Carlos Paz` ✅
        * `villa carlos paz` ✅
        * `VILLA CARLOS PAZ` ✅
        
        **Acepta mayúsculas, minúsculas y espacios.**
        """)
    else:
        st.info("""
        💡 **INSTRUCCIONES - InterPatagonia/WelcomeArgentina**
        
        Escribe la ciudad de cualquier forma, se normalizará automáticamente:
        
        * `Puerto Iguazú` → `puertoiguazu` ✅
        * `San Martín de los Andes` → `sanmartindelosandes` ✅
        * `EL CALAFATE` → `elcalafate` ✅
        * `Villa La Angostura` → `villalaangostura` ✅
        
        **Se convertirá automáticamente: minúsculas, sin espacios, sin acentos, todo junto.**
        """)

if st.button("🔍 1. ANALIZAR CIUDAD", type="secondary", use_container_width=True):
    if not ciudad_input:
        st.warning("⚠️ ¡Falta escribir la ciudad!")
    else:
        # NORMALIZACIÓN AUTOMÁTICA según el sitio
        if sitio_elegido == "TurismoCordoba":
            # TurismoCordoba: acepta cualquier formato
            ciudad_clean = ciudad_input.strip()
        else:
            # InterPatagonia/WelcomeArgentina: todo junto, sin espacios ni guiones
            # Convertir a minúsculas, quitar espacios, quitar guiones, quitar acentos
            ciudad_clean = ciudad_input.strip().lower()
            ciudad_clean = ciudad_clean.replace(" ", "")  # Sin espacios
            ciudad_clean = ciudad_clean.replace("-", "")  # Sin guiones
            ciudad_clean = ciudad_clean.replace("_", "")  # Sin guiones bajos
            # Quitar acentos comunes
            reemplazos = {
                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
                'ñ': 'n', 'ü': 'u'
            }
            for acento, sin_acento in reemplazos.items():
                ciudad_clean = ciudad_clean.replace(acento, sin_acento)
        
        with st.spinner(f"Analizando {sitio_elegido}..."):
            # Determinar qué función usar según el sitio
            if sitio_elegido == "TurismoCordoba":
                enlaces = buscar_enlaces_turismocordoba(ciudad_clean)
            else:
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
    st.subheader(f"📊 Resultados para: {st.session_state.ciudad_actual}")
    
    # Mostrar info adicional para TurismoCordoba
    if st.session_state.sitio_actual == "TurismoCordoba":
        st.info(f"""
        📌 **Total disponible:** {len(st.session_state.urls_encontradas)} alojamientos
        
        ⚠️ **Nota:** Los alojamientos se validan durante la extracción. 
        Algunos pueden ser descartados si no corresponden a la ciudad buscada.
        """)
    
    total_disponible = len(st.session_state.urls_encontradas)
    limite = st.slider("Selecciona cantidad a extraer:", 1, total_disponible, min(10, total_disponible))
    
    if st.button(f"🚀 2. EXTRAER DATOS ({limite})", type="primary", use_container_width=True):
        
        lista_a_procesar = st.session_state.urls_encontradas[:limite]
        
        barra_carga = st.progress(0)
        mensaje_estado = st.empty()
        
        # Determinar qué función usar según el sitio
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
            st.balloons()
            
            # Mostrar estadísticas
            if st.session_state.sitio_actual == "TurismoCordoba":
                descartados = limite - len(datos)
                if descartados > 0:
                    st.warning(f"⚠️ Se descartaron {descartados} alojamientos (no correspondían a la ciudad)")
                mensaje_estado.success(f"¡Proceso Terminado! Extraídos: {len(datos)}")
            else:
                mensaje_estado.success("¡Proceso Terminado!")
            
            # Mostrar estadísticas de contacto
            con_telefono = df[df['Telefonos'] != 'No encontrado'].shape[0]
            st.metric("Con Teléfono", f"{con_telefono}/{len(df)}", f"{con_telefono/len(df)*100:.1f}%")
            
            st.subheader("Vista Previa:")
            st.dataframe(df.head(10))
            
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            
            file_name = f"Datos_{st.session_state.sitio_actual}_{st.session_state.ciudad_actual}.csv"
            
            st.download_button(
                label=f"📥 DESCARGAR ARCHIVO ({len(datos)} datos)",
                data=csv,
                file_name=file_name,
                mime="text/csv",
                type="primary"
            )
        else:
            st.error("No se pudieron extraer datos. Todos los alojamientos fueron descartados.")
