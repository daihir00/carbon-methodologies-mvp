import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from pyproj import Geod
from engine.core import CarbonEngine

st.set_page_config(layout="wide")
st.title("🌳 VM0047 Carbon Simulator")

engine = CarbonEngine()

st.markdown("Draw a polygon on the map to define your project area, or manually input it below.")

col1, col2 = st.columns([2, 1])

with col1:
    m = folium.Map(location=[0, 0], zoom_start=2)
    Draw(
        export=True,
        position='topleft',
        draw_options={
            'polyline': False,
            'polygon': True,
            'circle': False,
            'rectangle': True,
            'marker': False,
            'circlemarker': False
        }
    ).add_to(m)
    
    map_data = st_folium(m, width=900, height=500)

area_ha = 0.0

if map_data and map_data.get("all_drawings") and len(map_data["all_drawings"]) > 0:
    latest_drawing = map_data["all_drawings"][-1]
    geom = latest_drawing.get("geometry", {})
    if geom.get("type") == "Polygon":
        coords = geom.get("coordinates", [[]])[0]
        if len(coords) >= 3:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            try:
                geod = Geod(ellps="WGS84")
                area_m2, _ = geod.polygon_area_perimeter(lons, lats)
                area_ha = abs(area_m2) / 10000.0
            except Exception as e:
                st.error(f"Error calculating area: {e}")

with col2:
    st.subheader("Project Settings")
    if area_ha > 0:
        st.success(f"Drawn Area: **{area_ha:,.2f} ha**")
        area = st.number_input("Area (ha)", value=float(area_ha), min_value=0.1)
    else:
        st.info("Draw a polygon on the map to auto-calculate area.")
        area = st.number_input("Area (ha)", value=100.0, min_value=0.1)
        
    years = st.slider("Project Duration", 1, 50, 20)
    
    species = st.selectbox(
        "Species",
        ["teak", "eucalyptus", "pine"]
    )
    
    region = st.selectbox(
        "Region",
        ["tropical", "temperate", "boreal"]
    )
    
    uncertainty = st.checkbox("Include Uncertainty Range", True)
    
    run = st.button("Run Simulation", type="primary")

if run:
    inputs = {
        "area_ha": area,
        "species": species,
        "region": region,
        "project_duration_years": years,
        "include_uncertainty": uncertainty
    }

    results = engine.run(inputs)

    st.divider()
    st.subheader("Results")
    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        st.metric("🌍 Total CO2 (tCO2)", f"{results['total']:,.0f}")
    with col_res2:
        st.metric("📊 Net Credits (tCO2)", f"{results['net']:,.0f}")
    with col_res3:
        st.metric("⚖️ Uncertainty Range", f"{results['uncertainty']['low']:,.0f} - {results['uncertainty']['high']:,.0f}")

    st.subheader("📈 Yearly CO2 Simulation")
    st.line_chart([r["co2"] for r in results["yearly"]])
