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
# Esto evita el error "NameError" cuando cambias de pestaña y se borran los datos
# -----------------------------------------------------------------------------
if 'n_paneles_real' not in st.session_state:
    st.session_state.n_paneles_real = 10
if 'gen_total_mensual' not in st.session_state:
    st.session_state.gen_total_mensual = 0.0
if 'potencia_sistema_kw' not in st.session_state:
    st.session_state.potencia_sistema_kw = 0.0

# -----------------------------------------------------------------------------
# 3. FUNCIONES AUXILIARES (LÓGICA DEL PROGRAMA)
# -----------------------------------------------------------------------------

def limpiar(texto):
    """
    Limpia el texto de caracteres especiales para que FPDF no falle.
    Convierte todo a compatible con Latin-1.
    """
    if texto is None: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def simulacion_pvsyst(potencia_dc_kw, hsp_sitio, temp_amb_grados):
    """
    Simula la producción de energía considerando pérdidas por calor y sistema.
    Fórmula basada en estándares de PVSyst simplificado.
    """
    # Pérdidas por Temperatura (aprox 0.4% por cada grado arriba de 25°C)
    perdida_temp = 0.004 * (temp_amb_grados - 25)
    if perdida_temp < 0: perdida_temp = 0

    # Pérdidas del Sistema (Cables 2%, Suciedad 3%, Inversor 3%, Desajuste 3%, Otros 3%) = ~14%
    perdidas_sistema = 0.14

    # Eficiencia Total (Performance Ratio - PR)
    eficiencia_global = 1 - (perdidas_sistema + perdida_temp)

    # Cálculo de Energía Diaria: Potencia (kW) * Horas Sol (h) * Eficiencia
    generacion_diaria = potencia_dc_kw * hsp_sitio * eficiencia_global
    
    return generacion_diaria, eficiencia_global

# -----------------------------------------------------------------------------
# 4. BASE DE DATOS (CIUDADES Y EQUIPOS)
# Se define aquí para asegurar que siempre esté cargada
# -----------------------------------------------------------------------------
def cargar_biblioteca():
    # DATOS DE CIUDADES COLOMBIA
    data_ciudades = {
        "Departamento": [
            "Amazonas", "Antioquia", "Antioquia", "Arauca", "Atlántico", "Bolívar", "Boyacá", "Caldas", 
            "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Bogotá D.C.", 
            "Guainía", "Guaviare", "Huila", "La Guajira", "Magdalena", "Meta", "Nariño", 
            "Norte de Santander", "Putumayo", "Quindío", "Risaralda", "San Andrés", "Santander", 
            "Sucre", "Tolima", "Valle del Cauca", "Vaupés", "Vichada"
        ],
        "Ciudad": [
            "Leticia", "Medellín", "Rionegro", "Arauca", "Barranquilla", "Cartagena", "Tunja", "Manizales", 
            "Florencia", "Yopal", "Popayán", "Valledupar", "Quibdó", "Montería", "Girardot", "Bogotá", 
            "Inírida", "San José del Guaviare", "Neiva", "Riohacha", "Santa Marta", "Villavicencio", "Pasto", 
            "Cúcuta", "Mocoa", "Armenia", "Pereira", "San Andrés", "Bucaramanga", 
            "Sincelejo", "Ibagué", "Cali", "Mitú", "Puerto Carreño"
        ],
        "HSP": [
            4.5, 4.8, 4.7, 5.2, 5.5, 5.3, 4.6, 4.2, 
            4.0, 4.9, 4.5, 5.6, 3.8, 5.1, 4.8, 4.2, 
            4.6, 4.5, 5.2, 6.0, 5.5, 4.7, 4.3, 
            5.0, 3.9, 4.4, 4.5, 5.2, 5.0, 
            5.2, 4.9, 4.8, 4.4, 5.1
        ]
    }
    
    # DATOS DE PANELES SOLARES
    data_paneles = {
        "Referencia": ["Panel 450W Monocristalino", "Panel 550W Bifacial", "Panel 600W Industrial"],
        "Potencia": [450, 550, 600],
        "Voc": [41.5, 49.6, 41.7], # Voltaje Circuito Abierto
        "Isc": [13.4, 13.9, 18.1], # Corriente Cortocircuito
        "Precio": [550000, 720000, 850000] 
    }
    
    # DATOS DE INVERSORES
    data_inversores = {
        "Referencia": ["Microinversor 1.2kW", "Inversor 3kW", "Inversor 5kW Híbrido", "Inversor 10kW Trifásico"],
        "Potencia": [1200, 3000, 5000, 10000],
        "Vmin": [20, 80, 120, 180],   # Voltaje Mínimo de Arranque (MPPT)
        "Vmax": [60, 600, 600, 1000], # Voltaje Máximo Permitido
        "Precio": [1200000, 2500000, 4500000, 7000000] 
    }
    return pd.DataFrame(data_ciudades), pd.DataFrame(data_paneles), pd.DataFrame(data_inversores)

# Ejecutamos la carga
df_ciudades, df_modulos, df_inversores = cargar_biblioteca()

# Coordenadas exactas para el mapa (Diccionario Hardcoded para velocidad)
coordenadas_ciudades = {
    "Bucaramanga": [7.1193, -73.1227], "Bogotá": [4.7110, -74.0721], "Medellín": [6.2442, -75.5812], 
    "Cali": [3.4516, -76.5320], "Barranquilla": [10.9685, -74.7813], "San José del Guaviare": [2.5729, -72.6378], 
    "Colombia": [4.5709, -74.2973], "Leticia": [-4.2153, -69.9406], "Villavicencio": [4.1420, -73.6266]
}

# -----------------------------------------------------------------------------
# 5. BARRA LATERAL (SIDEBAR) - SEGURIDAD Y CONFIGURACIÓN
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/solar-panel.png", width=80)
st.sidebar.title("Configuración")

# Sistema de Contraseña
password = st.sidebar.text_input("🔑 Contraseña de Acceso", type="password")
if password != "SOLAR2025":
    st.sidebar.error("⚠️ Acceso Bloqueado")
    st.title("Sistema Bloqueado")
    st.info("Por favor ingrese la contraseña correcta en el menú lateral.")
    st.stop() # Detiene la ejecución si la contraseña es incorrecta

st.sidebar.success("✅ Sistema Activo")
st.sidebar.markdown("---")

# Selectores Globales
tipo_sistema = st.sidebar.selectbox(
    "Tipo de Sistema",
    ["On-Grid (Conectado a Red)", "Off-Grid (Autónomo)", "Bombeo Solar"]
)

# Configuración del Mapa
st.sidebar.subheader("🌍 Configuración de Mapa")
ciudad_ref = st.sidebar.selectbox("Centrar Mapa en:", list(coordenadas_ciudades.keys()))
lat_atlas = st.sidebar.number_input("Latitud Manual", value=coordenadas_ciudades.get(ciudad_ref, [4.5, -74])[0], format="%.4f")
lon_atlas = st.sidebar.number_input("Longitud Manual", value=coordenadas_ciudades.get(ciudad_ref, [4.5, -74])[1], format="%.4f")

tipo_mapa = st.sidebar.radio(
    "Estilo de Mapa:",
    ["Satélite Híbrido", "Satélite Puro", "Relieve / Topográfico", "Calles / Tráfico"]
)

# -----------------------------------------------------------------------------
# 6. INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------
st.title("CESAR CM INGENIERÍA - SUITE SOLAR v3.0")
st.markdown("---")

# Datos del Cliente
col_cli1, col_cli2 = st.columns([2, 1])
with col_cli1:
    cliente = st.text_input("Nombre del Cliente / Proyecto", "Cliente General")
with col_cli2:
    fecha_proy = st.date_input("Fecha del Proyecto", datetime.now())

# Selección de Ubicación
st.header("📍 1. Ubicación y Recurso Solar")
c1, c2, c3 = st.columns(3)
with c1: 
    depto = st.selectbox("Departamento", df_ciudades["Departamento"].unique())
with c2: 
    ciudades_filtradas = df_ciudades[df_ciudades["Departamento"] == depto]
    ciudad = st.selectbox("Ciudad", ciudades_filtradas["Ciudad"])
with c3:
    # Obtener HSP Automático
    try:
        hsp = ciudades_filtradas[ciudades_filtradas["Ciudad"] == ciudad].iloc[0]["HSP"]
    except:
        hsp = 4.5
    st.metric("HSP (Horas Sol Pico)", f"{hsp} kWh/m²")

# VISUALIZACIÓN DE MAPA (PYDECK)
coords_mapa = coordenadas_ciudades.get(ciudad, [lat_atlas, lon_atlas])
lat_map, lon_map = coords_mapa[0], coords_mapa[1]

# Definimos el estilo del mapa para Google Maps
estilos_google = {
    "Satélite Híbrido": "y",
    "Satélite Puro": "s",
    "Relieve / Topográfico": "p",
    "Calles / Tráfico": "m"
}

# Capa de Mapa
layer_mapa = pdk.Layer(
    "TileLayer",
    data=None,
    get_tile_data=f"https://mt1.google.com/vt/lyrs={estilos_google[tipo_mapa]}&x={{x}}&y={{y}}&z={{z}}",
    opacity=1
)

# Capa de Marcador (Gota Roja)
icon_data = {
    "url": "https://img.icons8.com/color/100/marker--v1.png",
    "width": 128, "height": 128, "anchorY": 128
}
layer_icono = pdk.Layer(
    "IconLayer",
    pd.DataFrame([{"lat": lat_map, "lon": lon_map, "icon": icon_data}]),
    get_icon="icon",
    get_size=4,
    size_scale=15,
    get_position="[lon, lat]",
    pickable=True
)

st.pydeck_chart(pdk.Deck(
    map_style=None,
    initial_view_state=pdk.ViewState(latitude=lat_map, longitude=lon_map, zoom=16, pitch=45),
    layers=[layer_mapa, layer_icono],
    tooltip={"text": f"{ciudad}"}
))

# Selección de Equipos
st.header("⚙️ 2. Selección de Equipos")
ce1, ce2 = st.columns(2)
with ce1: 
    ref_panel = st.selectbox("Panel Solar", df_modulos["Referencia"])
    dato_panel = df_modulos[df_modulos["Referencia"] == ref_panel].iloc[0]
    st.caption(f"Potencia: {dato_panel['Potencia']}W | Voc: {dato_panel['Voc']}V")
with ce2: 
    ref_inv = st.selectbox("Inversor", df_inversores["Referencia"])
    dato_inv = df_inversores[df_inversores["Referencia"] == ref_inv].iloc[0]
    st.caption(f"Potencia: {dato_inv['Potencia']}W | Rango MPPT: {dato_inv['Vmin']}-{dato_inv['Vmax']}V")

# -----------------------------------------------------------------------------
# 7. PESTAÑAS DE CÁLCULO (CORE DEL PROGRAMA)
# -----------------------------------------------------------------------------
st.markdown("---")
tab1, tab2, tab3 = st.tabs(["📐 Dimensionamiento Energético", "⚡ Diseño Eléctrico (RETIE)", "💰 Financiero & Reporte PDF"])

# --- PESTAÑA 1: DIMENSIONAMIENTO ---
with tab1:
    st.subheader("Cálculo de Demanda y Generación")
    col_dim1, col_dim2 = st.columns(2)
    
    with col_dim1:
        consumo = st.number_input("Consumo Promedio Mensual (kWh)", value=500, step=10)
    with col_dim2:
        temp = st.number_input("Temperatura Ambiente Promedio (°C)", value=28.0)

    if consumo > 0:
        # 1. Estimación Inicial
        gen_panel_simple = (dato_panel["Potencia"] / 1000) * hsp * 30 * 0.80 # 80% eficiencia global estimada
        n_paneles_sugerido = int(consumo / gen_panel_simple) + 1
        
        st.info(f"💡 Según tu consumo de {consumo} kWh, necesitas aproximadamente **{n_paneles_sugerido} paneles**.")
        
        # 2. Ajuste Fino (Usuario decide)
        val_slider = st.slider("Ajustar Cantidad Real de Paneles a Instalar", 1, 100, n_paneles_sugerido)
        
        # GUARDAMOS EN SESSION STATE PARA USAR EN OTRAS PESTAÑAS
        st.session_state.n_paneles_real = val_slider
        
        # 3. Cálculo Profesional (PVSyst)
        potencia_sistema_kw = (st.session_state.n_paneles_real * dato_panel["Potencia"]) / 1000
        st.session_state.potencia_sistema_kw = potencia_sistema_kw
        
        gen_dia_real, eficiencia_real = simulacion_pvsyst(potencia_sistema_kw, hsp, temp)
        gen_mes_real = gen_dia_real * 30
        st.session_state.gen_total_mensual = gen_mes_real
        
        # 4. Resultados
        res1, res2, res3 = st.columns(3)
        res1.metric("Potencia Instalada (Wp)", f"{potencia_sistema_kw*1000:.0f} Wp")
        res2.metric("Generación Real Estimada", f"{gen_mes_real:.0f} kWh/mes", delta=f"{gen_mes_real-consumo:.0f} vs Consumo")
        res3.metric("Performance Ratio (PR)", f"{eficiencia_real*100:.1f}%")
        
        # 5. Gráfica Comparativa
        st.subheader("📊 Balance Energético")
        datos_grafica = pd.DataFrame({
            "Mes": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
            "Consumo Red": [consumo] * 12,
            "Generación Solar": [gen_mes_real] * 12
        })
        st.bar_chart(datos_grafica.set_index("Mes"), color=["#FF4B4B", "#00CC96"])

# --- PESTAÑA 2: ELÉCTRICO ---
with tab2:
    st.subheader("Validación de Series (Strings) y Protecciones")
    
    # Recuperamos el número de paneles de la pestaña 1
    n_paneles_totales = st.session_state.n_paneles_real
    
    if n_paneles_totales > 0:
        # Configuración de Series
        n_serie = st.slider("Paneles por Serie (String)", 1, 20, min(n_paneles_totales, 15))
        n_paralelo = n_paneles_totales / n_serie
        
        # Cálculos de Voltaje
        voc_string = dato_panel["Voc"] * n_serie
        vmp_string = (dato_panel["Voc"] * 0.85) * n_serie # Estimado Vmp
        
        col_elec1, col_elec2 = st.columns(2)
        
        with col_elec1:
            st.metric("Voltaje Voc del String (Circuito Abierto)", f"{voc_string:.1f} V")
            st.metric("Límite Máximo del Inversor", f"{dato_inv['Vmax']} V")
        
        with col_elec2:
            # Validación de Seguridad
            if voc_string > dato_inv["Vmax"]:
                st.error(f"🛑 PELIGRO: El voltaje {voc_string:.1f}V quema el inversor (> {dato_inv['Vmax']}V)")
            elif voc_string < dato_inv["Vmin"]:
                st.warning(f"⚠️ VOLTAJE BAJO: {voc_string:.1f}V no alcanza a encender el inversor (Min: {dato_inv['Vmin']}V)")
            else:
                st.success(f"✅ CONFIGURACIÓN CORRECTA: El voltaje está dentro del rango operativo.")
                st.progress(voc_string / dato_inv["Vmax"])
        
        st.divider()
        st.subheader("🛠️ Materiales y Protecciones AC (RETIE)")
        
        # Cálculo de Protecciones
        corriente_salida_inv = dato_inv["Potencia"] / 220 # Asumiendo 220V Bifásico/Trifásico
        breaker_sugerido = corriente_salida_inv * 1.25 # Factor de seguridad del 25%
        
        # Redondeo a comerciales comunes (20, 32, 40, 63)
        if breaker_sugerido <= 20: breaker_com = 20
        elif breaker_sugerido <= 32: breaker_com = 32
        elif breaker_sugerido <= 40: breaker_com = 40
        else: breaker_com = 63
        
        c_mat1, c_mat2 = st.columns(2)
        with c_mat1:
            st.info(f"**Breaker AC Recomendado:** {breaker_com} A")
            st.info(f"**Cableado AC Sugerido:** Calibre 10 AWG (THHN/THWN-2)")
        with c_mat2:
            st.info(f"**Protección DC:** Fusibles 15A 1000V + DPS DC 1000V")
            st.info(f"**Puesta a Tierra:** Cable desnudo 8 AWG mínimo")

# --- PESTAÑA 3: FINANCIERO Y PDF ---
with tab3:
    st.subheader("Análisis de Rentabilidad")
    
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        tarifa = st.number_input("Tarifa Energía ($/kWh)", value=850)
        # Costo estimado automático si el usuario no pone nada
        costo_auto = (st.session_state.n_paneles_real * dato_panel["Precio"]) + dato_inv["Precio"] + 3000000 # 3M en accesorios/MO
        costo_proyecto = st.number_input("Costo Total del Proyecto ($)", value=int(costo_auto))
    
    with col_fin2:
        ahorro_mensual = st.session_state.gen_total_mensual * tarifa
        if ahorro_mensual > 0:
            retorno_anios = costo_proyecto / (ahorro_mensual * 12)
            st.metric("Retorno de Inversión (ROI)", f"{retorno_anios:.1f} Años")
            st.metric("Ahorro Mensual en Factura", f"${ahorro_mensual:,.0f} COP")
        else:
            retorno_anios = 0
            st.warning("Calcula primero la generación en la Pestaña 1.")

    # Gráfica de Retorno de Inversión
    flujo_caja = []
    saldo = -costo_proyecto
    for i in range(26): # 25 años
        flujo_caja.append(saldo)
        saldo += (ahorro_mensual * 12 * 1.05) # 5% incremento tarifa anual
    
    st.line_chart(pd.DataFrame({"Año": range(26), "Saldo Acumulado": flujo_caja}).set_index("Año"))

    st.markdown("---")
    st.subheader("📄 Generación de Entregables")
    
    if st.button("Generar Informe Técnico PDF", use_container_width=True):
        try:
            # 1. Generar imágenes temporales para el PDF
            # Gráfica ROI
            fig1, ax1 = plt.subplots(figsize=(10, 4))
            ax1.plot(flujo_caja, color='green', linewidth=2)
            ax1.set_title("Proyección de Retorno de Inversión (25 Años)")
            ax1.set_xlabel("Años")
            ax1.set_ylabel("Flujo de Caja ($)")
            ax1.grid(True, linestyle='--', alpha=0.5)
            fig1.savefig("temp_roi.png", bbox_inches='tight')
            plt.close(fig1)

            # 2. Inicializar PDF
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # --- PÁGINA 1: PORTADA Y RESUMEN ---
            pdf.add_page()
            
            # Intentar cargar logo si existe
            if os.path.exists("logo.png"):
                try: pdf.image("logo.png", x=10, y=10, w=40)
                except: pass
            
            pdf.ln(20)
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'MEMORIA DE CALCULO - SISTEMA SOLAR FV', 0, 1, 'C')
            pdf.ln(10)
            
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 8, f'Cliente: {limpiar(cliente)}', 0, 1)
            pdf.cell(0, 8, f'Ubicacion: {limpiar(ciudad)} (Lat: {lat_map}, Lon: {lon_map})', 0, 1)
            pdf.cell(0, 8, f'Fecha: {fecha_proy}', 0, 1)
            pdf.ln(10)
            
            # Tabla Resumen Técnico
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, '1. RESUMEN TECNICO DEL SISTEMA', 0, 1, 'L', True)
            pdf.ln(5)
            
            pdf.set_font('Arial', '', 11)
            texto_tecnico = f"""
            - Tipo de Sistema: {limpiar(tipo_sistema)}
            - Potencia Instalada (DC): {st.session_state.potencia_sistema_kw:.2f} kWp
            - Generacion Promedio Estimada: {st.session_state.gen_total_mensual:.0f} kWh/mes
            - Modulos Fotovoltaicos: {st.session_state.n_paneles_real} unidades x {dato_panel['Potencia']}W ({limpiar(ref_panel)})
            - Inversor: 1 unidad x {dato_inv['Potencia']}W ({limpiar(ref_inv)})
            """
            pdf.multi_cell(0, 7, texto_tecnico)
            
            # --- PÁGINA 2: ANÁLISIS FINANCIERO ---
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, '2. ANALISIS FINANCIERO', 0, 1, 'L', True)
            pdf.ln(5)
            
            pdf.set_font('Arial', '', 11)
            texto_fin = f"""
            - Inversion Total Estimada: ${costo_proyecto:,.0f} COP
            - Ahorro Mensual Estimado: ${ahorro_mensual:,.0f} COP
            - Periodo de Retorno (ROI): {retorno_anios:.1f} Años
            - Ahorro Acumulado (25 anios): ${flujo_caja[-1]:,.0f} COP
            """
            pdf.multi_cell(0, 7, texto_fin)
            
            # Insertar Gráfica
            if os.path.exists("temp_roi.png"):
                pdf.image("temp_roi.png", x=10, w=190)
            
            # --- PÁGINA 3: DIAGRAMA UNIFILAR (DIBUJADO) ---
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, '3. DIAGRAMA UNIFILAR PRELIMINAR', 0, 1, 'L', True)
            pdf.ln(10)
            
            # Coordenadas base
            y = 60
            
            # 1. Paneles
            pdf.rect(20, y, 40, 30)
            pdf.set_font('Arial', 'B', 9)
            pdf.text(25, y+15, "GENERADOR FV")
            pdf.text(25, y+20, f"{st.session_state.n_paneles_real}x Paneles")
            
            # Cable DC
            pdf.line(60, y+15, 90, y+15)
            pdf.text(65, y+12, "Cable DC Solar")
            
            # 2. Inversor
            pdf.rect(90, y+5, 40, 20)
            pdf.text(95, y+18, "INVERSOR")
            
            # Cable AC
            pdf.line(130, y+15, 160, y+15)
            pdf.text(135, y+12, "Cable AC")
            
            # 3. Tablero
            pdf.rect(160, y, 30, 30)
            pdf.text(165, y+15, "RED")
            pdf.text(165, y+20, "PUBLICA")
            
            pdf.ln(50)
            pdf.set_font('Arial', 'I', 8)
            pdf.multi_cell(0, 5, "Nota: Este diagrama es ilustrativo. Para construccion refierase a los planos detallados de ingenieria aprobados por RETIE.")

            # --- PÁGINA 4: LISTA DE MATERIALES (BOM) ---
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, '4. LISTA DE MATERIALES (BOM)', 0, 1, 'L', True)
            pdf.ln(5)
            
            # Encabezados Tabla
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(100, 10, 'Descripcion del Item', 1)
            pdf.cell(30, 10, 'Cantidad', 1, 0, 'C')
            pdf.cell(30, 10, 'Unidad', 1, 1, 'C')
            
            # Filas
            pdf.set_font('Arial', '', 10)
            
            items = [
                (f"Panel Solar {dato_panel['Potencia']}W Monocristalino", str(st.session_state.n_paneles_real), "Unid"),
                (f"Inversor {dato_inv['Potencia']}W {limpiar(tipo_sistema)}", "1", "Unid"),
                ("Estructura de Montaje Aluminio Anodizado", "1", "Kit"),
                ("Cable Solar Fotovoltaico 4mm/6mm", "100", "mts"),
                ("Conectores MC4 (Parejas)", str(st.session_state.n_paneles_real + 2), "Juego"),
                ("Protecciones DC (DPS + Fusibles)", "1", "Tablero"),
                ("Protecciones AC (Breaker + DPS)", "1", "Tablero"),
                ("Sistema de Puesta a Tierra", "1", "Kit")
            ]
            
            for desc, cant, unid in items:
                pdf.cell(100, 10, limpiar(desc), 1)
                pdf.cell(30, 10, cant, 1, 0, 'C')
                pdf.cell(30, 10, unid, 1, 1, 'C')

            # Generar Output Compatible
            pdf_content = pdf.output(dest='S')
            
            # Manejo de compatibilidad bytes/str para diferentes versiones de FPDF
            if isinstance(pdf_content, str):
                pdf_bytes = pdf_content.encode('latin-1')
            else:
                pdf_bytes = pdf_content

            st.download_button(
                label="📥 DESCARGAR INFORME COMPLETO (PDF)",
                data=pdf_bytes,
                file_name=f"Informe_Solar_{limpiar(cliente)}.pdf",
                mime="application/pdf"
            )
            st.success("✅ Informe PDF generado exitosamente. Haga clic arriba para descargar.")

        except Exception as e:
            st.error(f"Error al generar el PDF: {e}")
