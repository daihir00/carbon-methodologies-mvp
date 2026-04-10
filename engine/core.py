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

        rho = sp["wood_density"]

        agb = 0.0673 * (rho * dbh**2 * height) ** 0.976
        bgb = agb * params["root_shoot_ratio"]
        litter = agb * params["litter_ratio"]
        deadwood = agb * params["deadwood_ratio"]

        soil = (
            params["soil"]["default_tCO2_per_ha"]
            + params["soil"]["accumulation_rate_tCO2_per_ha_yr"] * year
        ) * inputs["area_ha"]

        carbon = (agb + bgb + litter + deadwood) * params["carbon_fraction"]
        co2 = carbon * params["co2_conversion"] * inputs["area_ha"]

        return {
            "year": year,
            "co2": co2,
            "agb": agb,
            "bgb": bgb,
            "litter": litter,
            "deadwood": deadwood,
            "soil": soil
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
