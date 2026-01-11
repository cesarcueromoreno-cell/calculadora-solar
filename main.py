import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import requests
import pydeck as pdk
import matplotlib.pyplot as plt
import numpy as np

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="CESAR CM Solar Suite",
    page_icon="☀️",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. INICIALIZACIÓN DE VARIABLES
# -----------------------------------------------------------------------------
if 'n_paneles_real' not in st.session_state:
    st.session_state.n_paneles_real = 10
if 'gen_total_mensual' not in st.session_state:
    st.session_state.gen_total_mensual = 0.0
if 'potencia_sistema_kw' not in st.session_state:
    st.session_state.potencia_sistema_kw = 0.0

# -----------------------------------------------------------------------------
# 3. FUNCIONES AUXILIARES
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 4. BASE DE DATOS
# -----------------------------------------------------------------------------
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
        "Isc": [13.4, 13.9, 18.1],
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

# -----------------------------------------------------------------------------
# 5. SIDEBAR
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/solar-panel.png", width=80)
st.sidebar.title("Configuración")

password = st.sidebar.text_input("🔑 Contraseña", type="password")
if password != "SOLAR2025":
    st.sidebar.error("Acceso Bloqueado")
    st.stop()

st.sidebar.success("Sistema Activo")
st.sidebar.markdown("---")

tipo_sistema = st.sidebar.selectbox("Tipo de Sistema", ["On-Grid (Conectado a Red)", "Off-Grid (Autónomo)", "Bombeo Solar"])
ciudad_ref = st.sidebar.selectbox("Ciudad Mapa", list(coordenadas_ciudades.keys()))
lat_atlas = st.sidebar.number_input("Latitud", value=coordenadas_ciudades.get(ciudad_ref, [4.5, -74])[0], format="%.4f")
lon_atlas = st.sidebar.number_input("Longitud", value=coordenadas_ciudades.get(ciudad_ref, [4.5, -74])[1], format="%.4f")
tipo_mapa = st.sidebar.radio("Mapa:", ["Satélite Híbrido", "Satélite Puro", "Relieve"])

# -----------------------------------------------------------------------------
# 6. INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------
st.title("CESAR CM INGENIERÍA - SUITE SOLAR v3.0")
st.markdown("---")

col_cli1, col_cli2 = st.columns([2, 1])
with col_cli1: cliente = st.text_input("Cliente / Proyecto", "Cliente General")
with col_cli2: fecha_proy = st.date_input("Fecha", datetime.now())

st.header("📍 1. Ubicación y Recurso Solar")
c1, c2, c3 = st.columns(3)
with c1: depto = st.selectbox("Departamento", df_ciudades["Departamento"].unique())
with c2: 
    ciudades_filtradas = df_ciudades[df_ciudades["Departamento"] == depto]
    ciudad = st.selectbox("Ciudad", ciudades_filtradas["Ciudad"])
with c3:
    try: hsp = ciudades_filtradas[ciudades_filtradas["Ciudad"] == ciudad].iloc[0]["HSP"]
    except: hsp = 4.5
    st.metric("HSP (Horas Sol)", f"{hsp} kWh/m²")

coords_mapa = coordenadas_ciudades.get(ciudad, [lat_atlas, lon_atlas])
lat_map, lon_map = coords_mapa[0], coords_mapa[1]

# MAPA PYDECK
st.pydeck_chart(pdk.Deck(
    map_style=None,
    initial_view_state=pdk.ViewState(latitude=lat_map, longitude=lon_map, zoom=16, pitch=45),
    layers=[
        pdk.Layer("TileLayer", data=None, get_tile_data=f"https://mt1.google.com/vt/lyrs={'y' if 'Híb' in tipo_mapa else 's'}&x={{x}}&y={{y}}&z={{z}}", opacity=1),
        pdk.Layer("IconLayer", pd.DataFrame([{"lat": lat_map, "lon": lon_map, "icon": {"url": "https://img.icons8.com/color/100/marker--v1.png", "width": 128, "height": 128, "anchorY": 128}}]), get_icon="icon", get_size=4, size_scale=15, get_position="[lon, lat]")
    ]
))

# --- GRÁFICAS SOLARES EN INTERFAZ ---
with st.expander("☀️ Análisis de Trayectoria Solar e Irradiancia (Detallado)", expanded=True):
    col_sol1, col_sol2 = st.columns(2)
    
    with col_sol1:
        st.subheader("Trayectoria Solar (Carta Solar)")
        fig_sun, ax_sun = plt.subplots(figsize=(5, 3))
        azimuth = np.linspace(-90, 90, 100)
        elevation_winter = 45 * np.cos(np.radians(azimuth)) 
        elevation_summer = 70 * np.cos(np.radians(azimuth)) 
        ax_sun.plot(azimuth, elevation_summer, color='orange', label='Verano')
        ax_sun.plot(azimuth, elevation_winter, color='blue', label='Invierno')
        ax_sun.fill_between(azimuth, 0, 15, color='gray', alpha=0.3, label='Sombras')
        ax_sun.set_title("Trayectoria Solar")
        ax_sun.set_xlabel("Azimut")
        ax_sun.set_ylabel("Elevación")
        ax_sun.grid(True, linestyle='--')
        st.pyplot(fig_sun)

    with col_sol2:
        st.subheader("Curva de Potencia Diaria")
        horas = np.arange(6, 19)
        irradiancia = np.sin(np.pi * (horas - 6) / 12) * 1000 
        fig_irr, ax_irr = plt.subplots(figsize=(5, 3))
        ax_irr.plot(horas, irradiancia, color='#f1c40f', linewidth=2)
        ax_irr.fill_between(horas, irradiancia, color='#f1c40f', alpha=0.2)
        ax_irr.set_title("Curva de Generación Diaria")
        ax_irr.grid(True, alpha=0.3)
        st.pyplot(fig_irr)

st.header("⚙️ 2. Selección de Equipos")
ce1, ce2 = st.columns(2)
with ce1: 
    ref_panel = st.selectbox("Panel Solar", df_modulos["Referencia"])
    dato_panel = df_modulos[df_modulos["Referencia"] == ref_panel].iloc[0]
with ce2: 
    ref_inv = st.selectbox("Inversor", df_inversores["Referencia"])
    dato_inv = df_inversores[df_inversores["Referencia"] == ref_inv].iloc[0]

# -----------------------------------------------------------------------------
# 7. CÁLCULOS
# -----------------------------------------------------------------------------
st.markdown("---")
tab1, tab2, tab3 = st.tabs(["📐 Dimensionamiento", "⚡ Eléctrico", "💰 Presupuesto & PDF"])

with tab1:
    col_dim1, col_dim2 = st.columns(2)
    consumo = col_dim1.number_input("Consumo (kWh/mes)", value=500)
    temp = col_dim2.number_input("Temperatura (°C)", value=28.0)

    if consumo > 0:
        gen_panel_simple = (dato_panel["Potencia"] / 1000) * hsp * 30 * 0.80
        n_sug = int(consumo / gen_panel_simple) + 1
        st.info(f"Sugerido: {n_sug} paneles")
        
        val_slider = st.slider("Cantidad Real de Paneles", 1, 100, n_sug)
        st.session_state.n_paneles_real = val_slider
        
        st.session_state.potencia_sistema_kw = (st.session_state.n_paneles_real * dato_panel["Potencia"]) / 1000
        gen_dia, ef = simulacion_pvsyst(st.session_state.potencia_sistema_kw, hsp, temp)
        st.session_state.gen_total_mensual = gen_dia * 30
        
        c1, c2 = st.columns(2)
        c1.metric("Potencia DC", f"{st.session_state.potencia_sistema_kw*1000:.0f} Wp")
        c2.metric("Generación", f"{st.session_state.gen_total_mensual:.0f} kWh/mes")
        
        # Gráfica en Interfaz
        df_graf = pd.DataFrame({"Mes": range(1,13), "Consumo": [consumo]*12, "Solar": [st.session_state.gen_total_mensual]*12})
        st.bar_chart(df_graf.set_index("Mes"), color=["#FF4B4B", "#00CC96"])

with tab2:
    n_pan = st.session_state.n_paneles_real
    if n_pan > 0:
        n_ser = st.slider("Paneles por Serie", 1, 20, min(n_pan, 15))
        voc = dato_panel["Voc"] * n_ser
        ce1, ce2 = st.columns(2)
        ce1.metric("Voc String", f"{voc:.1f} V")
        if voc > dato_inv["Vmax"]: ce2.error(f"🛑 > {dato_inv['Vmax']}V")
        else: 
            ce2.success("✅ Voltaje Seguro")
            st.progress(voc / dato_inv["Vmax"])

with tab3:
    st.subheader("Presupuesto Estimado y Reporte")
    
    # Costos
    costo_paneles = st.session_state.n_paneles_real * dato_panel["Precio"]
    costo_inversor = dato_inv["Precio"]
    costo_estructura = st.session_state.n_paneles_real * 150000 
    costo_elec = 800000 
    costo_mo = st.session_state.potencia_sistema_kw * 600000 
    costo_total = costo_paneles + costo_inversor + costo_estructura + costo_elec + costo_mo
    
    df_costos = pd.DataFrame({
        "Item": ["Paneles", "Inversor", "Estructura", "Eléctrico", "Mano Obra"],
        "Valor": [costo_paneles, costo_inversor, costo_estructura, costo_elec, costo_mo]
    })
    st.dataframe(df_costos, use_container_width=True)
    st.metric("Inversión Total Estimada", f"${costo_total:,.0f} COP")
    
    # ROI
    tarifa = st.number_input("Tarifa ($/kWh)", value=850)
    ahorro = st.session_state.gen_total_mensual * tarifa
    if ahorro > 0:
        roi = costo_total / (ahorro * 12)
        st.metric("Retorno Inversión", f"{roi:.1f} Años")
        
    flujo = [-costo_total]
    for _ in range(25): flujo.append(flujo[-1] + (ahorro*12*1.05))
    
    if st.button("Generar PDF Profesional", use_container_width=True):
        try:
            # 1. GENERAR IMÁGENES TEMPORALES (TODAS)
            
            # A. Trayectoria Solar
            fig_sun, ax_sun = plt.subplots(figsize=(5, 3))
            azimuth = np.linspace(-90, 90, 100)
            elevation_winter = 45 * np.cos(np.radians(azimuth)) 
            elevation_summer = 70 * np.cos(np.radians(azimuth)) 
            ax_sun.plot(azimuth, elevation_summer, color='orange', label='Verano')
            ax_sun.plot(azimuth, elevation_winter, color='blue', label='Invierno')
            ax_sun.fill_between(azimuth, 0, 15, color='gray', alpha=0.3, label='Sombras')
            ax_sun.set_title("Trayectoria Solar")
            ax_sun.set_xlabel("Azimut")
            ax_sun.set_ylabel("Elevación")
            ax_sun.grid(True, linestyle='--')
            fig_sun.savefig("temp_sunpath.png", bbox_inches='tight')
            plt.close(fig_sun)

            # B. Curva Diaria
            horas = np.arange(6, 19)
            irradiancia = np.sin(np.pi * (horas - 6) / 12) * 1000 
            fig_irr, ax_irr = plt.subplots(figsize=(5, 3))
            ax_irr.plot(horas, irradiancia, color='#f1c40f', linewidth=2)
            ax_irr.fill_between(horas, irradiancia, color='#f1c40f', alpha=0.2)
            ax_irr.set_title("Curva de Generación Diaria")
            ax_irr.grid(True, alpha=0.3)
            fig_irr.savefig("temp_curve.png", bbox_inches='tight')
            plt.close(fig_irr)

            # C. Gráfica de Barras Mensuales (Solar vs Red)
            meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            consumo_mensual = [consumo] * 12
            gen_solar = [st.session_state.gen_total_mensual] * 12
            x = np.arange(len(meses_nombres))
            width = 0.35
            fig_bar, ax_bar = plt.subplots(figsize=(10, 4))
            rects1 = ax_bar.bar(x - width/2, consumo_mensual, width, label='Consumo Red', color='#FF4B4B')
            rects2 = ax_bar.bar(x + width/2, gen_solar, width, label='Generación Solar', color='#00CC96')
            ax_bar.set_ylabel('Energía (kWh)')
            ax_bar.set_title('Balance Energético Mensual: Generación vs Consumo')
            ax_bar.set_xticks(x)
            ax_bar.set_xticklabels(meses_nombres)
            ax_bar.legend()
            ax_bar.grid(axis='y', linestyle='--', alpha=0.3)
            fig_bar.savefig("temp_bars.png", bbox_inches='tight')
            plt.close(fig_bar)

            # D. Gráfica ROI
            fig_roi, ax_roi = plt.subplots(figsize=(10, 4))
            ax_roi.plot(flujo, color='green', linewidth=2)
            ax_roi.set_title("Flujo de Caja Acumulado (25 Años)")
            ax_roi.set_ylabel("Rentabilidad ($)")
            ax_roi.grid(True, linestyle='--', alpha=0.5)
            fig_roi.savefig("temp_roi.png", bbox_inches='tight')
            plt.close(fig_roi)

            # --- INICIO PDF ---
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # --- PÁGINA 1: PORTADA ---
            pdf.add_page()
            # Franja Azul
            pdf.set_fill_color(10, 40, 90)
            pdf.rect(0, 0, 210, 40, 'F')
            if os.path.exists("logo.png"): 
                try: pdf.image("logo.png", x=10, y=5, w=50)
                except: pass
            
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 24)
            pdf.set_xy(70, 15); pdf.cell(0, 10, 'PROPUESTA TECNICA', 0, 1)
            pdf.set_font('Arial', '', 12)
            pdf.set_xy(70, 25); pdf.cell(0, 10, 'SISTEMA FOTOVOLTAICO', 0, 1)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(30)
            
            # Resumen
            pdf.set_font('Arial', 'B', 12)
            pdf.set_fill_color(230, 230, 230)
            pdf.cell(0, 10, "  DATOS DEL PROYECTO", 0, 1, 'L', True)
            pdf.ln(2)
            pdf.set_font('Arial', '', 11)
            datos = [("Cliente:", limpiar(cliente)), ("Ubicacion:", limpiar(ciudad)), ("Potencia:", f"{st.session_state.potencia_sistema_kw:.2f} kWp")]
            for t, v in datos:
                pdf.set_font('Arial','B',11); pdf.cell(40,8,t,0,0)
                pdf.set_font('Arial','',11); pdf.cell(0,8,v,0,1)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
            pdf.ln(5)
            # Imágenes Solares
            pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, "ANALISIS DE RECURSO SOLAR", 0, 1)
            y_i = pdf.get_y()
            if os.path.exists("temp_sunpath.png"): pdf.image("temp_sunpath.png", x=10, y=y_i, w=90)
            if os.path.exists("temp_curve.png"): pdf.image("temp_curve.png", x=105, y=y_i, w=90)
            
            # --- PÁGINA 2: GENERACIÓN Y FINANZAS ---
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, 'ANALISIS DE GENERACION Y RETORNO', 0, 1)
            
            # 1. Gráfica Barras
            if os.path.exists("temp_bars.png"): 
                pdf.image("temp_bars.png", x=10, y=30, w=190)
            
            # 2. Gráfica ROI
            if os.path.exists("temp_roi.png"): 
                pdf.image("temp_roi.png", x=10, y=120, w=190)

            # --- PÁGINA 3: DIAGRAMA UNIFILAR (CAD - RESTAURADO) ---
            pdf.add_page('L')
            # Marco
            pdf.set_line_width(0.5); pdf.rect(5, 5, 287, 200); pdf.rect(10, 10, 277, 190)
            pdf.line(10, 175, 287, 175) # Cajetín
            
            # Datos Cajetín
            pdf.set_font('Arial','B',8)
            pdf.set_xy(15, 177); pdf.cell(20,5,"PROYECTO:"); pdf.set_xy(15,182); pdf.set_font('Arial','',8); pdf.cell(20,5,limpiar(cliente))
            pdf.set_xy(80, 177); pdf.set_font('Arial','B',8); pdf.cell(20,5,"UBICACION:"); pdf.set_xy(80,182); pdf.set_font('Arial','',8); pdf.cell(20,5,limpiar(ciudad))
            pdf.set_xy(220, 177); pdf.set_font('Arial','B',8); pdf.cell(20,5,"PLANO:"); pdf.set_xy(220,182); pdf.set_font('Arial','',8); pdf.cell(20,5,"EL-01")

            # DIBUJO DETALLADO (EL QUE TE GUSTÓ)
            yb = 80; xs = 30
            # Paneles
            pdf.set_draw_color(0); pdf.set_line_width(0.3)
            for i in range(3):
                pdf.rect(xs+i*15, yb, 12, 20); pdf.line(xs+i*15, yb+6, xs+i*15+12, yb+6); pdf.line(xs+i*15, yb+13, xs+i*15+12, yb+13)
            pdf.set_font('Arial','B',8); pdf.text(xs, yb-5, "GENERADOR FV")
            pdf.set_font('Arial','',7); pdf.text(xs, yb-2, f"{st.session_state.n_paneles_real} x {dato_panel['Potencia']}W")
            # DC
            pdf.set_draw_color(200,0,0); pdf.line(xs+36, yb+2, 90, yb+2); pdf.text(70, yb+1, "DC+")
            pdf.set_draw_color(0); pdf.line(xs+36, yb+18, 90, yb+18); pdf.text(70, yb+17, "DC-")
            pdf.set_draw_color(0,150,0); pdf.line(xs+6, yb+20, xs+6, yb+30); pdf.line(xs+6, yb+30, 250, yb+30); pdf.text(xs+7, yb+28, "T")
            # Caja
            pdf.set_draw_color(0); pdf.rect(90, yb-10, 40, 40); pdf.set_font('Arial','B',7); pdf.text(92, yb-7, "TABLERO DC")
            pdf.rect(95, yb, 8, 4); pdf.rect(95, yb+16, 8, 4); pdf.text(96, yb-1, "Fus")
            pdf.rect(110, yb+8, 6, 10); pdf.text(111, yb+7, "DPS"); pdf.line(113, yb+18, 113, yb+30)
            pdf.set_draw_color(200,0,0); pdf.line(130, yb+2, 150, yb+2)
            pdf.set_draw_color(0); pdf.line(130, yb+18, 150, yb+18)
            # Inversor
            pdf.rect(150, yb-5, 30, 30); pdf.set_font('Arial','B',8); pdf.text(152, yb, "INVERSOR"); pdf.set_font('Arial','',6); pdf.text(152, yb+5, f"{dato_inv['Potencia']}W")
            pdf.set_draw_color(0,150,0); pdf.line(165, yb+25, 165, yb+30)
            # AC
            pdf.set_draw_color(0); pdf.line(180, yb+10, 200, yb+10); pdf.line(180, yb+15, 200, yb+15); pdf.text(185, yb+9, "L"); pdf.text(185, yb+14, "N")
            # Tablero AC
            pdf.rect(200, yb-5, 30, 30); pdf.set_font('Arial','B',7); pdf.text(202, yb-2, "TABLERO AC")
            pdf.rect(205, yb+8, 5, 10); pdf.line(205, yb+13, 210, yb+8); pdf.text(205, yb+7, "Brk")
            pdf.line(230, yb+10, 250, yb+10); pdf.line(230, yb+15, 250, yb+15)
            # Medidor
            pdf.rect(250, yb, 20, 20)
            try:
                if hasattr(pdf, 'ellipse'): pdf.ellipse(254, yb+5, 12, 12)
                else: pdf.circle(260, yb+11, 6)
            except: 
                pdf.set_font('Arial','B',14); pdf.text(257, yb+15, "(M)")
            pdf.set_font('Arial', 'B', 10); pdf.text(256, yb+12, "kWh")
            # Red
            pdf.line(270, yb+10, 280, yb+10); pdf.line(270, yb+15, 280, yb+15); pdf.text(275, yb+8, "RED")
            # Tierra Gen
            pdf.set_draw_color(0,150,0); pdf.line(30, yb+30, 270, yb+30); dibujar_tierra(pdf, 150, yb+30); pdf.set_font('Arial','B',6); pdf.text(152, yb+34, "SPT")

            # --- PÁGINA 4: BOM ---
            pdf.add_page('P')
            pdf.set_font('Arial', 'B', 16); pdf.cell(0, 10, 'PRESUPUESTO', 0, 1, 'C'); pdf.ln(10)
            pdf.set_fill_color(200, 220, 255); pdf.set_font('Arial', 'B', 10)
            pdf.cell(100, 10, 'Item', 1, 0, 'C', True); pdf.cell(20, 10, 'Cant', 1, 0, 'C', True); pdf.cell(35, 10, 'Unit', 1, 0, 'C', True); pdf.cell(35, 10, 'Total', 1, 1, 'C', True)
            pdf.set_font('Arial', '', 10)
            total_pres = 0
            for desc, cant, unit in items_bom:
                tot = cant * unit
                total_pres += tot
                pdf.cell(100, 10, limpiar(desc[:50]), 1); pdf.cell(20, 10, str(int(cant)), 1, 0, 'C'); pdf.cell(35, 10, f"${unit:,.0f}", 1, 0, 'R'); pdf.cell(35, 10, f"${tot:,.0f}", 1, 1, 'R')
            pdf.set_font('Arial', 'B', 12); pdf.cell(155, 10, "TOTAL", 1, 0, 'R'); pdf.cell(35, 10, f"${total_pres:,.0f}", 1, 1, 'R')

            # DOWNLOAD
            pdf_content = pdf.output(dest='S')
            if isinstance(pdf_content, str): pdf_bytes = pdf_content.encode('latin-1')
            else: pdf_bytes = pdf_content
            st.download_button("📥 DESCARGAR REPORTE FINAL", pdf_bytes, f"Reporte_{limpiar(cliente)}.pdf", "application/pdf")
            st.success("✅ Reporte Completo Generado")

        except Exception as e:
            st.error(f"Error PDF: {e}")
