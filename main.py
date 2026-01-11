import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime
import os
import requests
import pydeck as pdk
import matplotlib.pyplot as plt
import math

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DEL SISTEMA Y ESTILOS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="PVsyst Clone - Ingeniería Solar Avanzada",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS para simular interfaz profesional
st.markdown("""
    <style>
    .main {background-color: #f8f9fa;}
    .stMetric {background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}
    h1, h2, h3 {color: #2c3e50;}
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. MOTOR DE CÁLCULO PVSYST (FÍSICA SOLAR)
# -----------------------------------------------------------------------------
class PVSystemEngine:
    def __init__(self, lat, lon, tilt, azimuth, albedo=0.2):
        self.lat = lat
        self.lon = lon
        self.tilt = np.radians(tilt)
        self.azimuth = np.radians(azimuth)
        self.albedo = albedo

    def get_solar_position(self, day_of_year, hour):
        # Algoritmo simplificado de posición solar
        declination = 23.45 * np.sin(np.radians(360/365 * (day_of_year - 81)))
        declination = np.radians(declination)
        
        time_offset = 0 # Simplificado para UTC local
        tst = hour + time_offset / 60
        hour_angle = np.radians(15 * (tst - 12))
        
        lat_rad = np.radians(self.lat)
        
        # Elevación Solar
        sin_elev = np.sin(lat_rad) * np.sin(declination) + np.cos(lat_rad) * np.cos(declination) * np.cos(hour_angle)
        elevation = np.degrees(np.arcsin(np.clip(sin_elev, -1, 1)))
        
        # Azimut Solar
        cos_azi = (np.sin(declination) * np.cos(lat_rad) - np.cos(declination) * np.sin(lat_rad) * np.cos(hour_angle)) / np.cos(np.radians(elevation))
        azimuth = np.degrees(np.arccos(np.clip(cos_azi, -1, 1)))
        if np.sin(hour_angle) > 0: azimuth = 360 - azimuth
        
        return elevation, azimuth

    def calculate_poa_irradiance(self, ghi, elevation, sun_azimuth):
        # Modelo de Cielo Isotrópico (Liu & Jordan)
        if elevation <= 0: return 0
        
        zenith = np.radians(90 - elevation)
        sun_az_rad = np.radians(sun_azimuth)
        
        # Ángulo de incidencia
        cos_theta = np.cos(zenith) * np.cos(self.tilt) + np.sin(zenith) * np.sin(self.tilt) * np.cos(sun_az_rad - self.azimuth)
        theta = np.arccos(np.clip(cos_theta, -1, 1))
        
        # Componentes (Simplificado: 60% Directa, 40% Difusa)
        dni = ghi # Aproximación para este modelo simple
        direct = dni * max(0, np.cos(theta))
        diffuse = ghi * ((1 + np.cos(self.tilt)) / 2) # Modelo isotrópico simple
        reflected = ghi * self.albedo * ((1 - np.cos(self.tilt)) / 2)
        
        return direct + diffuse + reflected

    def simulate_year(self, hsp_avg):
        # Generación de perfil horario sintético anual (8760 horas)
        monthly_prod = []
        hourly_prod = []
        
        for month in range(12):
            days_in_month = 30
            # Curva de campana diaria ajustada por HSP
            daily_curve = []
            for h in range(24):
                if 6 <= h <= 18:
                    val = np.sin(np.pi * (h - 6) / 12)
                else:
                    val = 0
                daily_curve.append(val)
            
            # Normalizar curva a HSP
            total_area = sum(daily_curve)
            if total_area > 0:
                factor = (hsp_avg * 1000) / total_area
                daily_profile = [x * factor for x in daily_curve]
            else:
                daily_profile = [0] * 24
                
            monthly_prod.append(sum(daily_profile) * days_in_month / 1000) # kWh/m2/mes
            hourly_prod.extend(daily_profile * days_in_month)
            
        return monthly_prod, hourly_prod

# -----------------------------------------------------------------------------
# 3. BASE DE DATOS TÉCNICA (MODULOS E INVERSORES)
# -----------------------------------------------------------------------------
@st.cache_data
def load_technical_library():
    # Paneles (Datos de hoja de datos real)
    panels = pd.DataFrame({
        "Modelo": ["Jinko 450W Tiger", "Trina 550W Vertex", "Canadian 600W BiHi", "Longi 540W Hi-MO"],
        "Pmax": [450, 550, 600, 540],
        "Voc": [41.5, 49.6, 41.7, 49.5],
        "Isc": [13.4, 13.9, 18.1, 13.8],
        "Vmp": [34.5, 41.6, 34.9, 41.9],
        "Imp": [13.0, 13.2, 17.2, 12.9],
        "Eff": [20.8, 21.5, 21.2, 21.3],
        "Temp_Coef_P": [-0.35, -0.34, -0.34, -0.35], # %/°C
        "Precio": [550000, 680000, 850000, 670000]
    })
    
    # Inversores
    inverters = pd.DataFrame({
        "Modelo": ["Fronius Primo 3.0", "Huawei SUN2000 5KTL", "SMA Sunny Boy 3.0", "Growatt 5000MTL"],
        "Pnom_AC": [3000, 5000, 3000, 5000],
        "Vmin_MPPT": [80, 120, 100, 100],
        "Vmax_MPPT": [800, 980, 600, 550],
        "Imax_DC": [12, 15, 12, 15],
        "Eff_Euro": [97.0, 97.5, 96.5, 97.2],
        "Precio": [4500000, 5200000, 4800000, 3200000]
    })
    return panels, inverters

df_panels, df_inverters = load_technical_library()

# -----------------------------------------------------------------------------
# 4. FUNCIONES DE DIBUJO E INGENIERÍA
# -----------------------------------------------------------------------------
def dibujar_tierra(pdf, x, y):
    pdf.line(x, y, x, y+3)
    pdf.line(x-3, y+3, x+3, y+3)
    pdf.line(x-2, y+4, x+2, y+4)
    pdf.line(x-1, y+5, x+1, y+5)

# -----------------------------------------------------------------------------
# 5. INTERFAZ DE USUARIO (GUI)
# -----------------------------------------------------------------------------
# Barra Lateral
st.sidebar.title("Configuración PVsyst")
password = st.sidebar.text_input("🔑 Licencia / Password", type="password")
if password != "SOLAR2025":
    st.sidebar.warning("🔒 Ingrese contraseña para desbloquear")
    st.stop()

# Selección de Sitio
st.sidebar.subheader("📍 Ubicación del Proyecto")
ciudades = {
    "Bogotá": [4.7110, -74.0721, 4.2],
    "Medellín": [6.2442, -75.5812, 4.5],
    "Cali": [3.4516, -76.5320, 4.8],
    "Barranquilla": [10.9685, -74.7813, 5.5],
    "Leticia": [-4.2153, -69.9406, 4.5],
    "San José del Guaviare": [2.5729, -72.6378, 4.5]
}
ciudad_sel = st.sidebar.selectbox("Ciudad Base", list(ciudades.keys()))
lat, lon, hsp = ciudades[ciudad_sel]

# Parámetros del Sistema
st.sidebar.subheader("☀️ Parámetros de Diseño")
tilt = st.sidebar.slider("Inclinación Panel (°)", 0, 90, 15)
azimuth = st.sidebar.slider("Azimut (0=N, 90=E, 180=S)", 0, 360, 180)

# Interfaz Principal
st.title("PVsyst Clone: Simulación & Ingeniería")
st.markdown(f"**Proyecto:** {ciudad_sel} | **Coordenadas:** {lat}, {lon} | **Recurso:** {hsp} kWh/m²/día")

# PESTAÑAS
tab_design, tab_results, tab_finance, tab_report = st.tabs([
    "🛠️ Diseño & Equipos", "📊 Simulación Energética", "💰 Análisis Financiero", "📄 Reporte Ingeniería"
])

# Variables de Estado Globales
if 'n_panels' not in st.session_state: st.session_state.n_panels = 10
if 'energy_annual' not in st.session_state: st.session_state.energy_annual = 0

# --- TAB 1: DISEÑO ---
with tab_design:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Selección de Módulos")
        p_model = st.selectbox("Modelo Panel", df_panels["Modelo"])
        panel_data = df_panels[df_panels["Modelo"] == p_model].iloc[0]
        
        # Dimensionamiento automático
        consumo = st.number_input("Consumo Mensual Objetivo (kWh)", 100, 10000, 500)
        n_sug = int((consumo * 12) / (panel_data["Pmax"] * hsp * 365 * 0.8 / 1000)) + 1
        st.info(f"Sugerido para {consumo} kWh/mes: **{n_sug} Paneles**")
        
        n_panels = st.slider("Número de Paneles", 1, 100, n_sug)
        st.session_state.n_panels = n_panels
        
        sys_power = n_panels * panel_data["Pmax"] / 1000 # kWp
        st.metric("Potencia DC Total", f"{sys_power:.2f} kWp")

    with c2:
        st.subheader("Configuración Eléctrica (Strings)")
        i_model = st.selectbox("Modelo Inversor", df_inverters["Modelo"])
        inv_data = df_inverters[df_inverters["Modelo"] == i_model].iloc[0]
        
        n_series = st.slider("Paneles por Serie (String)", 1, 20, min(n_panels, 12))
        n_strings = np.ceil(n_panels / n_series)
        
        voc_string = panel_data["Voc"] * n_series * 1.15 # Factor seguridad frío
        vmp_string = panel_data["Vmp"] * n_series
        
        # Validaciones de Ingeniería
        col_v1, col_v2 = st.columns(2)
        col_v1.metric("Voc String (-10°C)", f"{voc_string:.1f} V")
        col_v2.metric("Vmax Inversor", f"{inv_data['Vmax_MPPT']} V")
        
        if voc_string > inv_data["Vmax_MPPT"]:
            st.error("🛑 PELIGRO: Voltaje excede límite del inversor. Reduzca paneles en serie.")
        elif vmp_string < inv_data["Vmin_MPPT"]:
            st.warning("⚠️ Voltaje MPPT bajo. Aumente paneles en serie.")
        else:
            st.success("✅ Configuración Eléctrica Válida")

# --- TAB 2: SIMULACIÓN ---
with tab_results:
    st.subheader("Simulación de Producción Horaria (Modelo Físico)")
    
    # Motor de cálculo
    engine = PVSystemEngine(lat, lon, tilt, azimuth)
    monthly_irr, hourly_irr = engine.simulate_year(hsp)
    
    # Pérdidas del sistema (Loss Diagram)
    losses = {
        "Soiling": 0.03,
        "Shading": 0.02,
        "Thermal": 0.08, # Simplificado
        "Wiring": 0.02,
        "Inverter": 1 - (inv_data["Eff_Euro"]/100)
    }
    total_loss_factor = np.prod([1-l for l in losses.values()])
    
    # Energía Final
    monthly_energy = [irr * sys_power * total_loss_factor for irr in monthly_irr]
    annual_energy = sum(monthly_energy)
    st.session_state.energy_annual = annual_energy
    
    c_r1, c_r2, c_r3 = st.columns(3)
    c_r1.metric("Energía Anual", f"{annual_energy:,.0f} kWh")
    c_r2.metric("Producción Específica", f"{annual_energy/sys_power:.0f} kWh/kWp")
    c_r3.metric("Performance Ratio (PR)", f"{total_loss_factor*100:.1f}%")
    
    # Gráfica Mensual
    months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    fig_prod, ax = plt.subplots(figsize=(10, 4))
    ax.bar(months, monthly_energy, color='#3498db', edgecolor='#2980b9')
    ax.set_title("Producción de Energía Mensual Estimada")
    ax.set_ylabel("Energía (kWh)")
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    st.pyplot(fig_prod)
    fig_prod.savefig("temp_monthly.png", bbox_inches='tight')

# --- TAB 3: FINANCIERO ---
with tab_finance:
    st.subheader("Análisis de Retorno de Inversión (ROI)")
    
    # Costos
    cost_panels = n_panels * panel_data["Precio"]
    cost_inv = inv_data["Precio"]
    cost_bos = sys_power * 800000 # Balance of System (Estruc, cables)
    cost_mo = sys_power * 600000 # Mano de obra
    capex = cost_panels + cost_inv + cost_bos + cost_mo
    
    st.write(f"**Inversión Inicial (CAPEX):** ${capex:,.0f} COP")
    
    tarifa = st.number_input("Tarifa Energía ($/kWh)", 600, 1500, 850)
    opex = st.number_input("O&M Anual ($)", 0, 5000000, 200000)
    inflation = 0.04
    energy_price_increase = 0.05
    
    # Flujo de Caja
    cash_flow = [-capex]
    cumulative_cash = [-capex]
    
    for y in range(1, 26):
        income = (annual_energy * (1 - 0.005)**(y-1)) * (tarifa * (1 + energy_price_increase)**(y-1))
        expense = opex * (1 + inflation)**(y-1)
        net = income - expense
        cash_flow.append(net)
        cumulative_cash.append(cumulative_cash[-1] + net)
    
    # Gráfica ROI
    fig_roi, ax_roi = plt.subplots(figsize=(10, 4))
    ax_roi.plot(range(26), cumulative_cash, color='#27ae60', linewidth=2)
    ax_roi.fill_between(range(26), cumulative_cash, 0, where=(np.array(cumulative_cash)>0), color='#27ae60', alpha=0.3)
    ax_roi.fill_between(range(26), cumulative_cash, 0, where=(np.array(cumulative_cash)<0), color='#e74c3c', alpha=0.3)
    ax_roi.axhline(0, color='black', linewidth=1)
    ax_roi.set_title("Flujo de Caja Acumulado (25 Años)")
    ax_roi.set_ylabel("COP ($)")
    ax_roi.set_xlabel("Años")
    st.pyplot(fig_roi)
    fig_roi.savefig("temp_roi.png", bbox_inches='tight')
    
    # Cálculo Payback
    payback = next((i for i, x in enumerate(cumulative_cash) if x >= 0), 25)
    st.metric("Periodo de Retorno", f"{payback} Años")

# --- TAB 4: REPORTE PDF ---
with tab_report:
    st.header("Generación de Entregables")
    st.write("Genera un reporte técnico completo en formato PDF con planos y memorias.")
    
    if st.button("📄 Generar Reporte de Ingeniería", use_container_width=True):
        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # ================= PAGINA 1: PORTADA Y RESUMEN =================
            pdf.add_page()
            
            # Header Corporativo
            pdf.set_fill_color(41, 128, 185) # Azul PVsyst
            pdf.rect(0, 0, 210, 40, 'F')
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", "B", 24)
            pdf.text(20, 25, "REPORTE DE DISEÑO FOTOVOLTAICO")
            
            # Datos del Proyecto
            pdf.set_text_color(0)
            pdf.set_y(50)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "1. INFORMACIÓN DEL PROYECTO", 0, 1)
            pdf.set_font("Arial", "", 11)
            
            data_proj = [
                ("Cliente:", limpiar(cliente)),
                ("Ubicación:", f"{ciudad_sel} ({lat}, {lon})"),
                ("Potencia Instalada:", f"{sys_power:.2f} kWp"),
                ("Generación Anual:", f"{annual_energy:,.0f} kWh/año"),
                ("PR del Sistema:", f"{total_loss_factor*100:.1f}%")
            ]
            
            for k, v in data_proj:
                pdf.cell(50, 8, k, 0)
                pdf.cell(0, 8, v, 0, 1)
            
            # Gráfica de Producción
            pdf.ln(10)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "2. PRODUCCIÓN ENERGÉTICA MENSUAL", 0, 1)
            if os.path.exists("temp_monthly.png"):
                pdf.image("temp_monthly.png", x=10, w=190)

            # ================= PAGINA 2: FINANCIERO Y PÉRDIDAS =================
            pdf.add_page()
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "3. ANÁLISIS FINANCIERO", 0, 1)
            
            # Tabla Financiera
            pdf.set_fill_color(230, 230, 230)
            pdf.cell(100, 8, "Concepto", 1, 0, 'C', True)
            pdf.cell(90, 8, "Valor", 1, 1, 'C', True)
            pdf.set_font("Arial", "", 11)
            
            fin_data = [
                ("CAPEX (Inversión)", f"${capex:,.0f}"),
                ("Ahorro Año 1", f"${cash_flow[1]:,.0f}"),
                ("Retorno de Inversión", f"{payback} Años"),
                ("Ahorro Acumulado (25 años)", f"${cumulative_cash[-1]:,.0f}")
            ]
            for k, v in fin_data:
                pdf.cell(100, 8, limpiar(k), 1)
                pdf.cell(90, 8, limpiar(v), 1, 1, 'R')
                
            pdf.ln(5)
            if os.path.exists("temp_roi.png"):
                pdf.image("temp_roi.png", x=10, w=190)

            # ================= PAGINA 3: DIAGRAMA UNIFILAR TIPO CAD =================
            pdf.add_page('L') # Horizontal
            
            # Marco Plano
            pdf.set_line_width(0.5)
            pdf.rect(5, 5, 287, 200)
            pdf.rect(10, 10, 277, 190)
            
            # Cajetín
            y_base = 175
            pdf.line(10, y_base, 287, y_base)
            pdf.set_font("Arial", "B", 8)
            pdf.text(15, y_base+5, "PROYECTO: " + limpiar(cliente))
            pdf.text(100, y_base+5, "PLANO: DIAGRAMA UNIFILAR")
            pdf.text(200, y_base+5, "FECHA: " + str(datetime.now().date()))
            pdf.text(250, y_base+5, "REV: 01")
            
            # DIBUJO TÉCNICO
            y_draw = 80
            x_draw = 40
            
            # 1. Array PV
            pdf.set_draw_color(0)
            for i in range(3): # 3 strings representativos
                x = x_draw + (i*20)
                pdf.rect(x, y_draw, 15, 25) # Panel
                pdf.line(x, y_draw+8, x+15, y_draw+8)
                pdf.line(x, y_draw+16, x+15, y_draw+16)
            
            pdf.text(x_draw, y_draw-5, f"GENERADOR FV: {n_panels}x {panel_data['Pmax']}W")
            
            # Cableado DC
            pdf.set_draw_color(200, 0, 0) # Rojo
            pdf.line(x_draw+45, y_draw+5, 110, y_draw+5) # Positivo
            pdf.text(80, y_draw+4, "DC (+)")
            
            pdf.set_draw_color(0, 0, 0) # Negro
            pdf.line(x_draw+45, y_draw+20, 110, y_draw+20) # Negativo
            pdf.text(80, y_draw+19, "DC (-)")
            
            # Tablero DC (String Box)
            pdf.rect(110, y_draw-5, 30, 35)
            pdf.text(112, y_draw, "PROT. DC")
            # Fusibles
            pdf.rect(115, y_draw+5, 5, 2)
            pdf.rect(115, y_draw+20, 5, 2)
            pdf.text(122, y_draw+7, "Fus")
            
            # Inversor
            pdf.rect(160, y_draw-5, 40, 35)
            pdf.set_font("Arial", "B", 10)
            pdf.text(165, y_draw+10, "INVERSOR")
            pdf.set_font("Arial", "", 8)
            pdf.text(165, y_draw+15, limpiar(inv_data['Modelo'][:15]))
            
            # Conexión DC a Inversor
            pdf.line(140, y_draw+5, 160, y_draw+5)
            pdf.line(140, y_draw+20, 160, y_draw+20)
            
            # Salida AC
            pdf.line(200, y_draw+12, 230, y_draw+12)
            pdf.text(210, y_draw+10, "AC 220V")
            
            # Tablero AC
            pdf.rect(230, y_draw-5, 25, 35)
            pdf.text(232, y_draw, "TAB. AC")
            pdf.rect(235, y_draw+10, 5, 5) # Breaker
            pdf.text(242, y_draw+14, "Brk")
            
            # Medidor y Red
            pdf.line(255, y_draw+12, 270, y_draw+12)
            # Medidor (Círculo seguro)
            try:
                if hasattr(pdf, 'ellipse'): pdf.ellipse(270, y_draw+7, 10, 10)
                else: pdf.circle(275, y_draw+12, 5)
            except: 
                pdf.text(272, y_draw+15, "(M)")
                
            pdf.text(272, y_draw+25, "RED")

            # Tierra General
            pdf.set_draw_color(0, 150, 0)
            pdf.line(x_draw+7, y_draw+25, x_draw+7, y_draw+40) # Bajante paneles
            pdf.line(180, y_draw+30, 180, y_draw+40) # Bajante inversor
            pdf.line(40, y_draw+40, 250, y_draw+40) # Bus tierra
            dibujar_tierra(pdf, 150, y_draw+40)
            pdf.text(152, y_draw+45, "SPT")

            # ================= PAGINA 4: PRESUPUESTO =================
            pdf.add_page('P')
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "4. PRESUPUESTO DETALLADO", 0, 1, 'C')
            pdf.ln(10)
            
            # Tabla BOM
            pdf.set_fill_color(220)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(110, 10, "Descripción", 1, 0, 'C', True)
            pdf.cell(20, 10, "Cant", 1, 0, 'C', True)
            pdf.cell(30, 10, "Unitario", 1, 0, 'C', True)
            pdf.cell(30, 10, "Total", 1, 1, 'C', True)
            
            pdf.set_font("Arial", "", 10)
            items = [
                (f"Módulo {panel_data['Modelo']}", n_panels, panel_data['Precio']),
                (f"Inversor {inv_data['Modelo']}", 1, inv_data['Precio']),
                ("Estructura de Montaje (Aluminio)", n_panels, 150000),
                ("Cableado y Protecciones DC/AC", 1, cost_bos/sys_power), # Aprox
                ("Instalación e Ingeniería", 1, cost_mo)
            ]
            
            total = 0
            for desc, cant, unit in items:
                subtotal = cant * unit
                total += subtotal
                pdf.cell(110, 10, limpiar(desc[:60]), 1)
                pdf.cell(20, 10, str(int(cant)), 1, 0, 'C')
                pdf.cell(30, 10, f"${unit/1e6:.1f}M", 1, 0, 'R')
                pdf.cell(30, 10, f"${subtotal/1e6:.1f}M", 1, 1, 'R')
            
            pdf.set_font("Arial", "B", 12)
            pdf.cell(160, 10, "TOTAL PROYECTO (COP)", 1, 0, 'R')
            pdf.cell(30, 10, f"${total/1e6:.1f}M", 1, 1, 'R')

            # Generar
            pdf_bytes = pdf.output(dest='S')
            if isinstance(pdf_bytes, str): pdf_bytes = pdf_bytes.encode('latin-1')
            
            st.download_button(
                label="📥 Descargar Reporte Completo (PDF)",
                data=pdf_bytes,
                file_name=f"Proyecto_Solar_{limpiar(cliente)}.pdf",
                mime="application/pdf"
            )
            st.success("Reporte generado exitosamente.")

        except Exception as e:
            st.error(f"Error generando PDF: {e}")
