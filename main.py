import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import requests
import pydeck as pdk
import matplotlib.pyplot as plt
import numpy as np

# ==============================================================================
# 1. CONFIGURACIÓN DEL ENTORNO
# ==============================================================================
st.set_page_config(
    page_title="SIMU ING - Ingeniería Solar",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS para simular software profesional
st.markdown("""
    <style>
    .main {background-color: #f4f6f8;}
    /* Barra lateral técnica */
    [data-testid="stSidebar"] {
        background-color: #2c3e50;
        color: white;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] span {
        color: #ecf0f1 !important;
    }
    /* Títulos principales */
    h1, h2, h3 {
        color: #2980b9;
        font-family: 'Segoe UI', sans-serif;
    }
    /* Tarjetas de métricas */
    div.css-1r6slb0 {
        border: 1px solid #dcdcdc;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 15px;
        border-radius: 5px;
        background-color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Inicialización de variables de estado
if 'n_paneles_real' not in st.session_state: st.session_state.n_paneles_real = 12
if 'gen_total_mensual' not in st.session_state: st.session_state.gen_total_mensual = 0.0
if 'potencia_sistema_kw' not in st.session_state: st.session_state.potencia_sistema_kw = 0.0

# ==============================================================================
# 2. FUNCIONES DE CÁLCULO E INGENIERÍA
# ==============================================================================

def limpiar(texto):
    """Limpia caracteres especiales para PDF (Latin-1)"""
    if texto is None: return ""
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', '°': 'deg'
    }
    s = str(texto)
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode('latin-1', 'replace').decode('latin-1')

def simulacion_pvsyst(potencia_dc_kw, hsp_sitio, temp_amb_grados):
    """Motor simplificado de simulación energética"""
    perdida_temp = 0.004 * max(0, temp_amb_grados - 25)
    perdidas_sistema = 0.14
    eficiencia_global = 1 - (perdidas_sistema + perdida_temp)
    generacion_diaria = potencia_dc_kw * hsp_sitio * eficiencia_global
    return generacion_diaria, eficiencia_global

def dibujar_tierra_pdf(pdf, x, y):
    """Dibuja el símbolo técnico de tierra en el PDF"""
    pdf.line(x, y, x, y+2) 
    pdf.line(x-2, y+2, x+2, y+2) 
    pdf.line(x-1.2, y+2.8, x+1.2, y+2.8) 
    pdf.line(x-0.5, y+3.6, x+0.5, y+3.6) 

# ==============================================================================
# 3. BASE DE DATOS TÉCNICA
# ==============================================================================
def cargar_biblioteca():
    data_ciudades = {
        "San José del Guaviare": {"lat": 2.5729, "lon": -72.6378, "hsp": 4.6, "depto": "Guaviare"},
        "Bogotá D.C.": {"lat": 4.7110, "lon": -74.0721, "hsp": 4.2, "depto": "Cundinamarca"},
        "Medellín": {"lat": 6.2442, "lon": -75.5812, "hsp": 4.8, "depto": "Antioquia"},
        "Cali": {"lat": 3.4516, "lon": -76.5320, "hsp": 4.9, "depto": "Valle del Cauca"},
        "Barranquilla": {"lat": 10.9685, "lon": -74.7813, "hsp": 5.8, "depto": "Atlántico"},
        "Leticia": {"lat": -4.2153, "lon": -69.9406, "hsp": 4.5, "depto": "Amazonas"},
        "Villavicencio": {"lat": 4.1420, "lon": -73.6266, "hsp": 4.7, "depto": "Meta"}
    }
    
    data_paneles = {
        "Referencia": ["Panel 450W Monocristalino", "Panel 550W Bifacial", "Panel 600W Industrial"],
        "Potencia": [450, 550, 600],
        "Voc": [41.5, 49.6, 41.7],
        "Precio": [550000, 720000, 850000] 
    }
    
    data_inversores = {
        "Referencia": ["Microinversor 1.2kW", "Inversor 3kW", "Inversor 5kW Híbrido", "Inversor 10kW Trifásico"],
        "Potencia": [1200, 3000, 5000, 10000],
        "Vmin": [20, 80, 120, 180],
        "Vmax": [60, 600, 600, 1000],
        "Precio": [1200000, 2500000, 4500000, 7000000] 
    }
    return data_ciudades, pd.DataFrame(data_paneles), pd.DataFrame(data_inversores)

db_ciudades, df_modulos, df_inversores = cargar_biblioteca()

# ==============================================================================
# 4. INTERFAZ DE USUARIO (GUI TIPO PVSYST)
# ==============================================================================

# --- BARRA LATERAL ---
st.sidebar.title("SIMU ING v5.0")
st.sidebar.markdown("**Software de Ingeniería Fotovoltaica**")

# Login simulado
with st.sidebar.expander("🔐 Acceso", expanded=True):
    password = st.text_input("Clave de Licencia", type="password")
    if password != "SOLAR2025":
        st.error("Sistema Bloqueado")
        st.stop()
    st.success("Licencia Profesional Activa")

st.sidebar.markdown("---")

# Configuración del Sitio
st.sidebar.subheader("🌍 1. Sitio y Meteo")
ciudad_sel = st.sidebar.selectbox("Ubicación del Proyecto", list(db_ciudades.keys()))
info_ciudad = db_ciudades[ciudad_sel]

col_m1, col_m2 = st.sidebar.columns(2)
col_m1.metric("Latitud", f"{info_ciudad['lat']}°")
col_m2.metric("HSP", f"{info_ciudad['hsp']}")

# Configuración de Orientación
st.sidebar.subheader("📐 2. Orientación")
tilt = st.sidebar.slider("Inclinación (°)", 0, 90, 15)
azimut = st.sidebar.slider("Azimut (°)", -180, 180, 0)

# Datos del Cliente
st.sidebar.markdown("---")
st.sidebar.subheader("📋 3. Datos Cliente")
cliente = st.sidebar.text_input("Nombre / Razón Social", "Cliente General")
fecha_proy = st.sidebar.date_input("Fecha", datetime.now())

# --- PANEL PRINCIPAL ---
st.title("SIMU ING - Entorno de Simulación")

# Mapa Satelital
st.pydeck_chart(pdk.Deck(
    map_style='mapbox://styles/mapbox/satellite-v9',
    initial_view_state=pdk.ViewState(
        latitude=info_ciudad['lat'],
        longitude=info_ciudad['lon'],
        zoom=16,
        pitch=0,
    ),
    layers=[
        pdk.Layer(
            "ScatterplotLayer",
            data=pd.DataFrame([{"lat": info_ciudad['lat'], "lon": info_ciudad['lon']}]),
            get_position="[lon, lat]",
            get_color=[255, 0, 0, 160],
            get_radius=50,
        ),
    ],
    height=300
))

# --- PESTAÑAS DE FLUJO DE TRABAJO ---
tabs = st.tabs(["🏗️ Diseño del Sistema", "📊 Simulación", "💰 Análisis Económico", "📄 Reporte PDF"])

# PESTAÑA 1: DISEÑO
with tabs[0]:
    st.subheader("Definición de Arquitectura del Sistema")
    
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
        st.markdown("##### Selección de Módulos")
        ref_panel = st.selectbox("Modelo de Panel", df_modulos["Referencia"])
        dato_panel = df_modulos[df_modulos["Referencia"] == ref_panel].iloc[0]
        
        consumo = st.number_input("Consumo Mensual Objetivo (kWh)", 100, 50000, 567)
        # Cálculo inverso para sugerencia
        n_sug = int(consumo / (dato_panel["Potencia"]/1000 * info_ciudad['hsp'] * 30 * 0.8)) + 1
        st.info(f"Sugerencia: {n_sug} paneles para cubrir {consumo} kWh")
        
        n_paneles = st.number_input("Cantidad de Módulos", 1, 500, n_sug)
        st.session_state.n_paneles_real = n_paneles
        
        potencia_total_dc = (n_paneles * dato_panel["Potencia"]) / 1000
        st.session_state.potencia_sistema_kw = potencia_total_dc
        st.success(f"**Potencia DC Total: {potencia_total_dc:.2f} kWp**")

    with col_d2:
        st.markdown("##### Selección de Inversor")
        ref_inv = st.selectbox("Modelo de Inversor", df_inversores["Referencia"])
        dato_inv = df_inversores[df_inversores["Referencia"] == ref_inv].iloc[0]
        
        st.markdown("##### Validación de Strings")
        n_ser = st.slider("Módulos en Serie", 1, 25, 11)
        voc_array = dato_panel["Voc"] * n_ser * 1.15 # Factor seguridad frío
        
        c_v1, c_v2 = st.columns(2)
        c_v1.metric("Voc Array (-10°C)", f"{voc_array:.1f} V")
        c_v2.metric("Vmax Inversor", f"{dato_inv['Vmax']} V")
        
        if voc_array > dato_inv['Vmax']:
            st.error("🛑 PELIGRO: Voltaje excesivo para el inversor")
        else:
            st.success("✅ Diseño Eléctrico Correcto")

# PESTAÑA 2: SIMULACIÓN
with tabs[1]:
    st.subheader("Resultados de Simulación")
    
    # Motor de Cálculo
    gen_dia, pr = simulacion_pvsyst(potencia_total_dc, info_ciudad['hsp'], 28)
    gen_mensual = gen_dia * 30
    st.session_state.gen_total_mensual = gen_mensual
    gen_anual = gen_mensual * 12
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Generación Anual", f"{gen_anual:,.0f} kWh")
    col_kpi2.metric("PR (Performance Ratio)", f"{pr*100:.1f}%")
    col_kpi3.metric("Generación Específica", f"{gen_anual/potencia_total_dc:.0f} kWh/kWp")
    
    # Gráficas para PDF (Ocultas pero generadas)
    # 1. Trayectoria Solar
    fig_sun, ax_sun = plt.subplots(figsize=(5, 3))
    az = np.linspace(-90, 90, 100)
    alt_ver = 70 * np.cos(np.radians(az))
    alt_inv = 45 * np.cos(np.radians(az))
    ax_sun.plot(az, alt_ver, color='orange', label='Verano')
    ax_sun.plot(az, alt_inv, color='blue', label='Invierno')
    ax_sun.fill_between(az, 0, 15, color='gray', alpha=0.3)
    ax_sun.set_title("Trayectoria Solar")
    ax_sun.grid(True, linestyle='--')
    fig_sun.savefig("temp_sunpath.png", bbox_inches='tight')
    plt.close(fig_sun)

    # 2. Curva Diaria
    h = np.arange(6, 19)
    irr = np.sin(np.pi * (h-6)/12) * 1000
    fig_irr, ax_irr = plt.subplots(figsize=(5, 3))
    ax_irr.plot(h, irr, color='#f1c40f')
    ax_irr.fill_between(h, irr, color='#f1c40f', alpha=0.2)
    ax_irr.set_title("Curva de Generación Diaria")
    ax_irr.grid(True)
    fig_irr.savefig("temp_curve.png", bbox_inches='tight')
    plt.close(fig_irr)

    # 3. Barras Comparativas (Visible)
    meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    consumo_list = [consumo] * 12
    gen_list = [gen_mensual] * 12
    
    fig_bar, ax_bar = plt.subplots(figsize=(10, 4))
    x = np.arange(len(meses))
    width = 0.35
    ax_bar.bar(x - width/2, consumo_list, width, label='Consumo', color='#e74c3c')
    ax_bar.bar(x + width/2, gen_list, width, label='Generación Solar', color='#2ecc71')
    ax_bar.set_xticks(x); ax_bar.set_xticklabels(meses)
    ax_bar.legend()
    ax_bar.set_title("Balance Energético Mensual")
    st.pyplot(fig_bar)
    fig_bar.savefig("temp_bars.png", bbox_inches='tight')

# PESTAÑA 3: ECONÓMICO
with tabs[2]:
    st.subheader("Evaluación Económica")
    
    col_ec1, col_ec2 = st.columns(2)
    
    with col_ec1:
        st.markdown("###### CAPEX (Costos)")
        costo_paneles = n_paneles * dato_panel["Precio"]
        costo_inv = dato_inv["Precio"]
        costo_bos = n_paneles * 200000 
        costo_ing = potencia_total_dc * 600000 
        costo_total = costo_paneles + costo_inv + costo_bos + costo_ing
        
        st.write(f"**Inversión Total:** ${costo_total:,.0f} COP")
        
        tarifa = st.number_input("Tarifa Energía ($/kWh)", 850)
        ahorro = gen_mensual * tarifa
        roi = costo_total / (ahorro * 12) if ahorro > 0 else 0
        st.metric("ROI", f"{roi:.1f} Años")

    with col_ec2:
        # Flujo de Caja Gráfico
        flujo = [-costo_total]
        for _ in range(25): flujo.append(flujo[-1] + (ahorro*12*1.05))
        
        fig_roi, ax_roi = plt.subplots(figsize=(8, 4))
        ax_roi.plot(flujo, color='green')
        ax_roi.axhline(0, color='black', linestyle='--')
        ax_roi.set_title("Flujo de Caja Acumulado (25 Años)")
        ax_roi.grid(True)
        st.pyplot(fig_roi)
        fig_roi.savefig("temp_roi.png", bbox_inches='tight')

# PESTAÑA 4: REPORTE PDF
with tabs[3]:
    st.subheader("Generar Entregable")
    
    if st.button("📄 Generar Reporte PDF (SIMU ING)", use_container_width=True):
        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # === PÁGINA 1: PORTADA Y SOLAR ===
            pdf.add_page()
            # Encabezado Azul
            pdf.set_fill_color(10, 40, 90)
            pdf.rect(0, 0, 210, 40, 'F')
            pdf.set_text_color(255)
            pdf.set_font('Arial', 'B', 24); pdf.set_xy(10, 15); pdf.cell(0, 10, 'PROPUESTA TECNICA', 0, 1)
            pdf.set_font('Arial', '', 12); pdf.set_xy(10, 25); pdf.cell(0, 5, 'SISTEMA DE ENERGIA SOLAR FOTOVOLTAICA', 0, 1)
            pdf.set_text_color(0); pdf.ln(25)
            
            # Tabla Datos
            pdf.set_font('Arial', 'B', 12); pdf.set_fill_color(230, 230, 230)
            pdf.cell(0, 10, "  DATOS DEL PROYECTO", 0, 1, 'L', True); pdf.ln(2)
            
            pdf.set_font('Arial', '', 11)
            datos = [("Cliente:", limpiar(cliente)), ("Ubicacion:", limpiar(ciudad_sel)), 
                     ("Potencia DC:", f"{potencia_total_dc:.2f} kWp"), ("Generacion Mensual:", f"{gen_mensual:.0f} kWh")]
            for k,v in datos:
                pdf.set_font('Arial','B',11); pdf.cell(45, 8, k, 0)
                pdf.set_font('Arial','',11); pdf.cell(0, 8, v, 0, 1)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
            pdf.ln(10)
            # Imágenes Solares
            pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, "ANALISIS DE RECURSO SOLAR", 0, 1)
            y = pdf.get_y()
            if os.path.exists("temp_sunpath.png"): pdf.image("temp_sunpath.png", x=10, y=y, w=90)
            if os.path.exists("temp_curve.png"): pdf.image("temp_curve.png", x=105, y=y, w=90)
            
            # === PÁGINA 2: FINANCIERO ===
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, "ANALISIS FINANCIERO", 0, 1)
            if os.path.exists("temp_bars.png"): pdf.image("temp_bars.png", x=10, y=30, w=190)
            if os.path.exists("temp_roi.png"): pdf.image("temp_roi.png", x=10, y=120, w=190)
            
            pdf.set_y(230); pdf.set_font('Arial','',12)
            pdf.cell(0, 10, f"Inversion: ${costo_total:,.0f} | Retorno: {roi:.1f} Anios", 0, 1, 'C')

            # === PÁGINA 3: UNIFILAR CAD DETALLADO ===
            pdf.add_page('L')
            # Marco
            pdf.set_line_width(0.5); pdf.rect(5, 5, 287, 200); pdf.rect(10, 10, 277, 190)
            # Cajetín
            pdf.line(10, 175, 287, 175)
            pdf.set_font('Arial','B',8)
            pdf.set_xy(15, 177); pdf.cell(20,5,"PROYECTO:"); pdf.set_xy(15,182); pdf.set_font('Arial','',8); pdf.cell(50,5,limpiar(cliente))
            pdf.set_xy(80, 177); pdf.set_font('Arial','B',8); pdf.cell(20,5,"UBICACION:"); pdf.set_xy(80,182); pdf.set_font('Arial','',8); pdf.cell(50,5,limpiar(ciudad_sel))
            pdf.set_xy(230, 177); pdf.set_font('Arial','B',8); pdf.cell(20,5,"PLANO:"); pdf.set_xy(230,182); pdf.set_font('Arial','',8); pdf.cell(30,5,"EL-01")

            # DIBUJO (Restaurado 100%)
            y_base = 80; xs = 30
            pdf.set_draw_color(0)
            # Paneles
            for i in range(3):
                pdf.rect(xs+i*15, y_base, 12, 20); pdf.line(xs+i*15, y_base+6, xs+i*15+12, y_base+6); pdf.line(xs+i*15, y_base+13, xs+i*15+12, y_base+13)
            pdf.set_font('Arial','B',8); pdf.text(xs, y_base-5, "GENERADOR FV")
            pdf.set_font('Arial','',7); pdf.text(xs, y_base-2, f"{n_paneles} x {dato_panel['Potencia']}W")
            # DC
            pdf.set_draw_color(200,0,0); pdf.line(xs+36, y_base+2, 90, y_base+2); pdf.text(70, y_base+1, "DC+")
            pdf.set_draw_color(0); pdf.line(xs+36, y_base+18, 90, y_base+18); pdf.text(70, y_base+17, "DC-")
            # Tierra
            pdf.set_draw_color(0,150,0); pdf.line(xs+6, y_base+20, xs+6, y_base+35); pdf.line(xs+6, y_base+35, 250, y_base+35); pdf.text(xs+7, y_base+30, "T")
            # Caja DC
            pdf.set_draw_color(0); pdf.rect(90, y_base-10, 40, 40); pdf.set_font('Arial','B',7); pdf.text(92, y_base-7, "TABLERO DC")
            pdf.rect(95, y_base+4, 5, 2); pdf.rect(95, y_base+14, 5, 2) # Fusibles
            pdf.rect(110, y_base+8, 6, 10); pdf.text(111, y_base+7, "DPS"); pdf.line(113, y_base+18, 113, y_base+35)
            # Inversor
            pdf.rect(150, y_base-5, 30, 30); pdf.set_font('Arial','B',8); pdf.text(152, y_base, "INVERSOR")
            pdf.set_font('Arial','',6); pdf.text(152, y_base+5, f"{dato_inv['Potencia']}W")
            pdf.set_draw_color(200,0,0); pdf.line(130, y_base+2, 150, y_base+2); pdf.set_draw_color(0); pdf.line(130, y_base+18, 150, y_base+18)
            pdf.set_draw_color(0,150,0); pdf.line(165, y_base+25, 165, y_base+35)
            # AC
            pdf.set_draw_color(0); pdf.line(180, y_base+10, 200, y_base+10); pdf.line(180, y_base+15, 200, y_base+15)
            pdf.rect(200, y_base-5, 30, 30); pdf.text(202, y_base-2, "TAB AC")
            pdf.rect(205, y_base+8, 5, 10); pdf.line(205, y_base+13, 210, y_base+8); pdf.text(205, y_base+7, "Brk")
            pdf.line(230, y_base+10, 250, y_base+10); pdf.line(230, y_base+15, 250, y_base+15)
            # Medidor
            pdf.rect(250, y_base, 20, 20)
            try:
                if hasattr(pdf, 'ellipse'): pdf.ellipse(254, y_base+5, 12, 12)
                else: pdf.circle(260, y_base+11, 6)
            except: pdf.text(257, y_base+15, "M")
            pdf.set_font('Arial','B',10); pdf.text(256, y_base+12, "kWh")
            # Red
            pdf.line(270, y_base+10, 280, y_base+10); pdf.line(270, y_base+15, 280, y_base+15); pdf.text(275, y_base+8, "RED")
            # Tierra General
            pdf.set_draw_color(0,150,0); dibujar_tierra_pdf(pdf, 150, y_base+35); pdf.text(152, y_base+40, "SPT")

            # === PÁGINA 4: PRESUPUESTO ===
            pdf.add_page('P')
            pdf.set_font('Arial', 'B', 16); pdf.cell(0, 10, 'PRESUPUESTO DETALLADO', 0, 1, 'C'); pdf.ln(10)
            pdf.set_fill_color(200, 220, 255); pdf.set_font('Arial', 'B', 10)
            pdf.cell(100, 10, 'Descripcion', 1, 0, 'C', True); pdf.cell(20, 10, 'Cant', 1, 0, 'C', True); pdf.cell(35, 10, 'Unit', 1, 0, 'C', True); pdf.cell(35, 10, 'Total', 1, 1, 'C', True)
            pdf.set_font('Arial', '', 10)
            
            items = [
                (f"Panel Solar {dato_panel['Referencia']}", n_paneles, dato_panel['Precio']),
                (f"Inversor {dato_inv['Referencia']}", 1, dato_inv['Precio']),
                ("Estructura de Montaje", n_paneles, 150000),
                ("Kit Electrico (Cable, DPS)", 1, costo_bos),
                ("Mano de Obra e Ing.", 1, costo_ing)
            ]
            for d, c, u in items:
                t = c * u
                pdf.cell(100, 10, limpiar(d[:50]), 1); pdf.cell(20, 10, str(int(c)), 1, 0, 'C'); pdf.cell(35, 10, f"${u:,.0f}", 1, 0, 'R'); pdf.cell(35, 10, f"${t:,.0f}", 1, 1, 'R')
            pdf.set_font('Arial', 'B', 12); pdf.cell(155, 10, "GRAN TOTAL", 1, 0, 'R'); pdf.cell(35, 10, f"${costo_total:,.0f}", 1, 1, 'R')

            # Salida
            pdf_bytes = pdf.output(dest='S')
            if isinstance(pdf_bytes, str): pdf_bytes = pdf_bytes.encode('latin-1')
            st.download_button("📥 DESCARGAR REPORTE", pdf_bytes, f"SIMU_ING_{limpiar(cliente)}.pdf", "application/pdf")
            st.success("✅ Reporte Generado")

        except Exception as e:
            st.error(f"Error PDF: {e}")
