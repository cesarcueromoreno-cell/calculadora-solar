import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
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

# Estilos CSS Profesionales
st.markdown("""
    <style>
    .main {background-color: #f4f6f8;}
    [data-testid="stSidebar"] {background-color: #2c3e50; color: white;}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {color: #ecf0f1 !important;}
    [data-testid="stSidebar"] label {color: #bdc3c7 !important; font-weight: bold;}
    h1, h2, h3 {color: #2980b9; font-family: 'Segoe UI', sans-serif;}
    div.css-1r6slb0 {border: 1px solid #dcdcdc; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 15px; border-radius: 5px; background-color: white;}
    .stButton > button {background-color: #2980b9; color: white; border-radius: 0px; border: 1px solid #1abc9c; width: 100%;}
    .stButton > button:hover {background-color: #1a5276;}
    </style>
""", unsafe_allow_html=True)

# Inicialización de variables
if 'n_paneles_real' not in st.session_state: st.session_state.n_paneles_real = 12
if 'gen_total_mensual' not in st.session_state: st.session_state.gen_total_mensual = 0.0
if 'potencia_sistema_kw' not in st.session_state: st.session_state.potencia_sistema_kw = 0.0

# ==============================================================================
# 2. FUNCIONES
# ==============================================================================
def limpiar(texto):
    if texto is None: return ""
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'ñ': 'n', 'Ñ': 'N', '°': 'deg'}
    s = str(texto)
    for k, v in replacements.items(): s = s.replace(k, v)
    return s.encode('latin-1', 'replace').decode('latin-1')

def simulacion_pvsyst(potencia_dc_kw, hsp_sitio, temp_amb_grados):
    perdida_temp = 0.004 * max(0, temp_amb_grados - 25)
    perdidas_sistema = 0.14
    eficiencia_global = 1 - (perdidas_sistema + perdida_temp)
    generacion_diaria = potencia_dc_kw * hsp_sitio * eficiencia_global
    return generacion_diaria, eficiencia_global

def dibujar_tierra_pdf(pdf, x, y):
    pdf.set_draw_color(0, 150, 0)
    pdf.line(x, y, x, y+2) 
    pdf.line(x-2, y+2, x+2, y+2) 
    pdf.line(x-1.2, y+2.8, x+1.2, y+2.8) 
    pdf.line(x-0.5, y+3.6, x+0.5, y+3.6) 
    pdf.set_draw_color(0)

# ==============================================================================
# 3. BASE DE DATOS
# ==============================================================================
def cargar_biblioteca():
    data_ciudades = {
        "San José del Guaviare": {"lat": 2.5729, "lon": -72.6378, "hsp": 4.6, "depto": "Guaviare"},
        "Bogotá D.C.": {"lat": 4.7110, "lon": -74.0721, "hsp": 4.2, "depto": "Cundinamarca"},
        "Medellín": {"lat": 6.2442, "lon": -75.5812, "hsp": 4.8, "depto": "Antioquia"},
        "Cali": {"lat": 3.4516, "lon": -76.5320, "hsp": 4.9, "depto": "Valle del Cauca"},
        "Barranquilla": {"lat": 10.9685, "lon": -74.7813, "hsp": 5.8, "depto": "Atlántico"},
        "Leticia": {"lat": -4.2153, "lon": -69.9406, "hsp": 4.5, "depto": "Amazonas"}
    }
    data_paneles = {
        "Referencia": ["Panel 450W Monocristalino", "Panel 550W Bifacial", "Panel 600W Industrial"],
        "Potencia": [450, 550, 600], "Voc": [41.5, 49.6, 41.7], "Precio": [550000, 720000, 850000]
    }
    data_inversores = {
        "Referencia": ["Microinversor 1.2kW", "Inversor 3kW", "Inversor 5kW Híbrido", "Inversor 10kW Trifásico"],
        "Potencia": [1200, 3000, 5000, 10000], "Vmin": [20, 80, 120, 180], "Vmax": [60, 600, 600, 1000], "Precio": [1200000, 2500000, 4500000, 7000000]
    }
    return data_ciudades, pd.DataFrame(data_paneles), pd.DataFrame(data_inversores)

db_ciudades, df_modulos, df_inversores = cargar_biblioteca()

# ==============================================================================
# 4. INTERFAZ
# ==============================================================================
st.sidebar.title("SIMU ING v5.0")
st.sidebar.subheader("1. Sitio y Meteo")
ciudad_sel = st.sidebar.selectbox("Ubicación", list(db_ciudades.keys()))
info_ciudad = db_ciudades[ciudad_sel]
st.sidebar.metric("HSP", f"{info_ciudad['hsp']}")
st.sidebar.subheader("2. Cliente")
cliente = st.sidebar.text_input("Nombre", "Cliente General")

st.title("SIMU ING - Entorno de Simulación")

# --- MAPA 3D SATELITAL ROBUSTO (NO FALLA) ---
st.markdown("### 🛰️ Visualización de Sitio (3D)")
# Usamos un TileLayer de Esri que es público y de alta resolución
layer_sat = pdk.Layer(
    "TileLayer",
    data=None,
    get_tile_data="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    opacity=1
)
view_state = pdk.ViewState(
    latitude=info_ciudad['lat'], 
    longitude=info_ciudad['lon'], 
    zoom=16, 
    pitch=50 # Inclinación para efecto 3D
)

st.pydeck_chart(pdk.Deck(
    map_style=None,
    initial_view_state=view_state,
    layers=[
        layer_sat,
        pdk.Layer(
            "IconLayer",
            data=pd.DataFrame([{"lat": info_ciudad['lat'], "lon": info_ciudad['lon']}]),
            get_position="[lon, lat]",
            get_icon={"url": "https://img.icons8.com/color/100/marker--v1.png", "width": 128, "height": 128, "anchorY": 128},
            get_size=4,
            size_scale=15
        )
    ],
    height=450
))

# TABS
tabs = st.tabs(["🏗️ Diseño", "📊 Simulación", "💰 Económico", "📄 Reporte PDF"])

with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        ref_panel = st.selectbox("Panel", df_modulos["Referencia"])
        dato_panel = df_modulos[df_modulos["Referencia"] == ref_panel].iloc[0]
        consumo = st.number_input("Consumo (kWh)", 100, 50000, 567)
        n_sug = int(consumo / (dato_panel["Potencia"]/1000 * info_ciudad['hsp'] * 30 * 0.8)) + 1
        n_paneles = st.number_input("Cantidad", 1, 500, n_sug)
        st.session_state.n_paneles_real = n_paneles
        st.session_state.potencia_sistema_kw = (n_paneles * dato_panel["Potencia"]) / 1000
        st.success(f"Potencia DC: {st.session_state.potencia_sistema_kw:.2f} kWp")
    with c2:
        ref_inv = st.selectbox("Inversor", df_inversores["Referencia"])
        dato_inv = df_inversores[df_inversores["Referencia"] == ref_inv].iloc[0]
        n_ser = st.slider("Serie", 1, 20, 11)
        voc = dato_panel["Voc"] * n_ser * 1.15
        if voc > dato_inv["Vmax"]: st.error("Voltaje Alto")
        else: st.success("Diseño OK")

with tabs[1]:
    gen_dia, pr = simulacion_pvsyst(st.session_state.potencia_sistema_kw, info_ciudad['hsp'], 28)
    st.session_state.gen_total_mensual = gen_dia * 30
    st.metric("Generación Mensual", f"{st.session_state.gen_total_mensual:.0f} kWh")
    
    # Gráficas PDF (Generación Oculta)
    fig_sun, ax = plt.subplots(figsize=(5,3))
    az = np.linspace(-90,90,100)
    ax.plot(az, 70*np.cos(np.radians(az)), color='orange'); ax.set_title("Trayectoria Solar")
    fig_sun.savefig("temp_sunpath.png", bbox_inches='tight'); plt.close(fig_sun)

    fig_day, ax = plt.subplots(figsize=(5,3))
    h = np.arange(6,19); ax.plot(h, np.sin(np.pi*(h-6)/12)*1000, color='orange'); ax.set_title("Curva Diaria")
    fig_day.savefig("temp_curve.png", bbox_inches='tight'); plt.close(fig_day)
    
    # Gráfica Visible
    meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    fig_bar, ax = plt.subplots(figsize=(10,4))
    ax.bar(np.arange(12)-0.17, [consumo]*12, 0.35, label='Consumo', color='#e74c3c')
    ax.bar(np.arange(12)+0.17, [st.session_state.gen_total_mensual]*12, 0.35, label='Solar', color='#2ecc71')
    ax.legend(); ax.set_title("Balance Energético")
    st.pyplot(fig_bar)
    fig_bar.savefig("temp_bars.png", bbox_inches='tight'); plt.close(fig_bar)

with tabs[2]:
    costo_tot = (n_paneles*dato_panel["Precio"]) + dato_inv["Precio"] + (n_paneles*150000) + 800000 + (st.session_state.potencia_sistema_kw*600000)
    st.metric("Inversión Total", f"${costo_tot:,.0f}")
    tarifa = st.number_input("Tarifa", 850)
    ahorro = st.session_state.gen_total_mensual * tarifa
    flujo = [-costo_tot]; 
    for _ in range(25): flujo.append(flujo[-1] + (ahorro*12*1.05))
    fig_roi, ax = plt.subplots(figsize=(10,4)); ax.plot(flujo, color='green'); ax.set_title("Flujo de Caja")
    st.pyplot(fig_roi)
    fig_roi.savefig("temp_roi.png", bbox_inches='tight'); plt.close(fig_roi)

with tabs[3]:
    if st.button("Generar Reporte PDF (SIMU ING)", use_container_width=True):
        try:
            pdf = FPDF(); pdf.set_auto_page_break(auto=True, margin=15)
            
            # P1: PORTADA
            pdf.add_page(); pdf.set_fill_color(10,40,90); pdf.rect(0,0,210,35,'F')
            pdf.set_text_color(255); pdf.set_font('Arial','B',22); pdf.set_xy(10,10); pdf.cell(0,10,'PROPUESTA TECNICA',0,1)
            pdf.set_font('Arial','',12); pdf.set_xy(10,20); pdf.cell(0,5,'SISTEMA FOTOVOLTAICO',0,1)
            pdf.set_text_color(0); pdf.ln(20)
            
            pdf.set_font('Arial','B',12); pdf.cell(0,8,"DATOS DEL PROYECTO",0,1,'L')
            pdf.set_font('Arial','',10)
            datos = [("Cliente", limpiar(cliente)), ("Ubicacion", limpiar(ciudad_sel)), ("Potencia", f"{st.session_state.potencia_sistema_kw:.2f} kWp")]
            for k,v in datos: pdf.cell(40,7,k,0); pdf.cell(0,7,v,0,1); pdf.line(10,pdf.get_y(),200,pdf.get_y())
            
            pdf.ln(10); pdf.set_font('Arial','B',12); pdf.cell(0,10,"ANALISIS SOLAR",0,1)
            y = pdf.get_y()
            if os.path.exists("temp_sunpath.png"): pdf.image("temp_sunpath.png",x=10,y=y,w=90)
            if os.path.exists("temp_curve.png"): pdf.image("temp_curve.png",x=105,y=y,w=90)

            # P2: FINANCIERO
            pdf.add_page(); pdf.set_font('Arial','B',14); pdf.cell(0,10,"ANALISIS FINANCIERO",0,1)
            if os.path.exists("temp_bars.png"): pdf.image("temp_bars.png",x=10,y=30,w=190)
            if os.path.exists("temp_roi.png"): pdf.image("temp_roi.png",x=10,y=120,w=190)

            # P3: UNIFILAR CAD (DETALLADO Y CORREGIDO)
            pdf.add_page('L'); pdf.rect(5,5,287,200); pdf.rect(10,10,277,190); pdf.line(10,175,287,175)
            pdf.set_font('Arial','B',8); pdf.set_xy(15,177); pdf.cell(20,5,"PROYECTO: "+limpiar(cliente))
            pdf.set_xy(150, 177); pdf.cell(20, 5, "PLANO: EL-01 UNIFILAR")
            
            # Dibujo
            y0=80; xs=30; pdf.set_draw_color(0)
            # Paneles
            for i in range(3):
                pdf.rect(xs+i*15,y0,12,20); pdf.line(xs+i*15,y0+6,xs+i*15+12,y0+6)
            pdf.text(xs,y0-5,"GENERADOR FV")
            # DC
            pdf.set_draw_color(200,0,0); pdf.line(xs+36,y0+2,90,y0+2); pdf.text(70,y0+1,"DC+")
            pdf.set_draw_color(0); pdf.line(xs+36,y0+18,90,y0+18); pdf.text(70,y0+17,"DC-")
            # Caja DC
            pdf.rect(90,y0-10,40,40); pdf.text(92,y0-7,"TAB DC")
            pdf.rect(95,y0,8,4); pdf.text(96,y0-1,"Fus")
            pdf.rect(110,y0+8,6,10); pdf.text(111,y0+7,"DPS"); pdf.line(113,y0+18,113,y0+35)
            # Inversor
            pdf.rect(150,y0-5,30,30); pdf.text(152,y0,"INVERSOR")
            pdf.line(130,y0+2,150,y0+2); pdf.line(130,y0+18,150,y0+18)
            # AC
            pdf.line(180,y0+10,200,y0+10); pdf.line(180,y0+15,200,y0+15)
            # Tablero AC
            pdf.rect(200,y0-5,30,30); pdf.text(202,y0-2,"TAB AC")
            pdf.rect(205,y0+8,5,10); pdf.text(205,y0+7,"Brk")
            pdf.line(230,y0+10,250,y0+10); pdf.line(230,y0+15,250,y0+15)
            # Medidor
            pdf.rect(250,y0,20,20); pdf.text(256,y0+12,"kWh")
            try:
                if hasattr(pdf, 'ellipse'): pdf.ellipse(254,y0+5,12,12)
                else: pdf.circle(260,y0+11,6)
            except: pdf.text(257,y0+15,"M")
            # Red
            pdf.line(270,y0+10,280,y0+10); pdf.line(270,y0+15,280,y0+15); pdf.text(275,y0+8,"RED")
            # Tierra
            pdf.set_draw_color(0,150,0); pdf.line(30,y0+35,270,y0+35); dibujar_tierra_pdf(pdf,150,y0+35); pdf.text(152,y0+40,"SPT")

            # P4: BOM
            pdf.add_page('P'); pdf.set_font('Arial','B',16); pdf.cell(0,10,'PRESUPUESTO',0,1,'C'); pdf.ln(10)
            pdf.set_fill_color(200,220,255); pdf.set_font('Arial','B',10)
            pdf.cell(100,10,'Item',1,0,'C',True); pdf.cell(30,10,'Total',1,1,'C',True)
            pdf.set_font('Arial','',10)
            items = [(f"Paneles", n_paneles*dato_panel['Precio']), (f"Inversor", dato_inv['Precio']), ("Estructura", n_paneles*150000), ("Electrico", 800000), ("MO", st.session_state.potencia_sistema_kw*600000)]
            for d,v in items: pdf.cell(100,10,limpiar(d),1); pdf.cell(30,10,f"${v:,.0f}",1,1,'R')
            pdf.set_font('Arial','B',12); pdf.cell(100,10,"TOTAL",1,0,'R'); pdf.cell(30,10,f"${costo_tot:,.0f}",1,1,'R')

            st.download_button("📥 DESCARGAR REPORTE", pdf.output(dest='S').encode('latin-1'), f"SIMU_ING_{limpiar(cliente)}.pdf", "application/pdf")
            st.success("✅ Reporte Generado")
        except Exception as e: st.error(f"Error PDF: {e}")
