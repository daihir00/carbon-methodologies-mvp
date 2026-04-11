import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from pyproj import Geod
import pandas as pd
from engine.core import CarbonEngine
from ai.assistant import AIAssistant

# Initialize Engine and AI
engine = CarbonEngine()
ai = AIAssistant()

st.set_page_config(
    page_title="Carbon OS",
    page_icon="🌿",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #00CC66;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("🌿 Carbon OS")
    st.caption("AI-Powered Carbon Methodology Selection & Simulation Engine")

    # Workflow 1 & 2: Natural Language Input & AI Suggestion
    with st.sidebar:
        st.header("1. Describe Project")
        description = st.text_area(
            "Provide project details",
            placeholder="e.g. Reforestation of 500ha in a tropical climate using teak trees...",
            height=150
        )
        
        all_methods = engine.get_all_methodologies()
        
        st.header("2. AI Analysis")
        if description:
            suggested_ids = ai.suggest_methodology(description, all_methods)
            st.info(f"**Recommended:** {', '.join(suggested_ids)}")
        else:
            suggested_ids = [m['id'] for m in all_methods]

        method_options = {m['id']: f"{m['id']} - {m['name']}" for m in all_methods}
        default_idx = 0
        if suggested_ids and suggested_ids[0] in method_options:
            keys = list(method_options.keys())
            if suggested_ids[0] in keys:
                default_idx = keys.index(suggested_ids[0])

        st.header("3. Select Methodology")
        selected_method_id = st.selectbox(
            "Target Framework",
            options=list(method_options.keys()),
            format_func=lambda x: method_options[x],
            index=default_idx
        )

    if not selected_method_id:
        st.warning("Please verify methodology files are present in the 'data' directory.")
        return

    methodology = engine.get_methodology(selected_method_id)
    
    st.write("---")
    st.subheader(f"Methodology: {methodology['name']}")
    if 'applicability' in methodology:
        st.caption(f"**Applicability:** {methodology['applicability']['description']}")

    # Check if this method requires an area input
    inputs_def = methodology.get('inputs', [])
    has_area = any(inp['id'] == 'area_ha' for inp in inputs_def)
    
    area_ha = 0.0

    # Workflow 3: Map Integration (Only if area is needed)
    if has_area:
        st.markdown("##### 📍 Define Project Area")
        st.markdown("Draw a polygon on the map below. The AI will automatically integrate geospatial properties.")
        
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
        
        map_data = st_folium(m, width="100%", height=400)

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
                        st.success(f"Geospatial calculation complete: **{area_ha:,.2f} ha** identified.")
                    except Exception as e:
                        st.error(f"Error calculating area: {e}")

    # Workflow 3 (Cont.): Dynamic Form Generation
    st.markdown("##### 📋 Project Questionnaire")
    
    user_inputs = {}
    cols = st.columns(2)

    for idx, input_def in enumerate(inputs_def):
        col = cols[idx % 2]
        input_id = input_def['id']
        label = input_def.get('label', input_id.replace('_', ' ').title())
        if 'unit' in input_def:
            label += f" ({input_def['unit']})"
            
        guidance = ai.get_input_guidance(input_id)
        target_type = input_def.get('type', 'number')
        default_val = input_def.get('default')

        # Auto-fill map area
        if input_id == 'area_ha':
            current_val = float(area_ha) if area_ha > 0 else float(default_val or 100.0)
            val = col.number_input(label, value=current_val, help=guidance)
            user_inputs[input_id] = val
            
        elif target_type in ['number', 'integer']:
            val = col.number_input(label, value=float(default_val or 0.0), help=guidance)
            user_inputs[input_id] = val
            
        elif target_type == 'select':
            options = input_def.get('options', [])
            idx_opt = options.index(default_val) if default_val in options else 0
            val = col.selectbox(label, options=options, index=idx_opt, help=guidance)
            user_inputs[input_id] = val
            
        elif target_type == 'boolean':
            val = col.checkbox(label, value=bool(default_val), help=guidance)
            user_inputs[input_id] = val
            if input_id == 'include_uncertainty' and val:
                deduction_rate = col.slider("Risk & Uncertainty Deduction (%)", min_value=0, max_value=30, value=20, help="Select the buffer percentage to hold back for non-permanence risk and uncertainty.")
                user_inputs['uncertainty_deduction_rate'] = deduction_rate
            
        else:
            val = col.text_input(label, value=str(default_val or ""), help=guidance)
            user_inputs[input_id] = val

    st.write("")
    run = st.button("Calculate CO2 Removals", type="primary")

    # Workflow 4: Hybrid Execution & Results
    if run:
        try:
            validated_inputs = engine.validate_inputs(selected_method_id, user_inputs)
            results = engine.calculate(selected_method_id, validated_inputs)

            st.write("---")
            st.markdown("### 📊 Verification & Assessment")
            
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Gross Projected Removals", f"{results['gross_pre_deduction']:,.0f} tCO2e")
            with m2:
                deduction_amt = sum(d['amount'] for d in results.get('deductions', []))
                st.metric("Risk & Uncertainty Deductions", f"-{deduction_amt:,.0f} tCO2e")
            with m3:
                st.metric("Net Tradable Credits", f"{results['net_co2e']:,.0f} tCO2e", delta_color="normal")

            st.success(ai.explain_result(results))

            # Advanced Charting for Array-Based output (VM0047)
            if 'yearly_results' in results and results['yearly_results']:
                st.subheader("📈 Annual Yield Trajectory")
                st.line_chart([r["co2"] for r in results["yearly_results"]])

                st.subheader("📝 Calculation Transparency (Methodological Trace)")
                
                # Display calculation formula for every year in the project duration
                for index, yearly_data in enumerate(results["yearly_results"]):
                    year_num = index + 1
                    # Expand the first year by default, keep others collapsed to save vertical space
                    is_expanded = (year_num == 1)
                    with st.expander(f"Calculation Formula (Year {year_num})", expanded=is_expanded):
                        st.markdown(yearly_data["formula"])
                    
            # Legacy Charting for Step-Based output
            elif 'trace' in results and results['trace']:
                st.markdown("### Methodological Steps Executed")
                with st.expander("View Execution Trace"):
                     step_data = [[s['description'], s['formula'], f"{s['result']} {s.get('unit','')}"] for s in results['trace']]
                     st.table(pd.DataFrame(step_data, columns=["Step", "Equation / Execution", "Output Value"]))

        except Exception as e:
            st.error(f"Execution Error: {e}")

if __name__ == "__main__":
    main()
