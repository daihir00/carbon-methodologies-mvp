import streamlit as st
import pandas as pd
from engine.core import CarbonEngine
from ai.assistant import AIAssistant

# Initialize Engine and AI
engine = CarbonEngine()
ai = AIAssistant()

st.set_page_config(
    page_title="Carbon Methodology MVP",
    page_icon="🌿",
    layout="wide"
)

# Custom CSS for a cleaner look
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #00CC66;
        color: white;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("🌿 Carbon Credit Estimation Tool")
    st.caption("A preliminary estimation tool using standardized carbon methodologies.")

    # Sidebar: Project Context
    with st.sidebar:
        st.header("Project Details")
        description = st.text_area(
            "Describe your project",
            placeholder="e.g. Reforestation of 500ha of degraded cattle pasture in Brazil...",
            height=150
        )
        
        # Methodology Suggestion
        all_methods = engine.get_all_methodologies()
        if description:
            suggested_ids = ai.suggest_methodology(description, all_methods)
            st.info(f"AI Suggestion: {', '.join(suggested_ids)}")
        else:
            suggested_ids = [m['id'] for m in all_methods]

        method_options = {m['id']: f"{m['id']} - {m['name']}" for m in all_methods}
        
        # Filter options based on suggestion (optional, just sorting/highlighting for now)
        # For simplicity, we just show all but default to the suggested one
        default_idx = 0
        if suggested_ids and suggested_ids[0] in method_options:
            keys = list(method_options.keys())
            if suggested_ids[0] in keys:
                default_idx = keys.index(suggested_ids[0])

        selected_method_id = st.selectbox(
            "Select Methodology",
            options=list(method_options.keys()),
            format_func=lambda x: method_options[x],
            index=default_idx
        )

    if not selected_method_id:
        st.warning("Please verify methodology files are present in the 'data' directory.")
        return

    methodology = engine.get_methodology(selected_method_id)
    
    st.write("---")
    st.subheader(f"Methodology: {methodology['name']} ({methodology['id']})")
    st.write(f"**Applicability:** {methodology['applicability']['description']}")

    # Form Generation
    with st.form("calculation_form"):
        st.markdown("### Inputs")
        
        user_inputs = {}
        cols = st.columns(2)
        
        inputs_def = methodology.get('inputs', [])
        for idx, input_def in enumerate(inputs_def):
            col = cols[idx % 2]
            input_id = input_def['id']
            # Fallback for label if missing
            label_text = input_def.get('label', input_id.replace('_', ' ').title())
            label = f"{label_text} ({input_def.get('unit', '')})"
            
            # Get AI Guidance
            guidance = ai.get_input_guidance(input_id)
            
            if input_def['type'] == 'number':
                val = col.number_input(
                    label,
                    value=float(input_def.get('default', 0.0)),
                    help=guidance
                )
                user_inputs[input_id] = val
            else:
                 val = col.text_input(label, help=guidance)
                 user_inputs[input_id] = val

        submitted = st.form_submit_button("Calculate Estimation")

    if submitted:
        try:
            # Validate
            validated_inputs = engine.validate_inputs(selected_method_id, user_inputs)
            
            # Calculate
            results = engine.calculate(selected_method_id, validated_inputs)
            
            st.write("---")
            st.markdown("## Estimation Results")
            
            # Top-level Metrics
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Gross Removals", f"{results['gross_pre_deduction']:,.0f} tCO2e")
            with m2:
                deduction_total = results['gross_pre_deduction'] - results['net_co2e']
                st.metric("Total Deductions", f"-{deduction_total:,.0f} tCO2e")
            with m3:
                st.metric("Net Carbon Credits", f"{results['net_co2e']:,.0f} tCO2e", delta_color="normal")

            # AI Explanation
            st.success(ai.explain_result(results))

            # Traceability / breakdown
            st.markdown("### Calculation Trace")
            with st.expander("View Detailed Steps"):
                st.markdown("#### Quantification Steps")
                step_data = []
                for step in results['trace']:
                    step_data.append([step['description'], step['formula'], f"{step['result']:,.2f} {step['unit']}"])
                st.table(pd.DataFrame(step_data, columns=["Step", "Formula", "Result"]))
                
                st.markdown("#### Deductions Applied")
                ded_data = []
                for d in results['deductions']:
                    ded_data.append([d['name'], f"{d['value']*100}%", f"{d['amount']:,.2f}"])
                st.table(pd.DataFrame(ded_data, columns=["Deduction", "Rate", "Amount Cleared"]))
            
            st.caption("Disclaimer: This is a preliminary estimation only and not a verified carbon credit issuance. Final numbers require 3rd party auditing.")

        except Exception as e:
            st.error(f"Error during calculation: {e}")

if __name__ == "__main__":
    main()
