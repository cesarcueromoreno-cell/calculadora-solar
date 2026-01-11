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

# ==============================================================================
# 1. CONFIGURACIÓN DEL ENTORNO SIMU ING (Estilo PVsyst)
# ==============================================================================
st.set_page_config(
    page_title="SIMU ING - Ingeniería Fotovoltaica Avanzada",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS para simular software de ingeniería de escritorio
st.markdown("""
    <style>
    /* Fondo general gris técnico claro */
    .stApp {
        background-color: #f4f6f9;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    /* Barra lateral estilo oscuro profesional */
    [data-testid="stSidebar"] {
        background-color: #2c3e50;
        color: #ecf0f1;
    }
    [data-testid="stSidebar"] .css-17lntkn {
        color: #ecf0f1;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
        border-bottom: 1px solid #34495e;
        padding-bottom: 10px;
    }
    /* Inputs en la barra lateral */
    [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stNumberInput label, [data-testid="stSidebar"] .stSlider label {
        color: #bdc3c7 !important;
    }
    /* Contenedores principales (Tarjetas blancas) */
    div.css-1r6slb0 {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #dcdcdc;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    /* Títulos de secciones principales */
    h1, h2, h3 {
        color: #2980b9;
        font-weight: 600;
    }
    h1 { font-size: 2.2rem; }
    h2 { font-size: 1.6rem; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 20px;}
    h3 { font-size: 1.2rem; color: #34495e; }
    
    /* Métricas destacadas (KPIs) */
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
        color: #2c3e50;
        font-weight: bold;
    }
    [data-testid="stMetricLabel"] {
        color: #7f8c8d;
        font-size: 0.9rem;
    }
    
    /* Botones de acción */
    div.stButton > button {
        background-color: #2980b9;
        color: white;
        border-radius: 4px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #1a5276;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    
    /* Tablas de datos */
    .dataframe {
        font-size: 0.9rem;
        border: 1px solid #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)

# Inicialización de variables de estado (Persistencia)
if 'n_paneles_real' not in st.session_state: st.session_state.n_paneles_real = 12
if 'gen_total_mensual' not in st.session_state: st.session_state.gen_total_mensual = 0.0
if 'potencia_sistema_kw' not in st.session_state: st.session_state.potencia_sistema_kw = 0.0
if 'simulacion_ejecutada' not in st.session_state: st.session_state.simulacion_ejecutada = False

# ==============================================================================
# 2. MOTOR DE CÁLCULO E INGENIERÍA (KERNEL)
# ==============================================================================

class SolarEngineeringEngine:
    """Motor de cálculo físico para sistemas fotovoltaicos."""
    
    def __init__(self):
        pass

    def calcular_posicion_solar(self, latitud, dia_ano, hora):
        # Algoritmo simplificado de posición solar
        declinacion = 23.45 * np.sin(np.radians(360/365 * (dia_ano - 81)))
        hora_angular = 15 * (hora - 12)
        elevacion = np.degrees(np.arcsin(np.sin(np.radians(latitud)) * np.sin(np.radians(declinacion)) + 
                                         np.cos(np.radians(latitud)) * np.cos(np.radians(declinacion)) * np.cos(np.radians(hora_angular))))
        # Azimut simplificado (Sur = 0)
        azimut = np.degrees(np.arctan2(np.sin(np.radians(hora_angular)), 
                                       (np.cos(np.radians(hora_angular)) * np.sin(np.radians(latitud)) - 
                                        np.tan(np.radians(declinacion)) * np.cos(np.radians(latitud)))))
        return elevacion, azimut

    def simulacion_energetica(self, potencia_dc_kw, hsp_sitio, temp_amb_grados, perdidas_totales_pct):
        """Simula la producción de energía mensual."""
        # Modelo de eficiencia térmica
        # Coeficiente de temperatura típico: -0.4%/°C
        perdida_temp = 0.004 * max(0, (temp_amb_grados + (hsp_sitio/24 * 1000 / 800) * (45-20) - 25))
        
        # Eficiencia global del sistema (PR)
        pr_estimado = 1 - (perdidas_totales_pct/100) - perdida_temp
        
        # Generación Diaria Promedio
        generacion_diaria = potencia_dc_kw * hsp_sitio * pr_estimado
        
        return generacion_diaria, pr_estimado

def limpiar_texto(texto):
    """Limpia caracteres especiales para compatibilidad con PDF (Latin-1)"""
    if texto is None: return ""
    # Mapeo manual de caracteres problemáticos comunes
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', '°': 'deg'
    }
    s = str(texto)
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode('latin-1', 'replace').decode('latin-1')

def dibujar_tierra_pdf(pdf, x, y):
    """Dibuja el símbolo técnico de tierra en el PDF"""
    pdf.set_draw_color(0, 150, 0) # Verde tierra
    pdf.set_line_width(0.4)
    pdf.line(x, y, x, y+3)        # Bajante vertical
    pdf.line(x-3, y+3, x+3, y+3)  # Línea horizontal superior (larga)
    pdf.line(x-2, y+4, x+2, y+4)  # Línea horizontal media
    pdf.line(x-1, y+5, x+1, y+5)  # Línea horizontal inferior (corta)
    pdf.set_draw_color(0, 0, 0)   # Reset a negro

# ==============================================================================
# 3. BASE DE DATOS DE COMPONENTES E UBICACIONES
# ==============================================================================
def cargar_bases_datos():
    # Base de Datos Geográfica (Colombia)
    ciudades = {
        "Bogotá D.C.": {"lat": 4.7110, "lon": -74.0721, "hsp": 4.2, "depto": "Cundinamarca", "alt": 2600},
        "Medellín": {"lat": 6.2442, "lon": -75.5812, "hsp": 4.8, "depto": "Antioquia", "alt": 1495},
        "Cali": {"lat": 3.4516, "lon": -76.5320, "hsp": 4.9, "depto": "Valle del Cauca", "alt": 1018},
        "Barranquilla": {"lat": 10.9685, "lon": -74.7813, "hsp": 5.8, "depto": "Atlántico", "alt": 18},
        "Cartagena": {"lat": 10.3910, "lon": -75.4794, "hsp": 5.6, "depto": "Bolívar", "alt": 2},
        "Bucaramanga": {"lat": 7.1193, "lon": -73.1227, "hsp": 5.0, "depto": "Santander", "alt": 959},
        "San José del Guaviare": {"lat": 2.5729, "lon": -72.6378, "hsp": 4.6, "depto": "Guaviare", "alt": 185},
        "Leticia": {"lat": -4.2153, "lon": -69.9406, "hsp": 4.5, "depto": "Amazonas", "alt": 96},
        "Villavicencio": {"lat": 4.1420, "lon": -73.6266, "hsp": 4.7, "depto": "Meta", "alt": 467},
        "Santa Marta": {"lat": 11.2408, "lon": -74.1990, "hsp": 6.0, "depto": "Magdalena", "alt": 6}
    }
    
    # Base de Datos Técnica: Módulos FV
    modulos = pd.DataFrame({
        "Modelo": ["Jinko Tiger Pro 540W", "Trina Vertex S 500W", "Canadian Solar 600W BiHi", "Longi Hi-MO 5 550W", "JA Solar 460W Mono"],
        "Pmax": [540, 500, 600, 550, 460], # Wp
        "Voc": [49.5, 42.8, 41.7, 49.6, 41.8], # V
        "Isc": [13.85, 12.15, 18.1, 13.9, 11.2], # A
        "Vmp": [41.6, 36.2, 34.9, 41.9, 34.8], # V
        "Imp": [12.99, 13.81, 17.2, 13.12, 13.22], # A
        "Precio": [670000, 620000, 850000, 690000, 580000] # COP Estimado
    })
    
    # Base de Datos Técnica: Inversores
    inversores = pd.DataFrame({
        "Modelo": ["Fronius Primo 3.0-1", "Fronius Primo 5.0-1", "Fronius Symo 10.0-3", "Huawei SUN2000-3KTL", "Huawei SUN2000-5KTL", "Huawei SUN2000-10KTL", "SMA Sunny Boy 3.0", "SMA Sunny Boy 5.0"],
        "Pnom": [3000, 5000, 10000, 3000, 5000, 10000, 3000, 5000], # W
        "Vmin": [80, 80, 200, 100, 100, 200, 100, 100], # V
        "Vmax": [1000, 1000, 1000, 1100, 1100, 1100, 600, 600], # V
        "Fases": [1, 1, 3, 1, 1, 3, 1, 1],
        "Precio": [4500000, 5800000, 8900000, 3800000, 4900000, 7500000, 4200000, 5500000] # COP Estimado
    })
    
    return ciudades, modulos, inversores

db_ciudades, df_modulos, df_inversores = cargar_bases_datos()

# ==============================================================================
# 4. INTERFAZ DE USUARIO (GUI TIPO PVSYST)
# ==============================================================================

# --- BARRA LATERAL (PANEL DE PROYECTO) ---
st.sidebar.title("SIMU ING v2026")
st.sidebar.caption("Software de Ingeniería y Simulación Solar")

# Sección 1: Licencia y Acceso
with st.sidebar.expander("🔐 Licencia & Acceso", expanded=True):
    password = st.text_input("Clave de Activación", type="password")
    if password != "SOLAR2025":
        st.error("🔒 Sistema Bloqueado")
        st.info("Ingrese la clave para habilitar las funciones de ingeniería.")
        st.stop()
    st.success("✅ Licencia Profesional Activa")

st.sidebar.markdown("---")

# Sección 2: Definición del Sitio
st.sidebar.subheader("🌍 1. Sitio y Meteo")
ciudad_sel = st.sidebar.selectbox("Base de Datos Meteo", list(db_ciudades.keys()), index=6) # Default San José
info_ciudad = db_ciudades[ciudad_sel]

# Mostrar datos meteo en sidebar (estilo panel de control)
col_met1, col_met2 = st.sidebar.columns(2)
col_met1.metric("Latitud", f"{info_ciudad['lat']}°")
col_met1.metric("HSP (kWh/m²)", f"{info_ciudad['hsp']}")
col_met2.metric("Longitud", f"{info_ciudad['lon']}°")
col_met2.metric("Altitud", f"{info_ciudad['alt']} m")

# Sección 3: Orientación
st.sidebar.subheader("📐 2. Orientación del Plano")
tilt = st.sidebar.slider("Inclinación (Tilt)", 0, 90, 10, help="Ángulo respecto a la horizontal")
azimut = st.sidebar.slider("Azimut", -180, 180, 0, help="0° = Sur, -90° = Este, 90° = Oeste")

# Sección 4: Datos Cliente
st.sidebar.markdown("---")
st.sidebar.subheader("📋 3. Datos del Proyecto")
cliente = st.sidebar.text_input("Nombre del Cliente", "Cliente General")
fecha_proy = st.sidebar.date_input("Fecha de Simulación", datetime.now())

# --- PANEL PRINCIPAL DE TRABAJO ---
st.title("SIMU ING: Diseño y Simulación de Sistemas FV")

# Contenedor superior con mapa y resumen rápido
col_map, col_kpi = st.columns([2, 1])

with col_map:
    # Mapa Satelital Estilo Ingeniería
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
        height=250
    ))

with col_kpi:
    st.markdown("### Resumen del Sitio")
    st.info(f"""
    **Ubicación:** {ciudad_sel}, {info_ciudad['depto']}
    \n**Coordenadas:** {info_ciudad['lat']}, {info_ciudad['lon']}
    \n**Zona Climática:** Tropical Húmedo
    \n**Recurso Solar:** {info_ciudad['hsp']} kWh/m²/día (Promedio Anual)
    """)

# --- PESTAÑAS DE FLUJO DE TRABAJO ---
tabs = st.tabs(["🏗️ Diseño del Sistema", "📉 Pérdidas y Simulación", "💰 Análisis Económico", "📄 Reporte Ingeniería"])

# >>> PESTAÑA 1: DISEÑO DEL SISTEMA (System Design) <<<
with tabs[0]:
    st.subheader("Definición de Componentes y Arquitectura")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    
    with col_d1:
        st.markdown("##### 1. Consumo y Demanda")
        consumo_mes = st.number_input("Consumo Mensual Objetivo (kWh)", 100, 50000, 567)
        # Cálculo sugerido
        pot_sugerida = (consumo_mes / 30) / (info_ciudad['hsp'] * 0.80)
        st.caption(f"Potencia DC sugerida: **{pot_sugerida:.2f} kWp**")
        
    with col_d2:
        st.markdown("##### 2. Módulo Fotovoltaico")
        sel_panel = st.selectbox("Modelo de Panel", df_modulos["Modelo"])
        data_panel = df_modulos[df_modulos["Modelo"] == sel_panel].iloc[0]
        
        n_paneles = st.number_input("Cantidad de Módulos", 1, 500, int(pot_sugerida * 1000 / data_panel['Pmax']) + 1)
        st.session_state.n_paneles_real = n_paneles
        
        potencia_total_dc = (n_paneles * data_panel['Pmax']) / 1000 # kWp
        st.session_state.potencia_sistema_kw = potencia_total_dc
        
        st.success(f"**Potencia Instalada (STC): {potencia_total_dc:.2f} kWp**")
        
    with col_d3:
        st.markdown("##### 3. Inversor")
        sel_inv = st.selectbox("Modelo de Inversor", df_inversores["Modelo"])
        data_inv = df_inversores[df_inversores["Modelo"] == sel_inv].iloc[0]
        
        relacion_dc_ac = potencia_total_dc / (data_inv['Pnom']/1000)
        st.metric("Relación DC/AC", f"{relacion_dc_ac:.2f}", delta="Óptimo: 1.1 - 1.3" if 1.1 <= relacion_dc_ac <= 1.3 else "Revisar Dimensionamiento")

    st.markdown("---")
    st.subheader("Diseño del Arreglo (Array Design)")
    
    col_str1, col_str2 = st.columns(2)
    
    with col_str1:
        n_series = st.slider("Módulos en Serie (String)", 1, 25, 11)
        n_strings = np.ceil(n_paneles / n_series)
        st.write(f"Configuración: **{int(n_strings)} Strings de {n_series} módulos**")
        
    with col_str2:
        # Validación Eléctrica
        voc_array_cold = data_panel['Voc'] * n_series * 1.15 # Voc @ -10°C (Safety factor)
        vmp_array = data_panel['Vmp'] * n_series
        
        st.markdown("**Verificación de Límites del Inversor:**")
        col_chk1, col_chk2 = st.columns(2)
        col_chk1.metric("Voc Array (Max)", f"{voc_array_cold:.1f} V")
        col_chk2.metric("Vmax Inversor", f"{data_inv['Vmax']} V")
        
        if voc_array_cold > data_inv['Vmax']:
            st.error("🛑 PELIGRO: El voltaje de circuito abierto supera el límite del inversor. Reduzca módulos en serie.")
        elif vmp_array < data_inv['Vmin']:
            st.warning("⚠️ ALERTA: El voltaje de operación es muy bajo. El inversor podría no arrancar.")
        else:
            st.success("✅ Diseño Eléctrico Validado y Seguro.")

# >>> PESTAÑA 2: SIMULACIÓN (Simulation) <<<
with tabs[1]:
    st.subheader("Simulación Energética y Pérdidas")
    
    col_res1, col_res2 = st.columns([2, 1])
    
    # Motor de Cálculo
    gen_diaria, pr_sistema = simulacion_pvsyst(potencia_total_dc, info_ciudad['hsp'], 28) # Temp promedio 28°C
    gen_mensual = gen_diaria * 30
    st.session_state.gen_total_mensual = gen_mensual
    gen_anual = gen_mensual * 12
    
    with col_res1:
        # Gráfica de Producción Mensual (Barras Azules Técnicas)
        st.markdown("###### Producción de Energía Normalizada")
        meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        # Simulación de variación climática estacional
        produccion_simulada = [gen_mensual * (1 + 0.1*np.sin((i-1)*np.pi/6)) for i in range(12)]
        
        fig_prod, ax_prod = plt.subplots(figsize=(10, 4))
        ax_prod.bar(meses, produccion_simulada, color='#2c3e50', alpha=0.8, edgecolor='black', linewidth=0.5)
        ax_prod.set_ylabel("Energía [kWh]")
        ax_prod.set_title("Energía Inyectada a la Red (E_Grid)", fontsize=10)
        ax_prod.grid(axis='y', linestyle='--', alpha=0.4)
        ax_prod.spines['top'].set_visible(False)
        ax_prod.spines['right'].set_visible(False)
        st.pyplot(fig_prod)
        fig_prod.savefig("temp_bars_monthly.png", bbox_inches='tight') # Guardar para PDF

    with col_res2:
        st.markdown("###### Resultados Principales")
        st.metric("Generación Específica", f"{gen_anual/potencia_total_dc:.0f} kWh/kWp/año")
        st.metric("Performance Ratio (PR)", f"{pr_sistema*100:.1f} %")
        st.metric("Ahorro de CO2", f"{gen_anual * 0.4:.1f} kg/año") # Factor 0.4 kg/kWh
        
        st.markdown("###### Diagrama de Pérdidas")
        st.text("Temp. Array: -4.5%")
        st.text("Suciedad: -3.0%")
        st.text("Ohmicas DC: -1.5%")
        st.text("Inv. Eff: -3.0%")
        st.progress(pr_sistema)

    # Gráficas ocultas para PDF (Trayectoria Solar y Curva Diaria)
    # 1. Trayectoria Solar
    fig_sun, ax_sun = plt.subplots(figsize=(6, 4))
    azimuths = np.linspace(-90, 90, 100)
    altitudes = 90 - np.abs(info_ciudad['lat']) - np.abs(azimuths)/2 # Modelo simple
    ax_sun.plot(azimuths, altitudes, color='#f39c12', label='Solsticio Verano')
    ax_sun.plot(azimuths, altitudes-23.5, color='#3498db', label='Solsticio Invierno')
    ax_sun.fill_between(azimuths, 0, 15, color='gray', alpha=0.3, label='Horizonte/Obstáculos')
    ax_sun.set_title("Trayectoria Solar", fontsize=10)
    ax_sun.set_xlabel("Azimut [°]")
    ax_sun.set_ylabel("Elevación [°]")
    ax_sun.legend(loc='upper right', fontsize=8)
    ax_sun.grid(True, linestyle=':')
    fig_sun.savefig("temp_sunpath.png", bbox_inches='tight', dpi=100)
    plt.close(fig_sun)

    # 2. Curva Diaria
    fig_daily, ax_daily = plt.subplots(figsize=(6, 4))
    hours = np.arange(6, 19)
    irrad = np.sin(np.pi * (hours - 6) / 12) * 1000
    ax_daily.plot(hours, irrad, color='#e67e22', linewidth=2)
    ax_daily.fill_between(hours, irrad, color='#f1c40f', alpha=0.3)
    ax_daily.set_title("Perfil Diario de Irradiancia", fontsize=10)
    ax_daily.set_xlabel("Hora Solar")
    ax_daily.set_ylabel("Irradiancia [W/m²]")
    ax_daily.set_ylim(0, 1100)
    ax_daily.grid(True, linestyle=':')
    fig_daily.savefig("temp_daily_curve.png", bbox_inches='tight', dpi=100)
    plt.close(fig_daily)

    # 3. Gráfica Comparativa (Página 2 PDF)
    fig_comp, ax_comp = plt.subplots(figsize=(10, 4))
    x_idx = np.arange(len(meses))
    width = 0.35
    ax_comp.bar(x_idx - width/2, [consumo_mes]*12, width, label='Consumo Usuario', color='#e74c3c')
    ax_comp.bar(x_idx + width/2, produccion_simulada, width, label='Generación FV', color='#27ae60')
    ax_comp.set_title("Balance Energético: Generación vs Consumo")
    ax_comp.set_ylabel("Energía [kWh]")
    ax_comp.set_xticks(x_idx)
    ax_comp.set_xticklabels(meses)
    ax_comp.legend()
    ax_comp.grid(axis='y', linestyle='--', alpha=0.3)
    fig_comp.savefig("temp_balance_bar.png", bbox_inches='tight', dpi=100)
    plt.close(fig_comp)

# >>> PESTAÑA 3: ECONÓMICO (Financial) <<<
with tabs[2]:
    st.subheader("Análisis de Rentabilidad")
    
    col_fin1, col_fin2 = st.columns(2)
    
    with col_fin1:
        # Estructura de Costos (CAPEX)
        st.markdown("###### Estructura de Costos (Estimado)")
        costo_modulos = n_paneles * data_panel['Precio']
        costo_inversor = data_inv['Precio']
        costo_bos = n_paneles * 200000 # Estructura + Cableado estimado
        costo_ing = potencia_total_dc * 500000 # Ingeniería y trámites
        
        capex_total = costo_modulos + costo_inversor + costo_bos + costo_ing
        
        costos_df = pd.DataFrame({
            "Ítem": ["Módulos FV", "Inversores", "BOS (Estructura/Cables)", "Ingeniería & MO"],
            "Valor (COP)": [costo_modulos, costo_inversor, costo_bos, costo_ing]
        })
        st.dataframe(costos_df, use_container_width=True)
        st.metric("CAPEX Total", f"${capex_total:,.0f} COP")
        
    with col_fin2:
        st.markdown("###### Flujo de Caja")
        tarifa_energia = st.number_input("Tarifa Energía ($/kWh)", 500, 2000, 850)
        ahorro_anual_dinero = gen_anual * tarifa_energia
        
        # Cálculo simple de ROI y Payback
        flujo_acumulado = [-capex_total]
        saldo = -capex_total
        incremento_tarifa = 0.05 # 5% anual
        
        for i in range(25):
            ahorro_anio = ahorro_anual_dinero * ((1 + incremento_tarifa) ** i)
            saldo += ahorro_anio
            flujo_acumulado.append(saldo)
            
        roi_anos = capex_total / ahorro_anual_dinero
        
        st.metric("Retorno de Inversión (ROI)", f"{roi_anos:.1f} Años")
        st.metric("Ahorro Acumulado (25 años)", f"${flujo_acumulado[-1]:,.0f} COP")
        
        # Gráfica Flujo de Caja
        fig_cash, ax_cash = plt.subplots(figsize=(8, 4))
        ax_cash.plot(flujo_acumulado, color='#27ae60', linewidth=2)
        ax_cash.axhline(0, color='black', linestyle='-', linewidth=1)
        ax_cash.set_title("Flujo de Caja Acumulado (25 Años)")
        ax_cash.set_xlabel("Años")
        ax_cash.set_ylabel("COP Acumulado")
        ax_cash.grid(True, linestyle=':', alpha=0.6)
        st.pyplot(fig_cash)
        fig_cash.savefig("temp_roi.png", bbox_inches='tight', dpi=100)
        plt.close(fig_cash)

# --- BOTÓN DE GENERACIÓN DE REPORTE (FINAL) ---
with tabs[3]:
    st.subheader("Entregables de Ingeniería")
    st.markdown("Generación de memoria de cálculo completa, planos y presupuesto.")
    
    if st.button("📄 Generar Reporte PDF (Versión SIMU ING)", use_container_width=True):
        try:
            # INICIALIZACIÓN DEL PDF
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # ==================================================================
            # PÁGINA 1: PORTADA TÉCNICA
            # ==================================================================
            pdf.add_page()
            
            # Franja Encabezado
            pdf.set_fill_color(10, 40, 90) # Azul oscuro profesional
            pdf.rect(0, 0, 210, 35, 'F')
            
            # Títulos Portada
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 22)
            pdf.set_xy(10, 10)
            pdf.cell(0, 10, 'PROPUESTA TECNICA', 0, 1)
            pdf.set_font('Arial', '', 12)
            pdf.set_xy(10, 20)
            pdf.cell(0, 5, 'SISTEMA DE ENERGIA SOLAR FOTOVOLTAICA', 0, 1)
            
            # Logo (Si existe, o placeholder)
            if os.path.exists("logo.png"):
                try: pdf.image("logo.png", x=170, y=5, w=30)
                except: pass
                
            pdf.set_text_color(0, 0, 0)
            pdf.ln(20)
            
            # Tabla de Datos del Proyecto (Estilo PVsyst)
            pdf.set_font('Arial', 'B', 12)
            pdf.set_fill_color(230, 230, 230)
            pdf.cell(0, 8, "  DATOS DEL PROYECTO", 0, 1, 'L', True)
            pdf.ln(2)
            
            pdf.set_font('Arial', '', 10)
            datos_proyecto = [
                ("Cliente:", limpiar(cliente)),
                ("Ubicacion:", f"{limpiar(ciudad_sel)} ({info_ciudad['lat']}, {info_ciudad['lon']})"),
                ("Fecha:", str(fecha_proy)),
                ("Potencia DC:", f"{potencia_total_dc:.2f} kWp"),
                ("Generacion Mensual:", f"{gen_mensual:.0f} kWh/mes")
            ]
            
            for key, val in datos_proyecto:
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(40, 7, key, 0, 0)
                pdf.set_font('Arial', '', 10)
                pdf.cell(0, 7, val, 0, 1)
                pdf.set_draw_color(200, 200, 200)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
            pdf.ln(10)
            
            # Sección Análisis Solar (Gráficas lado a lado)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 8, "  ANALISIS DE RECURSO SOLAR", 0, 1, 'L', True)
            pdf.ln(2)
            
            y_graphs = pdf.get_y()
            if os.path.exists("temp_sunpath.png"):
                pdf.image("temp_sunpath.png", x=10, y=y_graphs, w=90)
            if os.path.exists("temp_daily_curve.png"):
                pdf.image("temp_daily_curve.png", x=105, y=y_graphs, w=90)
            
            pdf.ln(65)
            
            # ==================================================================
            # PÁGINA 2: ANÁLISIS FINANCIERO Y ENERGÉTICO
            # ==================================================================
            pdf.add_page()
            
            pdf.set_font('Arial', 'B', 12)
            pdf.set_fill_color(230, 230, 230)
            pdf.cell(0, 8, "  BALANCE ENERGETICO Y FINANCIERO", 0, 1, 'L', True)
            pdf.ln(5)
            
            # Gráfica de Barras Comparativas
            if os.path.exists("temp_balance_bar.png"):
                pdf.image("temp_balance_bar.png", x=10, w=190)
                pdf.ln(65) # Espacio de la imagen
                
            # Gráfica ROI
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 8, "  ANALISIS DE RETORNO DE INVERSION", 0, 1, 'L')
            if os.path.exists("temp_roi.png"):
                pdf.image("temp_roi.png", x=10, w=190)
                
            # Resumen Financiero Texto
            pdf.set_y(230)
            pdf.set_font('Arial', '', 11)
            resumen_fin = f"Inversion Total: ${capex_total:,.0f} | Retorno de Inversion: {roi_anos:.1f} Anios | Ahorro Acumulado: ${flujo_acumulado[-1]:,.0f}"
            pdf.multi_cell(0, 6, resumen_fin, 0, 'C')

            # ==================================================================
            # PÁGINA 3: DIAGRAMA UNIFILAR (CAD DETALLADO)
            # ==================================================================
            pdf.add_page('L') # Hoja Horizontal para Plano
            
            # Marco del Plano
            pdf.set_line_width(0.5)
            pdf.rect(5, 5, 287, 200) # Borde Exterior
            pdf.rect(10, 10, 277, 190) # Borde Interior
            
            # Cajetín Inferior
            y_cajetin = 175
            pdf.line(10, y_cajetin, 287, y_cajetin)
            
            # Datos Cajetín
            pdf.set_font('Arial', 'B', 8)
            pdf.set_xy(15, y_cajetin+3); pdf.cell(20, 4, "PROYECTO:", 0, 1)
            pdf.set_font('Arial', '', 8)
            pdf.set_xy(15, y_cajetin+7); pdf.cell(50, 4, limpiar(cliente), 0, 0)
            
            pdf.set_xy(80, y_cajetin+3); pdf.set_font('Arial', 'B', 8); pdf.cell(20, 4, "UBICACION:", 0, 1)
            pdf.set_xy(80, y_cajetin+7); pdf.set_font('Arial', '', 8); pdf.cell(50, 4, limpiar(ciudad_sel), 0, 0)
            
            pdf.set_xy(150, y_cajetin+3); pdf.set_font('Arial', 'B', 8); pdf.cell(20, 4, "DISENO:", 0, 1)
            pdf.set_xy(150, y_cajetin+7); pdf.set_font('Arial', '', 8); pdf.cell(50, 4, "INGENIERIA SIMU ING", 0, 0)
            
            pdf.set_xy(230, y_cajetin+3); pdf.set_font('Arial', 'B', 8); pdf.cell(20, 4, "PLANO:", 0, 1)
            pdf.set_xy(230, y_cajetin+7); pdf.set_font('Arial', '', 8); pdf.cell(30, 4, "EL-01 UNIFILAR", 0, 0)

            # --- DIBUJO DEL DIAGRAMA (Coordenadas calibradas) ---
            y0 = 80
            x_start = 30
            
            # 1. ARREGLO FOTOVOLTAICO
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.3)
            # Dibujo de 3 módulos simbólicos
            for i in range(3):
                px = x_start + i*15
                pdf.rect(px, y0, 12, 20) # Marco
                pdf.line(px, y0+6, px+12, y0+6) # Celda 1
                pdf.line(px, y0+13, px+12, y0+13) # Celda 2
            
            pdf.set_font('Arial', 'B', 8)
            pdf.text(x_start, y0-5, "GENERADOR FV")
            pdf.set_font('Arial', '', 7)
            pdf.text(x_start, y0-2, f"{n_paneles} x {data_panel['Pmax']}W")
            
            # Cableado DC
            pdf.set_draw_color(200, 0, 0) # Rojo Positivo
            pdf.line(x_start+36, y0+2, 90, y0+2)
            pdf.text(70, y0+1, "DC (+)")
            
            pdf.set_draw_color(0, 0, 0) # Negro Negativo
            pdf.line(x_start+36, y0+18, 90, y0+18)
            pdf.text(70, y0+17, "DC (-)")
            
            # Tierra Paneles
            pdf.set_draw_color(0, 150, 0) # Verde Tierra
            pdf.line(x_start+6, y0+20, x_start+6, y0+35) # Bajante
            pdf.line(x_start+6, y0+35, 250, y0+35) # Bus de tierra horizontal
            pdf.text(x_start+7, y0+30, "T")
            
            # 2. CAJA DC (Tablero de Protecciones)
            pdf.set_draw_color(0, 0, 0)
            pdf.rect(90, y0-10, 40, 40)
            pdf.set_font('Arial', 'B', 7)
            pdf.text(92, y0-7, "TABLERO DC")
            
            # Fusibles
            pdf.rect(95, y0, 8, 4); pdf.line(95, y0+2, 103, y0+2) # Fus +
            pdf.rect(95, y0+16, 8, 4); pdf.line(95, y0+18, 103, y0+18) # Fus -
            pdf.text(96, y0-1, "Fus 15A")
            
            # DPS DC
            pdf.rect(110, y0+8, 6, 10)
            pdf.text(111, y0+7, "DPS")
            pdf.line(113, y0+18, 113, y0+35) # Conexión a bus tierra
            
            # Salida DC a Inversor
            pdf.set_draw_color(200, 0, 0); pdf.line(130, y0+2, 150, y0+2)
            pdf.set_draw_color(0, 0, 0); pdf.line(130, y0+18, 150, y0+18)
            
            # 3. INVERSOR
            pdf.rect(150, y0-5, 30, 30)
            pdf.set_font('Arial', 'B', 8); pdf.text(152, y0, "INVERSOR")
            pdf.set_font('Arial', '', 6); pdf.text(152, y0+5, f"{data_inv['Pnom']/1000} kW")
            
            # Tierra Inversor
            pdf.set_draw_color(0, 150, 0)
            pdf.line(165, y0+25, 165, y0+35)
            
            # Salida AC
            pdf.set_draw_color(0, 0, 0)
            pdf.line(180, y0+10, 200, y0+10) # Fase
            pdf.line(180, y0+15, 200, y0+15) # Neutro
            pdf.text(185, y0+9, "L"); pdf.text(185, y0+14, "N")
            
            # 4. TABLERO AC
            pdf.rect(200, y0-5, 30, 30)
            pdf.set_font('Arial', 'B', 7); pdf.text(202, y0-2, "TABLERO AC")
            
            # Breaker AC
            pdf.rect(205, y0+8, 5, 10)
            pdf.line(205, y0+13, 210, y0+8) # Palanca
            pdf.text(205, y0+7, "Brk")
            
            # Salida a Medidor
            pdf.line(230, y0+10, 250, y0+10)
            pdf.line(230, y0+15, 250, y0+15)
            
            # 5. MEDIDOR (Versión Segura sin crash)
            pdf.rect(250, y0, 20, 20)
            try:
                # Intenta usar ellipse (FPDF moderno)
                if hasattr(pdf, 'ellipse'): pdf.ellipse(254, y0+5, 12, 12)
                # Intenta usar circle (FPDF antiguo)
                elif hasattr(pdf, 'circle'): pdf.circle(260, y0+11, 6)
                # Fallback texto
                else: 
                    pdf.set_font('Arial', 'B', 14)
                    pdf.text(257, y0+15, "M")
            except:
                pdf.set_font('Arial', 'B', 14)
                pdf.text(257, y0+15, "M")
                
            pdf.set_font('Arial', 'B', 10); pdf.text(256, y0+12, "kWh")
            
            # Red Eléctrica
            pdf.line(270, y0+10, 280, y0+10)
            pdf.line(270, y0+15, 280, y0+15)
            pdf.text(275, y0+8, "RED")
            
            # Tierra General Símbolo
            pdf.set_draw_color(0, 150, 0)
            pdf.line(30, y0+35, 270, y0+35) # Bus equipotencial extendido
            dibujar_tierra(pdf, 150, y0+35)
            pdf.set_font('Arial', 'B', 6); pdf.text(152, y0+40, "SPT")

            # ==================================================================
            # PÁGINA 4: PRESUPUESTO DETALLADO
            # ==================================================================
            pdf.add_page('P')
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'PRESUPUESTO DETALLADO DE OBRA', 0, 1, 'C')
            pdf.ln(10)
            
            # Encabezados Tabla
            pdf.set_fill_color(200, 220, 255)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(100, 10, 'Item / Descripcion', 1, 0, 'C', True)
            pdf.cell(20, 10, 'Cant.', 1, 0, 'C', True)
            pdf.cell(35, 10, 'Vr. Unitario', 1, 0, 'C', True)
            pdf.cell(35, 10, 'Vr. Total', 1, 1, 'C', True)
            
            pdf.set_font('Arial', '', 10)
            
            items_presupuesto = [
                (f"Panel Solar {data_panel['Modelo']}", n_paneles, data_panel['Precio']),
                (f"Inversor {data_inv['Modelo']}", 1, data_inv['Precio']),
                ("Estructura de Montaje (Aluminio Anodizado)", n_paneles, 150000),
                ("Materiales Electricos (Cable, DPS, Tableros)", 1, costo_bos),
                ("Ingenieria, Mano de Obra y Tramites", 1, costo_ing)
            ]
            
            total_presupuesto = 0
            
            for desc, cant, unit in items_presupuesto:
                total_linea = cant * unit
                total_presupuesto += total_linea
                
                pdf.cell(100, 10, limpiar(desc[:50]), 1)
                pdf.cell(20, 10, str(int(cant)), 1, 0, 'C')
                pdf.cell(35, 10, f"${unit:,.0f}", 1, 0, 'R')
                pdf.cell(35, 10, f"${total_linea:,.0f}", 1, 1, 'R')
            
            # Total General
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(155, 10, "GRAN TOTAL", 1, 0, 'R')
            pdf.cell(35, 10, f"${total_presupuesto:,.0f}", 1, 1, 'R')
            
            pdf.ln(20)
            pdf.set_font('Arial', 'I', 8)
            pdf.multi_cell(0, 5, "Nota: Los precios son estimados basados en lista de precios de mercado 2026. No incluye viaticos fuera de la ciudad base. Validez de la oferta: 15 dias.")

            # Generar Archivo Final
            pdf_bytes = pdf.output(dest='S')
            if isinstance(pdf_bytes, str): pdf_bytes = pdf_bytes.encode('latin-1')
            
            st.download_button(
                label="📥 DESCARGAR REPORTE OFICIAL (PDF)",
                data=pdf_bytes,
                file_name=f"Proyecto_Solar_{limpiar(cliente)}.pdf",
                mime="application/pdf"
            )
            st.success("✅ Reporte generado exitosamente.")

        except Exception as e:
            st.error(f"Error generando el PDF: {e}")
