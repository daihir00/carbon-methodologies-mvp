class AIAssistant:
    """
    Mock AI Assistant for the MVP.
    In a real production app, this would call an LLM API (e.g., Gemini/Vertex AI).
    """

    def suggest_methodology(self, project_description, methodologies):
        """
        Analyzes the project description and suggests the best methodology.
        Simple keyword matching for MVP.
        """
        desc_lower = project_description.lower()
        
        # Simple heuristic for MVP
        if "forest" in desc_lower or "tree" in desc_lower or "planting" in desc_lower:
            return ["VM0047"]
        
        # Default fallback
        return [m['id'] for m in methodologies]

    def explain_result(self, result_data):
        """
        Generates a plain-language explanation of the results.
        """
        net = result_data['net_co2e']
        gross = result_data['gross_pre_deduction']
        deductions_count = len(result_data['deductions'])
        
        explanation = (
            f"Based on the inputs provided, the estimated net carbon benefit is **{net:,.2f} tCO2e**.\n\n"
            f"This was calculated by first estimating a gross benefit of {gross:,.2f} tCO2e based on the "
            f"project area and growth rates. We then applied {deductions_count} deductions "
            f"(including uncertainty and leakage buffers) totalling {gross - net:,.2f} tCO2e to ensure "
            f"conservativeness."
        )
        return explanation

    def get_input_guidance(self, input_id):
        """
        Returns helpful context for specific inputs.
        """
        guidance = {
            "baseline_stock_tCO2_ha": "For degraded land, this is often near zero. If there is existing vegetation, estimated biomass surveys are needed.",
            "avg_growth_rate_tCO2_ha_yr": "Typical values range from 5-15 tCO2e/ha/yr for tropical regions, and 2-8 for temperate regions depending on species."
        }
        return guidance.get(input_id, "Please enter the estimated value based on project data.")
