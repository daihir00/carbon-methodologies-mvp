from engine.core import CarbonEngine

def test_engine():
    print("Initializing Engine...")
    engine = CarbonEngine()
    
    print("\nLoading Methodologies...")
    methods = engine.get_all_methodologies()
    print(f"Found {len(methods)} methodologies: {[m['id'] for m in methods]}")
    assert len(methods) > 0, "No methodologies found!"

    print("\nTesting VM0047 Calculation...")
    method_id = "VM0047"
    
    # Test Inputs
    inputs = {
        "area_ha": 100,
        "baseline_stock_tCO2_ha": 0,
        "avg_growth_rate_tCO2_ha_yr": 10,
        "project_duration_years": 20
    }
    
    # Expected Logic:
    # Baseline Emissions = 100 * 0 = 0
    # Annual Removals = 100 * 10 = 1000
    # Total Gross = 1000 * 20 = 20000
    # Net Before Deductions = 20000 - 0 = 20000
    # Deductions:
    # Uncertainty (5%): 1000
    # Leakage (10%): 2000
    # Buffer (15%): 3000
    # Total Deductions: 6000
    # Net = 14000
    
    print(f"Inputs: {inputs}")
    validated = engine.validate_inputs(method_id, inputs)
    results = engine.calculate(method_id, validated)
    
    print("\nResults:")
    print(f"Gross: {results['gross_pre_deduction']}")
    print(f"Net: {results['net_co2e']}")
    
    # Assertions
    assert results['gross_pre_deduction'] == 20000, f"Expected Gross 20000, got {results['gross_pre_deduction']}"
    assert results['net_co2e'] == 14000, f"Expected Net 14000, got {results['net_co2e']}"
    
    print("\n✅ Verification Passed!")

if __name__ == "__main__":
    test_engine()
