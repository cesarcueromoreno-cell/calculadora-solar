import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CESAR CM Solar Suite", page_icon="☀️", layout="wide")

st.write("⚠️ VERSIÓN NUEVA CARGADA CORRECTAMENTE")

# --- SISTEMA DE SEGURIDAD ---
# 1. Pedimos la contraseña en la barra lateral
password = st.sidebar.text_input("🔑 Ingresa la contraseña:", type="password")

# 2. Si la contraseña NO es correcta, paramos todo
if password != "SOLAR2025":
    st.sidebar.error("🔒 App Bloqueada")
    st.stop() # <--- Esto detiene la app aquí
# ----------------------------

# --- DICCIONARIO DE COORDENADAS (PARA EL MAPA) ---
coordenadas_ciudades = {
    "Bucaramanga": [7.1193, -73.1227],
    "Bogota": [4.7110, -74.0721],
    "Medellin": [6.2442, -75.5812],
    "Cali": [3.4516, -76.5320],
    "Barranquilla": [10.9685, -74.7813],
    "San Jose del Guaviare": [2.5729, -72.6378],
    "Colombia": [4.5709, -74.2973] 
}
# --- FUNCIÓN MOTOR DE CÁLCULO (PVSYST LITE) ---
def simulacion_pvsyst(potencia_dc_kw, hsp_sitio, temp_amb_grados):
    # 1. Pérdidas por Temperatura
    # Los paneles pierden eficiencia si hace mucho calor (aprox -0.4% por cada grado arriba de 25°C)
    perdida_temp = 0.004 * (temp_amb_grados - 25)
    if perdida_temp < 0: perdida_temp = 0 # Si hace frío, ganan un poco o se quedan igual (simplificado)
    
    # 2. Pérdidas del Sistema (Cables, suciedad, inversor)
    # Un estándar de la industria es 14% de pérdidas totales (Performance Ratio base 0.86)
    perdidas_sistema = 0.14 
    
    # 3. Eficiencia Total (Performance Ratio - PR)
    eficiencia_global = 1 - (perdidas_sistema + perdida_temp)
    
    # 4. Cálculo de Energía: Potencia * Sol * Eficiencia
    generacion_diaria = potencia_dc_kw * hsp_sitio * eficiencia_global
    
    return generacion_diaria, eficiencia_global
    
# --- CLASE PDF (LA RECETA DEL REPORTE) ---
class PDF(FPDF):
    def header(self):
        # Título del reporte (Sin logo)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte de Dimensionamiento Solar', 0, 1, 'C')
        self.ln(10)
# ------------------------------------------
def generar_pdf(cliente, ciudad, sistema_info, financiero_info):
    pdf = PDF()
    pdf.add_page()
    
    # --- LOGO (BLOQUE DE SEGURIDAD) ---
    # Usamos try/except para que NUNCA se rompa, incluso si la imagen falla
    try:
        # Prioridad 1: El archivo JPG (que sabemos que funciona)
        if os.path.exists("logo.png.JPG"):
            pdf.image("logo.png.JPG", x=10, y=8, w=40)
            pdf.ln(10)
        # Prioridad 2: El archivo doble extensión
        elif os.path.exists("logo.png.png"):
            pdf.image("logo.png.png", x=10, y=8, w=40)
            pdf.ln(10)
    except:
        # Si la imagen falla, no hacemos nada y seguimos generando el reporte
        pass

    # --- TÍTULO ---
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Reporte de Dimensionamiento Solar', 0, 1, 'C')
    pdf.ln(10)

    # --- CUERPO DEL REPORTE ---
    pdf.set_font('Arial', '', 12)
    
    # Función pequeña para arreglar tildes (latin-1) y evitar errores raros
    def limpiar(texto):
        return str(texto).encode('latin-1', 'replace').decode('latin-1')

    pdf.cell(0, 10, f'Cliente: {limpiar(cliente)}', 0, 1)
    pdf.cell(0, 10, f'Ubicacion: {limpiar(ciudad)}', 0, 1)
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Detalles del Sistema:', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 10, limpiar(sistema_info))
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Analisis Financiero:', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 10, limpiar(financiero_info))
    
    return pdf.output(dest='S').encode('latin-1', 'replace')
    
    # Retorno del PDF
    return pdf.output(dest='S').encode('latin-1')
# --- CARGA DE DATOS ---
try:
    archivo = "data/base_datos.xlsx"
    df_ciudades = pd.read_excel(archivo, sheet_name="Ciudades")
    df_modulos = pd.read_excel(archivo, sheet_name="Modulos")
    df_inversores = pd.read_excel(archivo, sheet_name="Inversores")
    
    # Limpieza
    df_modulos.columns = df_modulos.columns.str.strip()
    df_ciudades.columns = df_ciudades.columns.str.strip()
    df_inversores.columns = df_inversores.columns.str.strip()

except Exception as e:
    st.error(f"⚠️ Error leyendo Excel: {e}")
    st.stop()

# --- INTERFAZ ---
st.title("CESAR CM INGENIERÍA - SUITE PROFESIONAL")
st.markdown("---")

# BARRA LATERAL
# BARRA LATERAL (LOGO)
if os.path.exists("logo.png.JPG"):
    st.sidebar.image("logo.png.JPG")

    # --- DATOS DEL PROYECTO (Ahora fuera del if para que siempre funcionen) ---
    cliente = st.text_input("Cliente", "Empresa SAS")

st.header("2. Ubicación")
depto = st.selectbox("Departamento", df_ciudades["Departamento"].unique())
ciudades = df_ciudades[df_ciudades["Departamento"] == depto]
ciudad = st.selectbox("Ciudad", ciudades["Ciudad"])
hsp = ciudades[ciudades["Ciudad"] == ciudad].iloc[0]["HSP"]

st.header("3. Equipos")
ref_panel = st.selectbox("Panel", df_modulos["Referencia"])
dato_panel = df_modulos[df_modulos["Referencia"] == ref_panel].iloc[0]
ref_inv = st.selectbox("Inversor", df_inversores["Referencia"])
dato_inv = df_inversores[df_inversores["Referencia"] == ref_inv].iloc[0]

# CÁLCULOS GLOBALES
generacion_panel = (dato_panel["Potencia"] * hsp * 0.80 * 30) / 1000

# TABS
tab1, tab2, tab3 = st.tabs(["📐 Dimensionamiento", "⚡ Eléctrico", "💰 Financiero & PDF"])

with tab1:
        st.header("Dimensionamiento del Sistema")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 1. Aquí pedimos el Consumo
            consumo = st.number_input("Consumo Promedio (kWh/mes)", value=500)
        
        with col2:
            # 2. ¡AQUÍ ESTÁ LA MAGIA! Pedimos la Temperatura
            temp = st.number_input("🌡️ Temperatura Ambiente (°C)", value=28.0)

        # --- CÁLCULOS ---
        if consumo > 0:
            # Definir Hora Solar Pico (promedio Colombia)
            hsp = 4.5 
            
            # Cálculo de paneles (Estimación inicial)
            generacion_panel_mensual_simple = (dato_panel["Potencia"] / 1000) * hsp * 30 * 0.80
            n_paneles = int(consumo / generacion_panel_mensual_simple) + 1

            # Mostrar resultado verde
            st.success(f"✅ Paneles requeridos: {n_paneles}")
            
            st.divider() # Una línea separadora bonita

            # --- CÁLCULO PROFESIONAL (Usando tu función arreglada) ---
            
            # A. Calculamos potencia total
            potencia_sistema_kw = (n_paneles * dato_panel["Potencia"]) / 1000
            
            # B. Llamamos a la función que ya arreglaste arriba
            gen_diaria_real, eficiencia_real = simulacion_pvsyst(potencia_sistema_kw, hsp, temp)
            gen_total = gen_diaria_real * 30
            
            # C. Resultados Finales
           # --- SECCIÓN DE MAPA Y DATOS GEOGRÁFICOS ---
        st.markdown("---")
        st.subheader("📍 Ubicación y Recurso Solar")
        
        col_mapa, col_datos = st.columns([2, 1]) 
        
        with col_mapa:
            # Buscamos las coordenadas. Si no existe, usa Colombia por defecto.
            coords = coordenadas_ciudades.get(ciudad, coordenadas_ciudades["Colombia"])
            
            # Mapa Satelital
            df_mapa = pd.DataFrame({'lat': [coords[0]], 'lon': [coords[1]]})
            st.map(df_mapa, zoom=12)

        with col_datos:
            # Tabla de Datos Técnicos
            st.markdown("##### ☀️ Datos del Sitio")
            with st.container(border=True):
                st.markdown(f"**Ciudad:** {ciudad}")
                st.markdown(f"**Latitud:** {coords[0]}°")
                st.markdown(f"**Longitud:** {coords[1]}°")
                st.divider()
                st.markdown(f"**Irradiación:** {hsp:.1f} kWh/m²")
                st.markdown(f"**Temperatura:** {temp}°C") 
            col_res1, col_res2 = st.columns(2)
            col_res1.metric("⚡ Generación Real", f"{gen_diaria_real * 30:.0f} kWh/mes")
            col_res2.metric("📉 Eficiencia (PR)", f"{eficiencia_real*100:.1f}%")
            
            # D. Mensaje explicativo
            if temp > 25:
                st.caption(f"⚠️ Nota: A {temp}°C, los paneles pierden un poco de eficiencia por calor.")
            else:
                st.caption(f"❄️ Nota: A {temp}°C, los paneles trabajan muy eficientemente.")
            st.markdown("---") 
            st.subheader("📊 Comparativa: Solar vs Consumo")

        # Creamos los datos para la gráfica
        datos_grafica = pd.DataFrame({
            "Mes": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
            "Consumo Red": [consumo] * 12,       
            "Tu Energía Solar": [gen_total] * 12   
        })

        # Mostramos la gráfica (Rojo = Consumo, Verde = Solar)
        st.bar_chart(datos_grafica.set_index("Mes"), color=["#FF4B4B", "#00CC96"])
with tab2:
        n_serie = st.slider("Paneles en Serie", 1, 20, n_paneles)
        voc_total = dato_panel["Voc"] * n_serie
    
if voc_total > dato_inv["Vmax"]:
    st.error(f"🛑 PELIGRO: {voc_total:.1f}V supera el máximo de {dato_inv['Vmax']}V")
else:
    st.success(f"✅ Voltaje Seguro: {voc_total:.1f}V (Max: {dato_inv['Vmax']}V)")
    st.progress(voc_total / dato_inv["Vmax"])

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Datos Económicos")
        tarifa = st.number_input("Tarifa ($/kWh)", value=800)
        costo = st.number_input("Costo Proyecto ($)", value=20000000)
    
    with col2:
        ahorro_mes = gen_total * tarifa
        retorno = costo / (ahorro_mes * 12)
        st.metric("Retorno de Inversión", f"{retorno:.1f} Años")
        st.metric("Ahorro Mensual", f"${ahorro_mes:,.0f}")

# --- GRÁFICA DE RETORNO DE INVERSIÓN (NUEVO) ---
        st.subheader("📈 Proyección de Ahorro Acumulado (25 Años)")

        # 1. Calculamos cómo crece el dinero año tras año
        flujo_dinero = []
        dinero_actual = -costo  # Empezamos perdiendo la inversión inicial
        ahorro_anual = ahorro_mes * 12

        for anio in range(0, 26):
            flujo_dinero.append(dinero_actual)
            dinero_actual = dinero_actual + ahorro_anual  # Sumamos el ahorro de este año

        # 2. Preparamos los datos para la gráfica
        datos_roi = pd.DataFrame({
            "Año": range(0, 26),
            "Saldo Acumulado ($)": flujo_dinero
        })

        # 3. Dibujamos la línea
        # Pista visual: Ponemos una línea en el 0 para ver cuándo cruzamos a ganancia
        st.line_chart(datos_roi.set_index("Año"))

        # Mensaje inteligente
        if retorno < 5:
            st.success(f"🚀 ¡Excelente Inversión! En el año {int(retorno)+1} ya tienes ganancias puras.")
        else:
            st.info(f"ℹ️ El sistema se paga solo en {retorno:.1f} años. Después, la energía es gratis.")
    st.markdown("---")
    
  # --- PREPARACIÓN DEL REPORTE PDF (NUEVO CON COORDENADAS) ---
    
    # 1. Recuperamos las coordenadas para ponerlas en el reporte
    coords_pdf = coordenadas_ciudades.get(ciudad, coordenadas_ciudades["Colombia"])
    
    # 2. Texto TÉCNICO (Con Ubicación y Datos)
    info_sistema_txt = f"""
    1. UBICACION Y DATOS DEL SITIO
    --------------------------------------------------
    Ciudad: {ciudad}
    Coordenadas: Lat {coords_pdf[0]}, Lon {coords_pdf[1]}
    Irradiacion (HSP): {hsp:.1f} kWh/m2/dia
    Temperatura Ambiente: {temp} C
    
    2. DETALLES DEL SISTEMA
    --------------------------------------------------
    Paneles en Serie: {n_serie} unidades
    Potencia Total Instalada: {voc_total:.1f} V 
    Generacion Estimada: {gen_total:.0f} kWh/mes
    Eficiencia Global (PR): {eficiencia_real*100:.1f}%
    """

    # 3. Texto FINANCIERO
    info_financiera_txt = f"""
    3. ANALISIS FINANCIERO
    --------------------------------------------------
    Costo del Proyecto: ${costo:,.0f} COP
    Ahorro Mensual Estimado: ${ahorro_mes:,.0f} COP
    Retorno de Inversion (ROI): {retorno:.1f} Años
    """

    # --- BOTÓN DE DESCARGA ---
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    
    with col_centro:
        if st.button("📄 Generar Reporte PDF Oficial", use_container_width=True):
            # Usamos la variable 'ciudad' para que cambie según lo que elijas
            pdf_bytes = generar_pdf(password, ciudad, info_sistema_txt, info_financiera_txt)
            
            st.download_button(
            label="⬇️ Descargar PDF (CON COORDENADAS)",   # <--- ¡MIRA ESTA COMA AL FINAL!
                data=pdf_bytes,
                file_name=f"Reporte_Solar_{ciudad}.pdf",
                mime="application/pdf"
            )
            st.success("✅ ¡Reporte generado! Haz clic arriba para descargar.")
