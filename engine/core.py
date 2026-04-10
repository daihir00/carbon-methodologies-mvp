import math
import yaml

def growth(age, a, b, c, factor=1.0):
    return a * (1 - math.exp(-b * age)) ** c * factor

class CarbonEngine:

    def __init__(self):
        with open("methods/vm0047.yaml") as f:
            self.config = yaml.safe_load(f)

    def simulate_year(self, inputs, year):

        params = self.config["parameters"]

        species = inputs["species"]
        region = inputs["region"]

        sp = params["species_params"][species]
        factor = params["region_factors"][region]

        dbh = growth(year, **sp["dbh"], factor=factor)
        height = growth(year, **sp["height"], factor=factor)

        trees_per_ha = inputs.get("trees_per_ha", 1000)
        rho = sp["wood_density"]

        agb_tree_kg = 0.0673 * (rho * dbh**2 * height) ** 0.976
        agb_t_per_ha = (agb_tree_kg * trees_per_ha) / 1000.0

        agb = agb_t_per_ha
        bgb = agb * params["root_shoot_ratio"]
        litter = agb * params["litter_ratio"]
        deadwood = agb * params["deadwood_ratio"]

        soil = (
            params["soil"]["default_tCO2_per_ha"]
            + params["soil"]["accumulation_rate_tCO2_per_ha_yr"] * year
        ) * inputs["area_ha"]

        carbon = (agb + bgb + litter + deadwood) * params["carbon_fraction"]
        co2_t_per_ha = carbon * params["co2_conversion"]
        co2 = co2_t_per_ha * inputs["area_ha"]

        formula_text = f"""
**【Year {year} Calculation Trace (Area: {inputs['area_ha']} ha, Trees/ha: {trees_per_ha})】**

**1. Growth Model (Species: {species}, Region factor: {factor})**:
- DBH (cm) = *{sp['dbh']['a']} × (1 - exp(-{sp['dbh']['b']} × {year}))^{sp['dbh']['c']} × {factor}* = **{dbh:.2f} cm**
- Height (m) = *{sp['height']['a']} × (1 - exp(-{sp['height']['b']} × {year}))^{sp['height']['c']} × {factor}* = **{height:.2f} m**

**2. Biomass per Tree (Chave et al. equation)**:
- AGB_tree (kg) = *0.0673 × ({rho} × {dbh:.2f}² × {height:.2f})^0.976* = **{agb_tree_kg:.2f} kg/tree**

**3. Carbon Pools per Hectare (tons/ha)**:
- AGB (t/ha) = *{agb_tree_kg:.2f} kg × {trees_per_ha} trees / 1000* = **{agb:.2f} t/ha**
- BGB (t/ha) = *AGB × {params['root_shoot_ratio']}* = **{bgb:.2f} t/ha**
- Litter (t/ha) = *AGB × {params['litter_ratio']}* = **{litter:.2f} t/ha**
- Deadwood (t/ha) = *AGB × {params['deadwood_ratio']}* = **{deadwood:.2f} t/ha**

**4. CO2 Equivalents (tons/ha & total)**:
- Total Biomass Carbon = *({agb:.2f} + {bgb:.2f} + {litter:.2f} + {deadwood:.2f}) × {params['carbon_fraction']} (carbon fraction)* = **{carbon:.2f} tC/ha**
- CO2e per ha = *{carbon:.2f} × {params['co2_conversion']}* = **{co2_t_per_ha:.2f} tCO2/ha**
- **Total CO2e** = *{co2_t_per_ha:.2f} tCO2/ha × {inputs['area_ha']} ha* = **{co2:.2f} tCO2**
"""

        return {
            "year": year,
            "co2": co2,
            "agb": agb,
            "bgb": bgb,
            "litter": litter,
            "deadwood": deadwood,
            "soil": soil,
            "formula": formula_text
        }

    def run(self, inputs):

        years = inputs["project_duration_years"]
        results = []

        for y in range(1, years + 1):
            results.append(self.simulate_year(inputs, y))

        total = sum(r["co2"] for r in results)

        # baseline (simple: 0 growth)
        baseline = 0
        net = total - baseline

        if inputs.get("include_uncertainty", True):
            low = net * self.config["parameters"]["uncertainty"]["low"]
            high = net * self.config["parameters"]["uncertainty"]["high"]
        else:
            low = high = net

        return {
            "yearly": results,
            "total": total,
            "net": net,
            "uncertainty": {"low": low, "high": high}
        }
