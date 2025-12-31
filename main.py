import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os

# --- SISTEMA DE SEGURIDAD ---
# 1. Pedimos la contraseña en la barra lateral
password = st.sidebar.text_input("🔑 Ingresa la contraseña:", type="password")

# 2. Si la contraseña NO es correcta, paramos todo
if password != "SOLAR2025":
    st.sidebar.error("🔒 App Bloqueada")
    st.stop() # <--- Esto detiene la app aquí
# ----------------------------

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CESAR CM Solar Suite", page_icon="☀️", layout="wide")

# --- CLASE PDF (LA RECETA DEL REPORTE) ---
class PDF(FPDF):
    def header(self):
        # Título del reporte (Sin logo)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte de Dimensionamiento Solar', 0, 1, 'C')
        self.ln(10)
# ------------------------------------------

# --- MOTOR DE CÁLCULO (TIPO PVSYST) ---
# Copia esto y pégalo justo debajo de la class PDF
def simulacion_pvsyst(potencia_pico_kw, hsp, temp_ambiente):
    """
    Calcula la energía real considerando pérdidas físicas.
    """
    # 1. Pérdida por Temperatura (Los paneles odian el calor)
    # Se asume que la celda está 25°C más caliente que el aire
    temp_celda = temp_ambiente + 25 
    # Coeficiente de pérdida: 0.4% por cada grado extra
    perdida_termica = (temp_celda - 25) * 0.004 
    if perdida_termica < 0: perdida_termica = 0
    
    # 2. Pérdidas del Sistema (Eficiencia del Inversor y Cables)
    eficiencia_inversor = 0.96 # 96%
    perdida_suciedad = 0.03    # 3% por polvo
    perdida_cables = 0.02      # 2% por resistencia
    
    # Factor de Rendimiento Global (Performance Ratio)
    pr_sistema = (1 - perdida_termica) * (1 - perdida_suciedad) * (1 - perdida_cables) * eficiencia_inversor
    
    # 3. Cálculo Final
    generacion_diaria = potencia_pico_kw * hsp * pr_sistema
    
    return generacion_diaria, pr_sistema
# ------------------------------------------
    
    def footer(self):
        # Pie de página
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')
# ------------------------------------------

    def generar_pdf(cliente, ciudad, sistema_info, financiero_info):
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
    
    # Fecha
    pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')
    pdf.ln(10)
    
    # 1. DATOS DEL CLIENTE
    pdf.set_fill_color(200, 220, 255) # Azul clarito
    pdf.cell(0, 10, " 1. INFORMACION DEL PROYECTO", 1, 1, 'L', fill=True)
    pdf.ln(2)
    pdf.cell(0, 8, f"Cliente: {cliente}", ln=True)
    pdf.cell(0, 8, f"Ubicacion: {ciudad}", ln=True)
    pdf.ln(5)
    
    # 2. SISTEMA TÉCNICO
    pdf.cell(0, 10, " 2. DETALLES DEL SISTEMA", 1, 1, 'L', fill=True)
    pdf.ln(2)
    pdf.cell(0, 8, f"Paneles Solares: {sistema_info['num_paneles']} x {sistema_info['ref_panel']} ({sistema_info['potencia_panel']}W)", ln=True)
    pdf.cell(0, 8, f"Inversor: {sistema_info['inversor']}", ln=True)
    pdf.cell(0, 8, f"Potencia Total Instalada: {sistema_info['pot_total']} Wp", ln=True)
    pdf.cell(0, 8, f"Generacion Mensual Promedio: {int(sistema_info['generacion'])} kWh", ln=True)
    pdf.ln(5)
    
    # 3. FINANCIERO
    pdf.cell(0, 10, " 3. ANALISIS DE INVERSION", 1, 1, 'L', fill=True)
    pdf.ln(2)
    pdf.cell(0, 8, f"Inversion Inicial: ${financiero_info['costo']:,.0f}", ln=True)
    pdf.cell(0, 8, f"Ahorro Mensual Estimado: ${financiero_info['ahorro_mes']:,.0f}", ln=True)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"TIEMPO DE RETORNO: {financiero_info['retorno']:.1f} ANOS", ln=True)
    
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
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png")
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
    col1, col2 = st.columns(2)
    with col1:
        consumo = st.number_input("Consumo (kWh/mes)", value=500)
        # Pide la temperatura para calcular pérdidas por calor
            temp = st.number_input("🌡️ Temperatura Ambiente (°C)", value=28.0)
      st.success(f"✅ Paneles requeridos: {n_paneles}")
            
            # --- CÁLCULO EXACTO TIPO PVSYST ---
            # 1. Calculamos la potencia total de los paneles en kW
            potencia_sistema_kw = (n_paneles * dato_panel["Potencia"]) / 1000
            
            # 2. Llamamos al motor físico (simulacion_pvsyst)
            # Nota: 'hsp' ya lo tienes definido arriba en tu código
            gen_diaria_real, eficiencia_real = simulacion_pvsyst(potencia_sistema_kw, hsp, temp)
            
            # 3. Convertimos a Mensual (x 30 días)
            gen_mensual_real = gen_diaria_real * 30
            
            # 4. Mostrar Resultados Profesionales
            st.metric("⚡ Generación Real Promedio", f"{gen_mensual_real:.0f} kWh/mes")
            st.caption(f"📉 Eficiencia del Sistema (PR): {eficiencia_real*100:.1f}% (Considerando pérdidas por calor)")

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

    st.markdown("---")
    
    # Preparar datos para PDF
    datos_sistema = {
        "num_paneles": n_paneles,
        "ref_panel": ref_panel,
        "potencia_panel": dato_panel["Potencia"],
        "inversor": ref_inv,
        "generacion": gen_total,
        "pot_total": n_paneles * dato_panel["Potencia"]
    }
    datos_financieros = {
        "costo": costo,
        "ahorro_mes": ahorro_mes,
        "retorno": retorno
    }
    
    if st.button("Generar Reporte PDF Oficial"):
        pdf_bytes = generar_pdf(cliente, ciudad, datos_sistema, datos_financieros)
        st.download_button(
            label="💾 Descargar PDF con Logo",
            data=pdf_bytes,
            file_name=f"Cotizacion_{cliente}.pdf",
            mime="application/pdf"
        )
