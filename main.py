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
# 1. CONFIGURACIÓN VISUAL (ESTILO PVSYST)
# ==============================================================================
st.set_page_config(
    page_title="SIMU ING - Diseño Fotovoltaico",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyección de CSS para simular software de escritorio
st.markdown("""
    <style>
    /* Fondo general gris técnico */
    .stApp {
        background-color: #f0f2f6;
    }
    /* Barra lateral estilo oscuro */
    [data-testid="stSidebar"] {
        background-color: #2c3e50;
        color: white;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #ecf0f1 !important;
    }
    /* Etiquetas de sidebar en blanco */
    [data-testid="stSidebar"] label {
        color: #bdc3c7 !important;
    }
    /* Contenedores blancos estilo tarjeta */
    .css-1r6slb0 {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    /* Títulos de secciones */
    h1, h2, h3 {
        color: #2980b9;
        font-family: 'Segoe UI', sans-serif;
    }
    /* Métricas destacadas */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        color: #2c3e50;
    }
    </style>
""", unsafe_allow_html=True)

# Inicialización de estado
if 'n_paneles_real' not in st.session_state: st.session_state.n_paneles_real = 10
if 'gen_total_mensual' not in st.session_state: st.session_state.gen_total_mensual = 0.0
if 'potencia_sistema_kw' not in st.session_state: st.session_state.potencia_sistema_kw = 0.0

# ==============================================================================
# 2. FUNCIONES DE CÁLCULO
# ==============================================================================
def limpiar(texto):
    if texto is None: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def simulacion_pvsyst(potencia_dc_kw, hsp_sitio, temp_amb_grados):
    perdida_temp = 0.004 * (temp_amb_grados - 25)
    if perdida_temp < 0: perdida_temp = 0
    perdidas_sistema = 0.14
    eficiencia_global = 1 - (perdidas_sistema + perdida_temp)
    generacion_diaria = potencia_dc_kw * hsp_sitio * eficiencia_global
    return generacion_diaria, eficiencia_global

def dibujar_tierra(pdf, x, y):
    pdf.line(x, y, x, y+2) 
    pdf.line(x-2, y+2, x+2, y+2) 
    pdf.line(x-1.2, y+2.8, x+1.2, y+2.8) 
    pdf.line(x-0.5, y+3.6, x+0.5, y+3.6) 

# ==============================================================================
# 3. BASE DE DATOS
# ==============================================================================
def cargar_biblioteca():
    data_ciudades = {
        "Departamento": ["Amazonas", "Antioquia", "Arauca", "Atlántico", "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Bogotá D.C.", "Guainía", "Guaviare", "Huila", "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda", "San Andrés", "Santander", "Sucre", "Tolima", "Valle del Cauca", "Vaupés", "Vichada"],
        "Ciudad": ["Leticia", "Medellín", "Arauca", "Barranquilla", "Cartagena", "Tunja", "Manizales", "Florencia", "Yopal", "Popayán", "Valledupar", "Quibdó", "Montería", "Girardot", "Bogotá", "Inírida", "San José del Guaviare", "Neiva", "Riohacha", "Santa Marta", "Villavicencio", "Pasto", "Cúcuta", "Mocoa", "Armenia", "Pereira", "San Andrés", "Bucaramanga", "Sincelejo", "Ibagué", "Cali", "Mitú", "Puerto Carreño"],
        "HSP": [4.5, 4.8, 5.2, 5.5, 5.3, 4.6, 4.2, 4.0, 4.9, 4.5, 5.6, 3.8, 5.1, 4.8, 4.2, 4.6, 4.5, 5.2, 6.0, 5.5, 4.7, 4.3, 5.0, 3.9, 4.4, 4.5, 5.2, 5.0, 5.2, 4.9, 4.8, 4.4, 5.1]
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
    return pd.DataFrame(data_ciudades), pd.DataFrame(data_paneles), pd.DataFrame(data_inversores)

df_ciudades, df_modulos, df_inversores = cargar_biblioteca()

coordenadas_ciudades = {
    "Bucaramanga": [7.1193, -73.1227], "Bogotá": [4.7110, -74.0721], "Medellín": [6.2442, -75.5812], 
    "Cali": [3.4516, -76.5320], "Barranquilla": [10.9685, -74.7813], "San José del Guaviare": [2.5729, -72.6378], 
    "Colombia": [4.5709, -74.2973], "Leticia": [-4.2153, -69.9406], "Villavicencio": [4.1420, -73.6266]
}

# ==============================================================================
# 4. INTERFAZ DE USUARIO (GUI)
# ==============================================================================

# --- SIDEBAR: PANEL DE CONTROL ---
st.sidebar.title("🛠️ Configuración")
password = st.sidebar.text_input("🔑 Licencia / Clave", type="password")
if password != "SOLAR2025":
    st.sidebar.error("Sistema Bloqueado")
    st.stop()

st.sidebar.success("✅ Licencia Activa")
st.sidebar.markdown("---")

st.sidebar.subheader("1. Ubicación")
ciudad_sel = st.sidebar.selectbox("Ciudad Base", list(coordenadas_ciudades.keys()))
lat_atlas = st.sidebar.number_input("Latitud (°)", value=coordenadas_ciudades.get(ciudad_sel, [4.5, -74])[0], format="%.4f")
lon_atlas = st.sidebar.number_input("Longitud (°)", value=coordenadas_ciudades.get(ciudad_sel, [4.5, -74])[1], format="%.4f")

st.sidebar.subheader("2. Orientación")
tilt = st.sidebar.slider("Inclinación Panel (°)", 0, 90, 15)
azimut = st.sidebar.slider("Azimut (°)", -180, 180, 0)

# --- PANEL PRINCIPAL ---
st.title("SIMU ING - Entorno de Simulación")
col_main1, col_main2 = st.columns([1, 3])

with col_main1:
    st.info("📋 **Datos del Cliente**")
    cliente = st.text_input("Nombre / Empresa", "Cliente General")
    fecha_proy = st.date_input("Fecha de Diseño", datetime.now())
    st.markdown("---")
    depto = st.selectbox("Departamento", df_ciudades["Departamento"].unique())
    ciudades_filtradas = df_ciudades[df_ciudades["Departamento"] == depto]
    ciudad = st.selectbox("Ciudad Proyecto", ciudades_filtradas["Ciudad"])
    try: hsp = ciudades_filtradas[ciudades_filtradas["Ciudad"] == ciudad].iloc[0]["HSP"]
    except: hsp = 4.5
    st.metric("Irradiación (HSP)", f"{hsp} kWh/m²")

with col_main2:
    # Mapa Profesional Estrecho
    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/satellite-streets-v11',
        initial_view_state=pdk.ViewState(latitude=lat_atlas, longitude=lon_atlas, zoom=16, pitch=45),
        layers=[
            pdk.Layer("IconLayer", pd.DataFrame([{"lat": lat_atlas, "lon": lon_atlas, "icon": {"url": "https://img.icons8.com/color/100/marker--v1.png", "width": 128, "height": 128, "anchorY": 128}}]), get_icon="icon", get_size=4, size_scale=15, get_position="[lon, lat]")
        ],
        height=350
    ))

# --- PESTAÑAS DE TRABAJO ---
tabs = st.tabs(["🏗️ Diseño del Sistema", "📊 Simulación y Análisis", "💰 Economía y Reporte"])

# TAB 1: DISEÑO
with tabs[0]:
    c_d1, c_d2 = st.columns(2)
    with c_d1:
        st.subheader("Campo Fotovoltaico")
        ref_panel = st.selectbox("Módulo PV", df_modulos["Referencia"])
        dato_panel = df_modulos[df_modulos["Referencia"] == ref_panel].iloc[0]
        
        consumo = st.number_input("Consumo Mensual (kWh)", 100, 50000, 500)
        n_sug = int(consumo / (dato_panel["Potencia"]/1000 * hsp * 30 * 0.8)) + 1
        st.caption(f"Sugerido: {n_sug} paneles")
        
        val_slider = st.number_input("Cantidad de Módulos", 1, 500, n_sug)
        st.session_state.n_paneles_real = val_slider
        st.session_state.potencia_sistema_kw = (val_slider * dato_panel["Potencia"]) / 1000
        st.metric("Potencia DC Total", f"{st.session_state.potencia_sistema_kw:.2f} kWp")

    with c_d2:
        st.subheader("Configuración Inversor")
        ref_inv = st.selectbox("Inversor", df_inversores["Referencia"])
        dato_inv = df_inversores[df_inversores["Referencia"] == ref_inv].iloc[0]
        
        st.markdown("##### Validación Eléctrica")
        n_ser = st.slider("Módulos en Serie", 1, 20, 10)
        voc = dato_panel["Voc"] * n_ser
        
        c_v1, c_v2 = st.columns(2)
        c_v1.metric("Voc String", f"{voc:.1f} V")
        c_v2.metric("Vmax Inversor", f"{dato_inv['Vmax']} V")
        
        if voc > dato_inv["Vmax"]: st.error("❌ Diseño Inválido: Voltaje Excesivo")
        else: st.success("✅ Diseño Eléctrico Correcto")

# TAB 2: SIMULACIÓN
with tabs[1]:
    col_sim1, col_sim2 = st.columns([2, 1])
    temp = 28.0
    
    gen_dia, ef = simulacion_pvsyst(st.session_state.potencia_sistema_kw, hsp, temp)
    st.session_state.gen_total_mensual = gen_dia * 30
    
    with col_sim1:
        st.subheader("Producción de Energía")
        # Gráfica Barras Mensuales
        meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
        gen_solar = [st.session_state.gen_total_mensual] * 12
        consumo_red = [consumo] * 12
        
        x = np.arange(len(meses))
        width = 0.35
        fig_bar, ax_bar = plt.subplots(figsize=(8, 4))
        ax_bar.bar(x - width/2, consumo_red, width, label='Consumo', color='#e74c3c')
        ax_bar.bar(x + width/2, gen_solar, width, label='Generación', color='#2ecc71')
        ax_bar.set_xticks(x); ax_bar.set_xticklabels(meses)
        ax_bar.legend(); ax_bar.grid(axis='y', alpha=0.3)
        st.pyplot(fig_bar)
        fig_bar.savefig("temp_bars.png", bbox_inches='tight')

    with col_sim2:
        st.subheader("KPIs del Sistema")
        st.metric("Generación Mensual", f"{st.session_state.gen_total_mensual:.0f} kWh")
        st.metric("Generación Anual", f"{st.session_state.gen_total_mensual*12:,.0f} kWh")
        st.metric("Performance Ratio", f"{ef*100:.1f}%")

    # Gráficas Ocultas para PDF
    fig_sun, ax_sun = plt.subplots(figsize=(5, 3))
    az = np.linspace(-90, 90, 100)
    ax_sun.plot(az, 70*np.cos(np.radians(az)), color='orange', label='Verano')
    ax_sun.fill_between(az, 0, 15, color='gray', alpha=0.3)
    ax_sun.set_title("Trayectoria Solar")
    ax_sun.grid(True)
    fig_sun.savefig("temp_sunpath.png", bbox_inches='tight')
    plt.close(fig_sun)

    fig_irr, ax_irr = plt.subplots(figsize=(5, 3))
    h = np.arange(6, 19)
    ax_irr.plot(h, np.sin(np.pi*(h-6)/12)*1000, color='#f1c40f')
    ax_irr.fill_between(h, np.sin(np.pi*(h-6)/12)*1000, alpha=0.2, color='#f1c40f')
    ax_irr.set_title("Curva Diaria")
    fig_irr.savefig("temp_curve.png", bbox_inches='tight')
    plt.close(fig_irr)

# TAB 3: FINANCIERO & REPORTE
with tabs[2]:
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        st.subheader("Costos del Proyecto")
        costo_paneles = st.session_state.n_paneles_real * dato_panel["Precio"]
        costo_inv = dato_inv["Precio"]
        costo_est = st.session_state.n_paneles_real * 150000 
        costo_elec = 800000 
        costo_mo = st.session_state.potencia_sistema_kw * 600000 
        costo_total = costo_paneles + costo_inv + costo_est + costo_elec + costo_mo
        
        st.write(f"**Inversión Total (CAPEX):** ${costo_total:,.0f} COP")
        
        tarifa = st.number_input("Tarifa Energía ($/kWh)", 850)
        ahorro = st.session_state.gen_total_mensual * tarifa
        roi = costo_total / (ahorro * 12) if ahorro > 0 else 0
        st.metric("Retorno de Inversión", f"{roi:.1f} Años")

    with c_f2:
        st.subheader("Flujo de Caja")
        flujo = [-costo_total]
        for _ in range(25): flujo.append(flujo[-1] + (ahorro*12*1.05))
        
        fig_roi, ax_roi = plt.subplots(figsize=(8, 4))
        ax_roi.plot(flujo, color='green', linewidth=2)
        ax_roi.axhline(0, color='black', linestyle='--')
        ax_roi.set_title("Retorno de Inversión (25 Años)")
        ax_roi.grid(True)
        st.pyplot(fig_roi)
        fig_roi.savefig("temp_roi.png", bbox_inches='tight')

    st.markdown("---")
    st.subheader("📄 Generación de Reporte")
    
    if st.button("Generar Reporte PDF (Completo)", use_container_width=True):
        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # PÁGINA 1
            pdf.add_page()
            pdf.set_fill_color(10, 40, 90); pdf.rect(0, 0, 210, 40, 'F')
            pdf.set_text_color(255); pdf.set_font('Arial','B',24); pdf.set_xy(10, 15); pdf.cell(0, 10, 'PROPUESTA TECNICA SIMU ING', 0, 1)
            pdf.set_text_color(0); pdf.ln(30)
            
            pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, "DATOS DEL PROYECTO", 0, 1)
            pdf.set_font('Arial', '', 11)
            datos = [("Cliente", limpiar(cliente)), ("Ubicacion", limpiar(ciudad)), ("Potencia", f"{st.session_state.potencia_sistema_kw:.2f} kWp")]
            for k,v in datos: pdf.cell(40, 8, k, 1); pdf.cell(0, 8, v, 1, 1)
            
            pdf.ln(10); pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, "ANALISIS SOLAR", 0, 1)
            y_img = pdf.get_y()
            if os.path.exists("temp_sunpath.png"): pdf.image("temp_sunpath.png", x=10, y=y_img, w=90)
            if os.path.exists("temp_curve.png"): pdf.image("temp_curve.png", x=105, y=y_img, w=90)

            # PÁGINA 2
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, "BALANCE ENERGETICO Y FINANCIERO", 0, 1)
            if os.path.exists("temp_bars.png"): pdf.image("temp_bars.png", x=10, y=30, w=190)
            if os.path.exists("temp_roi.png"): pdf.image("temp_roi.png", x=10, y=120, w=190)

            # PÁGINA 3 (UNIFILAR DETALLADO)
            pdf.add_page('L')
            pdf.rect(5, 5, 287, 200); pdf.rect(10, 10, 277, 190); pdf.line(10, 175, 287, 175)
            pdf.set_xy(15, 177); pdf.set_font('Arial','B',8); pdf.cell(20,5,"PROYECTO: " + limpiar(cliente))
            
            y_base = 80; xs = 30
            pdf.set_draw_color(0)
            for i in range(3):
                pdf.rect(xs+i*15, y_base, 12, 20); pdf.line(xs+i*15, y_base+10, xs+i*15+12, y_base+10)
            pdf.text(xs, y_base-5, "GENERADOR FV")
            
            pdf.set_draw_color(200,0,0); pdf.line(xs+36, y_base+5, 90, y_base+5); pdf.text(70, y_base+4, "DC+")
            pdf.set_draw_color(0); pdf.line(xs+36, y_base+15, 90, y_base+15); pdf.text(70, y_base+14, "DC-")
            
            pdf.rect(90, y_base-10, 30, 35); pdf.text(92, y_base-7, "CAJA DC")
            pdf.rect(95, y_base+4, 5, 2); pdf.rect(95, y_base+14, 5, 2)
            
            pdf.rect(140, y_base-5, 30, 30); pdf.text(142, y_base, "INVERSOR")
            pdf.line(120, y_base+5, 140, y_base+5); pdf.line(120, y_base+15, 140, y_base+15)
            pdf.set_draw_color(0,150,0); pdf.line(165, y_base+25, 165, y_base+30)
            
            pdf.set_draw_color(0); pdf.line(180, y_base+10, 200, y_base+10); pdf.line(180, y_base+15, 200, y_base+15)
            pdf.rect(200, y_base-5, 30, 30); pdf.text(202, y_base-2, "TAB AC")
            pdf.rect(205, y_base+8, 5, 10); pdf.line(230, y_base+10, 250, y_base+10); pdf.line(230, y_base+15, 250, y_base+15)
            
            pdf.rect(250, y_base, 20, 20)
            try:
                if hasattr(pdf, 'ellipse'): pdf.ellipse(254, y_base+5, 12, 12)
                else: pdf.circle(260, y_base+11, 6)
            except: pdf.text(257, y_base+15, "M")
            pdf.text(256, y_base+12, "kWh")
            
            pdf.line(270, y_base+10, 280, y_base+10); pdf.line(270, y_base+15, 280, y_base+15); pdf.text(275, y_base+8, "RED")
            
            pdf.set_draw_color(0,150,0); pdf.line(30, y_base+30, 250, y_base+30); dibujar_tierra(pdf, 140, y_base+30); pdf.text(142, y_base+34, "SPT")

            # PÁGINA 4
            pdf.add_page('P')
            pdf.set_font('Arial', 'B', 16); pdf.cell(0, 10, 'PRESUPUESTO DETALLADO', 0, 1, 'C'); pdf.ln(10)
            pdf.set_fill_color(200, 220, 255); pdf.set_font('Arial', 'B', 10)
            pdf.cell(100, 10, 'Item', 1, 0, 'C', True); pdf.cell(30, 10, 'Total', 1, 1, 'C', True)
            pdf.set_font('Arial', '', 10)
            
            items = [
                (f"Paneles {dato_panel['Referencia']}", costo_paneles),
                (f"Inversor {dato_inv['Referencia']}", costo_inv),
                ("Estructura", costo_est), ("Electrico", costo_elec), ("Mano Obra", costo_mo)
            ]
            for d, v in items:
                pdf.cell(100, 10, limpiar(d[:55]), 1); pdf.cell(30, 10, f"${v:,.0f}", 1, 1, 'R')
            pdf.set_font('Arial', 'B', 12); pdf.cell(100, 10, "TOTAL", 1, 0, 'R'); pdf.cell(30, 10, f"${costo_total:,.0f}", 1, 1, 'R')

            # Generar
            pdf_bytes = pdf.output(dest='S')
            if isinstance(pdf_bytes, str): pdf_bytes = pdf_bytes.encode('latin-1')
            st.download_button("📥 DESCARGAR REPORTE", pdf_bytes, f"SIMU_ING_{limpiar(cliente)}.pdf", "application/pdf")
            st.success("✅ Reporte generado")

        except Exception as e:
            st.error(f"Error PDF: {e}")
