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
# 1. CONFIGURACIÓN DEL ENTORNO SIMU ING
# ==============================================================================
st.set_page_config(
    page_title="SIMU ING - Software Fotovoltaico",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS para simular interfaz de software de escritorio (Tipo PVsyst)
st.markdown("""
    <style>
    .main {background-color: #f0f2f6;}
    .stApp {background-color: #ffffff;}
    div.stButton > button {background-color: #004080; color: white; border-radius: 5px; width: 100%;}
    div.stButton > button:hover {background-color: #0059b3; color: white;}
    .reportview-container .main .block-container {padding-top: 2rem;}
    h1 {color: #00264d; font-family: 'Arial', sans-serif;}
    h2 {color: #004080; border-bottom: 2px solid #004080; padding-bottom: 5px;}
    .stMetric {background-color: #e6f2ff; padding: 10px; border-radius: 5px; border-left: 5px solid #004080;}
    </style>
""", unsafe_allow_html=True)

# Inicialización de Session State para persistencia de datos
if 'sim_done' not in st.session_state: st.session_state.sim_done = False
if 'gen_anual' not in st.session_state: st.session_state.gen_anual = 0
if 'pr_global' not in st.session_state: st.session_state.pr_global = 0
if 'losses' not in st.session_state: st.session_state.losses = {}

# ==============================================================================
# 2. MOTOR DE CÁLCULO E INGENIERÍA (KERNEL)
# ==============================================================================

class SolarEngine:
    """Motor de física solar simplificado para SIMU ING"""
    def __init__(self, lat, tilt, azimut):
        self.lat = lat
        self.tilt = np.radians(tilt)
        self.azimut = np.radians(azimut - 180) # Ajuste a Sur=0

    def calcular_transposicion(self, hsp_horizontal):
        # Modelo simplificado de transposición R. Perez (Ganancia por inclinación)
        # Factor geométrico simple
        gain = max(0, np.cos(self.tilt) + 0.3 * np.sin(self.tilt)) # Aproximación empírica
        return hsp_horizontal * gain

    def simular_produccion(self, potencia_dc, hsp_plano, perdidas_totales):
        # Generación de perfil mensual (Curva de campana estacional)
        meses = np.arange(1, 13)
        # Simulación de estacionalidad (Menos sol en invierno, más en verano relativo al ecuador)
        seasonality = 1 + 0.1 * np.cos((meses - 6) * 2 * np.pi / 12) 
        
        prod_diaria = potencia_dc * hsp_plano * seasonality * (1 - perdidas_totales)
        prod_mensual = prod_diaria * 30
        return prod_mensual

# Base de Datos de Componentes (Local DB)
def get_database():
    modulos = pd.DataFrame({
        "Modelo": ["Jinko Tiger 450W", "Trina Vertex 550W", "Canadian BiHi 600W", "Longi Hi-MO 540W"],
        "Pmax": [450, 550, 600, 540],
        "Voc": [41.5, 49.6, 41.7, 49.5],
        "Isc": [13.4, 13.9, 18.1, 13.8],
        "Coeff_T": [-0.35, -0.34, -0.34, -0.35],
        "Precio": [550000, 680000, 850000, 670000]
    })
    inversores = pd.DataFrame({
        "Modelo": ["Fronius Primo 3.0", "Huawei SUN2000 5KTL", "SMA Sunny Boy 3.0", "Growatt 5000MTL"],
        "Pnom": [3000, 5000, 3000, 5000],
        "Vmin": [80, 120, 100, 100],
        "Vmax": [800, 980, 600, 550],
        "Eff": [0.97, 0.98, 0.965, 0.97],
        "Precio": [4500000, 5200000, 4800000, 3200000]
    })
    return modulos, inversores

df_mod, df_inv = get_database()

# ==============================================================================
# 3. INTERFAZ GRÁFICA (GUI)
# ==============================================================================

# --- BARRA LATERAL: PROYECTO ---
st.sidebar.title("SIMU ING v5.0")
st.sidebar.subheader("1. Definición del Proyecto")
cliente = st.sidebar.text_input("Nombre del Cliente", "Cliente General")
ubicaciones = {
    "Bogotá": [4.71, -74.07, 4.2], "Medellín": [6.24, -75.58, 4.5],
    "Cali": [3.45, -76.53, 4.8], "Barranquilla": [10.96, -74.78, 5.5],
    "Leticia": [-4.21, -69.94, 4.5], "San José del Guaviare": [2.57, -72.63, 4.5]
}
sitio = st.sidebar.selectbox("Sitio Geográfico", list(ubicaciones.keys()))
lat, lon, hsp_base = ubicaciones[sitio]

st.sidebar.subheader("2. Orientación")
tilt = st.sidebar.slider("Inclinación (°)", 0, 90, 15)
azimut = st.sidebar.slider("Azimut (°)", 0, 360, 0, help="0=Sur, 90=Oeste, -90=Este")

# --- ÁREA PRINCIPAL ---
st.title("SIMU ING - Diseño y Simulación")

tabs = st.tabs(["🏗️ Diseño del Sistema", "📉 Pérdidas y Simulación", "💰 Financiero", "📄 Reporte PDF"])

# --- TAB 1: DISEÑO ---
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Campo Fotovoltaico")
        mod_sel = st.selectbox("Módulo PV", df_mod["Modelo"])
        dato_mod = df_mod[df_mod["Modelo"] == mod_sel].iloc[0]
        
        consumo = st.number_input("Consumo Meta (kWh/mes)", 100, 50000, 500)
        n_calc = int((consumo * 1.2) / (dato_mod["Pmax"] * hsp_base * 30 / 1000))
        
        n_mod = st.number_input("Número de Módulos", 1, 500, n_calc)
        pot_dc = n_mod * dato_mod["Pmax"] / 1000
        st.info(f"Potencia Array STC: **{pot_dc:.2f} kWp**")

    with c2:
        st.subheader("Selección de Inversor")
        inv_sel = st.selectbox("Inversor", df_inv["Modelo"])
        dato_inv = df_inv[df_inv["Modelo"] == inv_sel].iloc[0]
        
        # Validación Eléctrica (String Sizing)
        st.markdown("##### Verificación de Strings")
        n_serie = st.slider("Módulos en Serie", 1, 25, 10)
        voc_string = dato_mod["Voc"] * n_serie * 1.15 # Corrección por baja temp
        vmp_string = dato_mod["Pmax"]/dato_mod["Isc"] * n_serie # Aprox Vmp
        
        c_v1, c_v2 = st.columns(2)
        c_v1.metric("Voc @ -10°C", f"{voc_string:.1f} V")
        c_v2.metric("Vmax Inversor", f"{dato_inv['Vmax']} V")
        
        if voc_string > dato_inv["Vmax"]:
            st.error("❌ DISEÑO INVÁLIDO: El voltaje supera el límite del inversor.")
        elif vmp_string < dato_inv["Vmin"]:
            st.warning("⚠️ VOLTAJE BAJO: Verifique rango MPPT.")
        else:
            st.success("✅ Diseño Eléctrico OK")

# --- TAB 2: SIMULACIÓN ---
with tabs[1]:
    st.subheader("Balance Energético y Pérdidas")
    
    # Definición de Pérdidas Detalladas
    l_soiling = st.slider("Pérdidas por Suciedad (%)", 0, 10, 3) / 100
    l_thermal = 0.08 # Estimado térmico
    l_wiring = 0.015 # Caída de tensión DC
    l_inv = 1 - dato_inv["Eff"]
    l_total = 1 - ((1-l_soiling) * (1-l_thermal) * (1-l_wiring) * (1-l_inv))
    
    # Simulación
    engine = SolarEngine(lat, tilt, azimut)
    prod_mensual = engine.simular_produccion(pot_dc, hsp_base, l_total)
    gen_anual = sum(prod_mensual)
    
    # Guardar en Session State
    st.session_state.gen_anual = gen_anual
    st.session_state.prod_mensual = prod_mensual
    
    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric("Producción Anual", f"{gen_anual:,.0f} kWh")
    col_res2.metric("PR (Performance Ratio)", f"{(1-l_total)*100:.1f}%")
    col_res3.metric("Producción Específica", f"{gen_anual/pot_dc:.0f} kWh/kWp")
    
    # Gráfica
    meses_txt = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(meses_txt, prod_mensual, color='#004080')
    ax.set_title("Energía Inyectada a la Red (kWh)")
    ax.grid(axis='y', alpha=0.3)
    st.pyplot(fig)
    fig.savefig("temp_graph.png", bbox_inches='tight')

# --- TAB 3: FINANCIERO ---
with tabs[2]:
    st.subheader("Evaluación Económica")
    
    # CAPEX
    costo_modulos = n_mod * dato_mod["Precio"]
    costo_inv = dato_inv["Precio"]
    costo_bos = pot_dc * 800000 # Estructura + Cables
    costo_mo = pot_dc * 500000 # Mano de Obra
    capex = costo_modulos + costo_inv + costo_bos + costo_mo
    
    tarifa = st.number_input("Tarifa Energía ($/kWh)", 500, 2000, 850)
    ahorro_anual = gen_anual * tarifa
    roi = capex / ahorro_anual if ahorro_anual > 0 else 0
    
    st.write(f"**Inversión Total (CAPEX):** ${capex:,.0f} COP")
    st.metric("Retorno de Inversión (ROI)", f"{roi:.1f} Años")
    
    # Flujo de Caja
    flujo = [-capex]
    acumulado = -capex
    flujo_acumulado = [-capex]
    
    for i in range(25):
        ingreso = ahorro_anual * (1.05**i) # Inflación energética 5%
        acumulado += ingreso
        flujo_acumulado.append(acumulado)
        
    fig_roi, ax_roi = plt.subplots(figsize=(10, 4))
    ax_roi.plot(range(26), flujo_acumulado, color='green', linewidth=2)
    ax_roi.axhline(0, color='red', linestyle='--')
    ax_roi.set_title("Retorno de Inversión (25 Años)")
    ax_roi.grid(True)
    st.pyplot(fig_roi)
    fig_roi.savefig("temp_roi.png", bbox_inches='tight')

# --- TAB 4: REPORTE PDF SIMU ING ---
with tabs[3]:
    st.subheader("Generación de Reporte SIMU ING")
    
    if st.button("📄 Imprimir Reporte Oficial", use_container_width=True):
        try:
            # === GENERACIÓN DE GRÁFICAS ADICIONALES PARA PDF ===
            # 1. Trayectoria Solar
            fig_sun, ax_sun = plt.subplots(figsize=(6, 3))
            az = np.linspace(-90, 90, 100)
            alt = 70 * np.cos(np.radians(az))
            ax_sun.plot(az, alt, color='orange', label='Trayectoria')
            ax_sun.fill_between(az, 0, 15, color='gray', alpha=0.5, label='Obstáculos')
            ax_sun.set_title("Trayectoria Solar")
            ax_sun.legend()
            fig_sun.savefig("temp_sun.png", bbox_inches='tight')
            plt.close(fig_sun)
            
            # 2. Curva Diaria
            fig_day, ax_day = plt.subplots(figsize=(6, 3))
            h = np.arange(6, 19)
            irr = np.sin(np.pi * (h-6)/12) * 1000
            ax_day.plot(h, irr, color='orange')
            ax_day.fill_between(h, irr, alpha=0.2, color='orange')
            ax_day.set_title("Perfil Diario Irradiancia")
            fig_day.savefig("temp_day.png", bbox_inches='tight')
            plt.close(fig_day)

            # === INICIO DOCUMENTO PDF ===
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # --- PÁGINA 1: PORTADA Y RESUMEN ---
            pdf.add_page()
            
            # Encabezado Corporativo SIMU ING
            pdf.set_fill_color(0, 64, 128) # Azul Ingeniero
            pdf.rect(0, 0, 210, 40, 'F')
            
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 24)
            pdf.set_xy(10, 15)
            pdf.cell(0, 10, 'SIMU ING', 0, 1)
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 5, 'REPORTE DE INGENIERIA FOTOVOLTAICA', 0, 1)
            
            # Logo (Si existe)
            if os.path.exists("logo.png"):
                try: pdf.image("logo.png", x=170, y=5, w=30)
                except: pass
                
            pdf.set_text_color(0, 0, 0)
            pdf.ln(20)
            
            # Tabla Datos
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, '1. PARAMETROS DEL PROYECTO', 0, 1, 'L')
            
            pdf.set_font('Arial', '', 10)
            params = [
                ("Cliente", limpiar(cliente)),
                ("Ubicación", f"{sitio} ({lat}, {lon})"),
                ("Potencia DC", f"{pot_dc:.2f} kWp"),
                ("Inversor", limpiar(dato_inv["Modelo"])),
                ("Generación Anual", f"{gen_anual:,.0f} kWh")
            ]
            
            for k, v in params:
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(50, 8, k, 1, 0, 'L', True)
                pdf.cell(0, 8, v, 1, 1, 'L')
            
            pdf.ln(10)
            
            # Imágenes Solares (Lado a lado)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, '2. RECURSO SOLAR', 0, 1, 'L')
            y_img = pdf.get_y()
            if os.path.exists("temp_sun.png"): pdf.image("temp_sun.png", x=10, y=y_img, w=90)
            if os.path.exists("temp_day.png"): pdf.image("temp_day.png", x=105, y=y_img, w=90)
            pdf.ln(60)

            # --- PÁGINA 2: RESULTADOS Y FINANZAS ---
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, '3. RESULTADOS DE SIMULACION', 0, 1)
            
            # Gráfica Producción Mensual
            if os.path.exists("temp_graph.png"):
                pdf.image("temp_graph.png", x=10, w=190)
            
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, '4. ANALISIS FINANCIERO', 0, 1)
            
            # Gráfica ROI
            if os.path.exists("temp_roi.png"):
                pdf.image("temp_roi.png", x=10, w=190)
            
            pdf.set_font('Arial', '', 11)
            pdf.cell(0, 10, f"Retorno de Inversion Estimado: {roi:.1f} Anios", 0, 1)

            # --- PÁGINA 3: PLANO UNIFILAR (CAD STYLE) ---
            pdf.add_page('L') # Horizontal
            
            # Marco CAD
            pdf.set_line_width(0.5)
            pdf.rect(5, 5, 287, 200) # Exterior
            pdf.rect(10, 10, 277, 190) # Interior
            
            # Cajetín
            pdf.line(10, 175, 287, 175)
            pdf.set_font('Arial', 'B', 8)
            pdf.set_xy(15, 177); pdf.cell(20, 5, "PROYECTO: " + limpiar(cliente))
            pdf.set_xy(100, 177); pdf.cell(20, 5, "PLANO: DIAGRAMA UNIFILAR - SIMU ING")
            pdf.set_xy(220, 177); pdf.cell(20, 5, "REV: 01 - " + str(datetime.now().date()))
            
            # DIBUJO TÉCNICO DETALLADO
            # Coordenadas base
            y0 = 80
            
            # 1. Campo FV
            pdf.set_draw_color(0)
            for i in range(3):
                x = 40 + i*20
                pdf.rect(x, y0, 15, 25)
                # Celdas
                pdf.line(x, y0+8, x+15, y0+8)
                pdf.line(x, y0+16, x+15, y0+16)
            
            pdf.set_xy(40, y0-10)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(60, 5, f"CAMPO FV: {n_mod}x {dato_mod['Pmax']}W", 0, 1, 'C')
            
            # Cableado DC
            pdf.set_draw_color(200, 0, 0) # Rojo
            pdf.line(85, y0+5, 120, y0+5); pdf.text(95, y0+4, "DC +")
            pdf.set_draw_color(0) # Negro
            pdf.line(85, y0+20, 120, y0+20); pdf.text(95, y0+19, "DC -")
            
            # Caja Protecciones DC
            pdf.rect(120, y0-5, 30, 35)
            pdf.text(122, y0, "STR BOX")
            # Fusibles
            pdf.rect(125, y0+4, 6, 3); pdf.text(132, y0+7, "Fus")
            pdf.rect(125, y0+19, 6, 3)
            
            # Inversor
            pdf.rect(170, y0-5, 35, 35)
            pdf.set_font('Arial', 'B', 8)
            pdf.text(172, y0+5, "INVERSOR")
            pdf.text(172, y0+15, dato_inv["Modelo"][:10])
            
            # Conexión Caja-Inv
            pdf.line(150, y0+5, 170, y0+5)
            pdf.line(150, y0+20, 170, y0+20)
            
            # Salida AC
            pdf.set_draw_color(0, 0, 200) # Azul
            pdf.line(205, y0+12, 230, y0+12)
            pdf.text(210, y0+10, "AC")
            
            # Tablero AC
            pdf.set_draw_color(0)
            pdf.rect(230, y0-5, 25, 35)
            pdf.text(232, y0, "TAB. AC")
            pdf.rect(235, y0+10, 5, 5); pdf.text(242, y0+14, "Brk")
            
            # Medidor (Círculo seguro)
            pdf.line(255, y0+12, 270, y0+12)
            pdf.rect(270, y0+2, 15, 20)
            
            # INTENTO DE DIBUJAR CÍRCULO SEGURO
            try:
                # Detectar método disponible en FPDF
                if hasattr(pdf, 'ellipse'):
                    pdf.ellipse(272.5, y0+7, 10, 10)
                elif hasattr(pdf, 'circle'):
                    pdf.circle(277.5, y0+12, 5)
                else:
                    pdf.set_font('Arial', 'B', 12)
                    pdf.text(274, y0+15, "(M)")
            except:
                pdf.text(274, y0+15, "M")
                
            pdf.set_font('Arial', '', 8)
            pdf.text(273, y0+25, "kWh")

            # Tierra General
            pdf.set_draw_color(0, 150, 0)
            pdf.line(40, y0+40, 250, y0+40)
            pdf.line(47, y0+25, 47, y0+40) # Bajante Panel
            pdf.line(185, y0+30, 185, y0+40) # Bajante Inv
            # Simbolo Tierra (Función auxiliar)
            pdf.line(150, y0+40, 150, y0+45)
            pdf.line(148, y0+45, 152, y0+45)
            pdf.line(149, y0+46, 151, y0+46)
            pdf.text(152, y0+48, "SPT")

            # --- PÁGINA 4: BOM (PRESUPUESTO) ---
            pdf.add_page('P')
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "4. LISTA DE MATERIALES Y COSTOS", 0, 1, 'C')
            pdf.ln(10)
            
            pdf.set_fill_color(220, 230, 240)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(110, 10, "Item", 1, 0, 'C', True)
            pdf.cell(20, 10, "Cant.", 1, 0, 'C', True)
            pdf.cell(30, 10, "Unitario", 1, 0, 'C', True)
            pdf.cell(30, 10, "Total", 1, 1, 'C', True)
            
            pdf.set_font("Arial", "", 10)
            
            items_bom = [
                (f"Modulo FV {dato_mod['Modelo']}", n_mod, dato_mod['Precio']),
                (f"Inversor {dato_inv['Modelo']}", 1, dato_inv['Precio']),
                ("Estructura Soporte Alum.", n_mod, 150000),
                ("BOS (Cables, DPS, Tableros)", 1, costo_bos/pot_dc), # Aprox
                ("Ingeniería y Mano de Obra", 1, costo_mo)
            ]
            
            total_proy = 0
            for desc, cant, unit in items_bom:
                sub = cant * unit
                total_proy += sub
                pdf.cell(110, 10, limpiar(desc[:60]), 1)
                pdf.cell(20, 10, str(int(cant)), 1, 0, 'C')
                pdf.cell(30, 10, f"${unit/1e6:.1f}M", 1, 0, 'R')
                pdf.cell(30, 10, f"${sub/1e6:.1f}M", 1, 1, 'R')
            
            pdf.set_font("Arial", "B", 12)
            pdf.cell(160, 10, "TOTAL PROYECTO (COP)", 1, 0, 'R')
            pdf.cell(30, 10, f"${total_proy/1e6:.1f}M", 1, 1, 'R')
            
            pdf.ln(20)
            pdf.set_font("Arial", "I", 8)
            pdf.multi_cell(0, 5, "Generado por SIMU ING. Precios estimados para Colombia 2026. Validez 30 dias.")

            # Generar Archivo
            pdf_bytes = pdf.output(dest='S')
            if isinstance(pdf_bytes, str): pdf_bytes = pdf_bytes.encode('latin-1')
            
            st.download_button(
                label="📥 DESCARGAR REPORTE SIMU ING",
                data=pdf_bytes,
                file_name=f"SIMU_ING_{limpiar(cliente)}.pdf",
                mime="application/pdf"
            )
            st.success("✅ Documento generado con éxito")

        except Exception as e:
            st.error(f"Error generando reporte: {e}")
