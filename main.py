import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import requests
import pydeck as pdk
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA (ESTA LÍNEA SIEMPRE DEBE SER LA PRIMERA)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="CESAR CM Solar Suite",
    page_icon="☀️",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. INICIALIZACIÓN DE VARIABLES DE ESTADO (SESSION STATE)
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

# Función auxiliar para dibujar símbolo de tierra en el PDF
def dibujar_tierra(pdf, x, y):
    pdf.line(x, y, x, y+2) # Bajante
    pdf.line(x-2, y+2, x+2, y+2) # Línea larga
    pdf.line(x-1.2, y+2.8, x+1.2, y+2.8) # Línea media
    pdf.line(x-0.5, y+3.6, x+0.5, y+3.6) # Línea corta

# -----------------------------------------------------------------------------
# 4. BASE DE DATOS
# -----------------------------------------------------------------------------
def cargar_biblioteca():
    data_ciudades = {
        "Departamento": ["Amazonas", "Antioquia", "Antioquia", "Arauca", "Atlántico", "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Bogotá D.C.", "Guainía", "Guaviare", "Huila", "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda", "San Andrés", "Santander", "Sucre", "Tolima", "Valle del Cauca", "Vaupés", "Vichada"],
        "Ciudad": ["Leticia", "Medellín", "Rionegro", "Arauca", "Barranquilla", "Cartagena", "Tunja", "Manizales", "Florencia", "Yopal", "Popayán", "Valledupar", "Quibdó", "Montería", "Girardot", "Bogotá", "Inírida", "San José del Guaviare", "Neiva", "Riohacha", "Santa Marta", "Villavicencio", "Pasto", "Cúcuta", "Mocoa", "Armenia", "Pereira", "San Andrés", "Bucaramanga", "Sincelejo", "Ibagué", "Cali", "Mitú", "Puerto Carreño"],
        "HSP": [4.5, 4.8, 4.7, 5.2, 5.5, 5.3, 4.6, 4.2, 4.0, 4.9, 4.5, 5.6, 3.8, 5.1, 4.8, 4.2, 4.6, 4.5, 5.2, 6.0, 5.5, 4.7, 4.3, 5.0, 3.9, 4.4, 4.5, 5.2, 5.0, 5.2, 4.9, 4.8, 4.4, 5.1]
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

password = st.sidebar.text_input("🔑 Contraseña de Acceso", type="password")
if password != "SOLAR2025":
    st.sidebar.error("⚠️ Acceso Bloqueado")
    st.stop()

st.sidebar.success("✅ Sistema Activo")
st.sidebar.markdown("---")

tipo_sistema = st.sidebar.selectbox("Tipo de Sistema", ["On-Grid (Conectado a Red)", "Off-Grid (Autónomo)", "Bombeo Solar"])

st.sidebar.subheader("🌍 Configuración de Mapa")
ciudad_ref = st.sidebar.selectbox("Centrar Mapa en:", list(coordenadas_ciudades.keys()))
lat_atlas = st.sidebar.number_input("Latitud Manual", value=coordenadas_ciudades.get(ciudad_ref, [4.5, -74])[0], format="%.4f")
lon_atlas = st.sidebar.number_input("Longitud Manual", value=coordenadas_ciudades.get(ciudad_ref, [4.5, -74])[1], format="%.4f")
tipo_mapa = st.sidebar.radio("Estilo de Mapa:", ["Satélite Híbrido", "Satélite Puro", "Relieve / Topográfico", "Calles / Tráfico"])

# -----------------------------------------------------------------------------
# 6. INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------
st.title("CESAR CM INGENIERÍA - SUITE SOLAR v3.0")
st.markdown("---")

col_cli1, col_cli2 = st.columns([2, 1])
with col_cli1: cliente = st.text_input("Nombre del Cliente / Proyecto", "Cliente General")
with col_cli2: fecha_proy = st.date_input("Fecha del Proyecto", datetime.now())

st.header("📍 1. Ubicación y Recurso Solar")
c1, c2, c3 = st.columns(3)
with c1: depto = st.selectbox("Departamento", df_ciudades["Departamento"].unique())
with c2: 
    ciudades_filtradas = df_ciudades[df_ciudades["Departamento"] == depto]
    ciudad = st.selectbox("Ciudad", ciudades_filtradas["Ciudad"])
with c3:
    try: hsp = ciudades_filtradas[ciudades_filtradas["Ciudad"] == ciudad].iloc[0]["HSP"]
    except: hsp = 4.5
    st.metric("HSP (Horas Sol Pico)", f"{hsp} kWh/m²")

coords_mapa = coordenadas_ciudades.get(ciudad, [lat_atlas, lon_atlas])
lat_map, lon_map = coords_mapa[0], coords_mapa[1]
estilos_google = {"Satélite Híbrido": "y", "Satélite Puro": "s", "Relieve / Topográfico": "p", "Calles / Tráfico": "m"}

st.pydeck_chart(pdk.Deck(
    map_style=None,
    initial_view_state=pdk.ViewState(latitude=lat_map, longitude=lon_map, zoom=16, pitch=45),
    layers=[
        pdk.Layer("TileLayer", data=None, get_tile_data=f"https://mt1.google.com/vt/lyrs={estilos_google[tipo_mapa]}&x={{x}}&y={{y}}&z={{z}}", opacity=1),
        pdk.Layer("IconLayer", pd.DataFrame([{"lat": lat_map, "lon": lon_map, "icon": {"url": "https://img.icons8.com/color/100/marker--v1.png", "width": 128, "height": 128, "anchorY": 128}}]), get_icon="icon", get_size=4, size_scale=15, get_position="[lon, lat]")
    ]
))

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
tab1, tab2, tab3 = st.tabs(["📐 Dimensionamiento Energético", "⚡ Diseño Eléctrico (RETIE)", "💰 Financiero & Reporte PDF"])

with tab1:
    st.subheader("Cálculo de Demanda y Generación")
    cd1, cd2 = st.columns(2)
    consumo = cd1.number_input("Consumo Promedio Mensual (kWh)", value=500, step=10)
    temp = cd2.number_input("Temperatura Ambiente Promedio (°C)", value=28.0)

    if consumo > 0:
        gen_panel_simple = (dato_panel["Potencia"] / 1000) * hsp * 30 * 0.80
        n_paneles_sugerido = int(consumo / gen_panel_simple) + 1
        st.info(f"💡 Paneles sugeridos: **{n_paneles_sugerido}**")
        
        val_slider = st.slider("Ajustar Cantidad Real de Paneles", 1, 100, n_paneles_sugerido)
        st.session_state.n_paneles_real = val_slider
        
        potencia_sistema_kw = (st.session_state.n_paneles_real * dato_panel["Potencia"]) / 1000
        st.session_state.potencia_sistema_kw = potencia_sistema_kw
        
        gen_dia, ef = simulacion_pvsyst(potencia_sistema_kw, hsp, temp)
        st.session_state.gen_total_mensual = gen_dia * 30
        
        r1, r2, r3 = st.columns(3)
        r1.metric("Potencia DC", f"{potencia_sistema_kw*1000:.0f} Wp")
        r2.metric("Generación", f"{st.session_state.gen_total_mensual:.0f} kWh/mes")
        r3.metric("PR Global", f"{ef*100:.1f}%")
        
        df_graf = pd.DataFrame({"Mes": range(1,13), "Consumo": [consumo]*12, "Generación": [st.session_state.gen_total_mensual]*12})
        st.bar_chart(df_graf.set_index("Mes"), color=["#FF4B4B", "#00CC96"])

with tab2:
    st.subheader("Validación de Series")
    n_paneles = st.session_state.n_paneles_real
    if n_paneles > 0:
        n_serie = st.slider("Paneles por Serie", 1, 20, min(n_paneles, 15))
        voc = dato_panel["Voc"] * n_serie
        
        c_e1, c_e2 = st.columns(2)
        c_e1.metric("Voc String", f"{voc:.1f} V")
        if voc > dato_inv["Vmax"]: c_e2.error(f"🛑 PELIGRO: > {dato_inv['Vmax']}V")
        elif voc < dato_inv["Vmin"]: c_e2.warning("⚠️ Voltaje Bajo")
        else: 
            c_e2.success("✅ Configuración Segura")
            st.progress(voc / dato_inv["Vmax"])
            
        corriente_ac = dato_inv["Potencia"] / 220
        breaker = 20 if corriente_ac*1.25 < 20 else 40
        st.info(f"Breaker AC Recomendado: {breaker}A | Cable 10 AWG")

with tab3:
    col_f1, col_f2 = st.columns(2)
    tarifa = col_f1.number_input("Tarifa ($/kWh)", value=850)
    costo_proy = col_f1.number_input("Costo Proyecto", value=int((st.session_state.n_paneles_real*dato_panel["Precio"])+dato_inv["Precio"]+3000000))
    
    ahorro = st.session_state.gen_total_mensual * tarifa
    if ahorro > 0:
        roi = costo_proy / (ahorro * 12)
        col_f2.metric("ROI", f"{roi:.1f} Años")
        col_f2.metric("Ahorro Mes", f"${ahorro:,.0f}")
        
    flujo = [-costo_proy]
    for _ in range(25): flujo.append(flujo[-1] + (ahorro*12*1.05))
    st.line_chart(flujo)

    st.markdown("---")
    if st.button("Generar Informe Técnico PDF", use_container_width=True):
        try:
            # Gráfica temporal
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(flujo, color='green')
            ax.set_title("Flujo de Caja (25 Años)")
            ax.grid(True, linestyle='--', alpha=0.5)
            fig.savefig("temp_roi.png", bbox_inches='tight')
            plt.close(fig)

            # PDF INIT
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # --- PÁGINAS 1 y 2 (RESUMEN Y FINANCIERO) ---
            pdf.add_page()
            if os.path.exists("logo.png"): 
                try: pdf.image("logo.png", x=10, y=10, w=40)
                except: pass
            
            pdf.ln(20)
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'MEMORIA DE CALCULO - SISTEMA SOLAR FV', 0, 1, 'C')
            pdf.ln(5)
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 8, f'Cliente: {limpiar(cliente)} | Ubicacion: {limpiar(ciudad)}', 0, 1, 'C')
            pdf.ln(10)
            
            pdf.set_font('Arial', '', 11)
            pdf.multi_cell(0, 7, f"Generador: {st.session_state.n_paneles_real} x {dato_panel['Referencia']}\nInversor: {dato_inv['Referencia']}\nGeneracion Estimada: {st.session_state.gen_total_mensual:.0f} kWh/mes")
            
            pdf.add_page()
            pdf.cell(0, 10, 'ANALISIS FINANCIERO', 0, 1, 'L')
            if os.path.exists("temp_roi.png"): pdf.image("temp_roi.png", x=10, w=190)
            
            # --- PÁGINA 3: DIAGRAMA UNIFILAR PROFESIONAL (TIPO PLANO CAD) ---
            pdf.add_page('L') # Página Horizontal
            
            # MARCO DEL PLANO (Borde)
            pdf.set_line_width(0.5)
            pdf.rect(5, 5, 287, 200) # Borde Exterior
            pdf.rect(10, 10, 277, 190) # Borde Interior
            
            # CAJETÍN (RÓTULO) INFERIOR
            y_cajetin = 175
            pdf.line(10, y_cajetin, 287, y_cajetin)
            
            pdf.set_font('Arial', 'B', 8)
            pdf.set_xy(15, y_cajetin + 2)
            pdf.cell(50, 5, "PROYECTO:", 0, 1)
            pdf.set_font('Arial', '', 8)
            pdf.set_xy(15, y_cajetin + 7)
            pdf.cell(50, 5, limpiar(cliente), 0, 0)
            
            pdf.set_xy(80, y_cajetin + 2)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(50, 5, "UBICACION:", 0, 1)
            pdf.set_xy(80, y_cajetin + 7)
            pdf.set_font('Arial', '', 8)
            pdf.cell(50, 5, f"{limpiar(ciudad)}", 0, 0)

            pdf.set_xy(150, y_cajetin + 2)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(50, 5, "DISENO:", 0, 1)
            pdf.set_xy(150, y_cajetin + 7)
            pdf.set_font('Arial', '', 8)
            pdf.cell(50, 5, "CESAR CM INGENIERIA", 0, 0)

            pdf.set_xy(220, y_cajetin + 2)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(30, 5, "FECHA:", 0, 0)
            pdf.cell(30, 5, "PLANO:", 0, 1)
            pdf.set_xy(220, y_cajetin + 7)
            pdf.set_font('Arial', '', 8)
            pdf.cell(30, 5, str(datetime.now().date()), 0, 0)
            pdf.cell(30, 5, "EL-01", 0, 0)

            # --- DIBUJO DEL DIAGRAMA ---
            y_base = 80
            x_start = 30
            
            # 1. ARREGLO FV
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.3)
            
            for i in range(3):
                offset_x = i * 15
                pdf.rect(x_start + offset_x, y_base, 12, 20)
                pdf.line(x_start + offset_x, y_base+6, x_start + offset_x + 12, y_base+6)
                pdf.line(x_start + offset_x, y_base+13, x_start + offset_x + 12, y_base+13)
            
            pdf.set_font('Arial', 'B', 8)
            pdf.text(x_start, y_base - 5, "GENERADOR FV")
            pdf.set_font('Arial', '', 7)
            pdf.text(x_start, y_base - 2, f"{st.session_state.n_paneles_real} x {dato_panel['Potencia']}W")
            
            # Conexión DC
            pdf.set_draw_color(200, 0, 0) # Rojo Positivo
            pdf.line(x_start + 36, y_base + 2, 90, y_base + 2) 
            pdf.text(70, y_base + 1, "DC (+)")
            
            pdf.set_draw_color(0, 0, 0) # Negro Negativo
            pdf.line(x_start + 36, y_base + 18, 90, y_base + 18)
            pdf.text(70, y_base + 17, "DC (-)")

            # Tierra Paneles
            pdf.set_draw_color(0, 150, 0) # Verde Tierra
            pdf.line(x_start + 6, y_base + 20, x_start + 6, y_base + 30)
            pdf.line(x_start + 6, y_base + 30, 250, y_base + 30)
            pdf.text(x_start + 7, y_base + 28, "T")

            # 2. CAJA DE PROTECCIONES DC
            pdf.set_draw_color(0, 0, 0)
            pdf.rect(90, y_base - 10, 40, 40)
            pdf.set_font('Arial', 'B', 7)
            pdf.text(92, y_base - 7, "TABLERO DC")
            
            # Fusibles
            pdf.rect(95, y_base, 8, 4)
            pdf.line(95, y_base+2, 103, y_base+2)
            pdf.text(96, y_base-1, "Fus")
            
            pdf.rect(95, y_base+16, 8, 4)
            pdf.line(95, y_base+18, 103, y_base+18)
            
            # DPS
            pdf.rect(110, y_base+8, 6, 10)
            pdf.text(111, y_base+7, "DPS")
            pdf.line(113, y_base+18, 113, y_base+30)
            
            # Salida DC
            pdf.set_draw_color(200, 0, 0)
            pdf.line(130, y_base + 2, 150, y_base + 2)
            pdf.set_draw_color(0, 0, 0)
            pdf.line(130, y_base + 18, 150, y_base + 18)

            # 3. INVERSOR
            pdf.rect(150, y_base - 5, 30, 30)
            pdf.set_font('Arial', 'B', 8)
            pdf.text(152, y_base, "INVERSOR")
            pdf.set_font('Arial', '', 6)
            pdf.text(152, y_base + 5, f"{dato_inv['Referencia'][:15]}")
            
            pdf.set_draw_color(0, 150, 0) # Tierra
            pdf.line(165, y_base + 25, 165, y_base + 30)
            
            # Salida AC
            pdf.set_draw_color(0, 0, 0)
            pdf.line(180, y_base + 10, 200, y_base + 10)
            pdf.line(180, y_base + 15, 200, y_base + 15)
            pdf.text(185, y_base + 9, "L")
            pdf.text(185, y_base + 14, "N")

            # 4. TABLERO AC
            pdf.rect(200, y_base - 5, 30, 30)
            pdf.set_font('Arial', 'B', 7)
            pdf.text(202, y_base - 2, "TABLERO AC")
            
            pdf.rect(205, y_base + 8, 5, 10) # Breaker
            pdf.line(205, y_base+13, 210, y_base+8)
            pdf.text(205, y_base + 7, "Brk")
            
            pdf.line(230, y_base + 10, 250, y_base + 10)
            pdf.line(230, y_base + 15, 250, y_base + 15)

            # 5. MEDIDOR (SIN CIRCLE, USANDO ELLIPSE PARA COMPATIBILIDAD)
            pdf.rect(250, y_base, 20, 20)
            # Solución Universal para círculos en FPDF
            pdf.ellipse(254, y_base + 5, 12, 12)
            
            pdf.set_font('Arial', 'B', 10)
            pdf.text(256, y_base + 12, "kWh")
            
            # Red
            pdf.line(270, y_base + 10, 280, y_base + 10)
            pdf.line(270, y_base + 15, 280, y_base + 15)
            pdf.text(275, y_base + 8, "RED")
            
            # TIERRA GENERAL
            pdf.set_draw_color(0, 150, 0)
            pdf.set_line_width(0.5)
            pdf.line(30, y_base + 30, 270, y_base + 30)
            dibujar_tierra(pdf, 150, y_base + 30)
            pdf.set_font('Arial', 'B', 6)
            pdf.text(152, y_base + 34, "SPT")

            # Output
            pdf_content = pdf.output(dest='S')
            if isinstance(pdf_content, str): pdf_bytes = pdf_content.encode('latin-1')
            else: pdf_bytes = pdf_content

            st.download_button("📥 DESCARGAR INFORME TÉCNICO", pdf_bytes, f"Plano_{limpiar(cliente)}.pdf", "application/pdf")
            st.success("✅ Informe Generado Correctamente.")

        except Exception as e:
            st.error(f"Error: {e}")
