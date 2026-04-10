import yaml
import os
import simpleeval

class CarbonEngine:
    def __init__(self, methodologies_path="data"):
        self.methodologies_path = methodologies_path
        self.methodologies = {}
        self.load_methodologies()

    def load_methodologies(self):
        """Loads all YAML methodology files from the data directory."""
        if not os.path.exists(self.methodologies_path):
            return

        for filename in os.listdir(self.methodologies_path):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.methodologies_path, filename)
                try:
                    with open(filepath, 'r') as f:
                        methodology = yaml.safe_load(f)
                        if 'id' in methodology:
                            self.methodologies[methodology['id']] = methodology
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

    def get_methodology(self, method_id):
        return self.methodologies.get(method_id)

    def get_all_methodologies(self):
        return list(self.methodologies.values())

    def validate_inputs(self, method_id, user_inputs):
        """Validates that all required inputs are present and of correct type."""
        methodology = self.get_methodology(method_id)
        if not methodology:
            raise ValueError(f"Methodology {method_id} not found.")

        validated = {}
        errors = []

        for input_def in methodology.get('inputs', []):
            input_id = input_def['id']
            # Fallback for label if missing (e.g. if using strict minimal yaml)
            label = input_def.get('label', input_id)
            value = user_inputs.get(input_id)

            if input_def.get('required', False) and value is None:
                if 'default' in input_def:
                    value = input_def['default']
                else:
                    errors.append(f"Missing required input: {label} ({input_id})")
                    continue
            
            if value is not None:
                try:
                    target_type = input_def.get('type', 'number')
                    if target_type == 'number':
                        value = float(value)
                    elif target_type == 'integer':
                        value = int(value)
                    elif target_type == 'array':
                        if isinstance(value, str):
                            value = [float(x.strip()) for x in value.split(',') if x.strip()]
                        elif isinstance(value, list):
                            value = [float(x) for x in value]
                    validated[input_id] = value
                except ValueError:
                    errors.append(f"Invalid type for {label}: expected {input_def['type']}")

        if errors:
            raise ValueError("\n".join(errors))

        return validated

    def calculate(self, method_id, inputs):
        """
        Executes the methodology steps deterministically.
        Supports both legacy 'formula' (simpleeval) and new 'quantification' (method-based) schemas.
        """
        methodology = self.get_methodology(method_id)
        if not methodology:
            raise ValueError(f"Methodology {method_id} not found.")

        context = inputs.copy()
        trace = []
        
        # Check for new 'quantification' block
        if 'quantification' in methodology:
            steps = methodology['quantification']['steps']
            for step in steps:
                step_id = step['id']
                method = step['method']
                step_inputs = step.get('inputs', [])
                output_key = step['output']
                
                result = 0.0
                step_desc = step.get('description', step_id)

                try:
                    operand_values = [context.get(k, 0.0) for k in step_inputs]
                    params = step.get('parameters', {})
                    
                    if method == 'multiply':
                        if all(isinstance(v, (int, float)) for v in operand_values):
                            val = 1.0
                            for v in operand_values:
                                val *= v
                            result = val
                        else:
                            arr_idx = 0 if isinstance(operand_values[0], list) else 1
                            scalar_idx = 1 - arr_idx
                            if len(operand_values) == 2 and isinstance(operand_values[arr_idx], list):
                                scalar = operand_values[scalar_idx]
                                result = [v * scalar for v in operand_values[arr_idx]]
                            else:
                                raise ValueError("multiply currently supports one array and one scalar max")
                        
                    elif method == 'subtract':
                        if len(operand_values) > 0:
                            v0 = operand_values[0]
                            if isinstance(v0, list):
                                if len(operand_values) == 2 and not isinstance(operand_values[1], list):
                                    result = [x - operand_values[1] for x in v0]
                                else:
                                    raise ValueError("subtract array minus array not yet implemented")
                            else:
                                result = v0
                                for v in operand_values[1:]:
                                    result -= v
                        else:
                            result = 0.0
                            
                    elif method == 'si_to_agb':
                        a = params.get('a', 1.0)
                        b = params.get('b', 1.0)
                        si_array = operand_values[0]
                        result = [a * (si ** b) for si in si_array]
                        
                    elif method == 'percentile':
                        p = params.get('p', 50)
                        arr = sorted(operand_values[0])
                        k = (len(arr) - 1) * (p / 100.0)
                        f = int(k)
                        c = int(k) + 1 if int(k) + 1 < len(arr) else f
                        result = arr[f] + (k - f) * (arr[c] - arr[f])
                        
                    elif method == 'clip_min':
                        min_val = params.get('min', 0.0)
                        v0 = operand_values[0]
                        if isinstance(v0, list):
                            result = [max(x, min_val) for x in v0]
                        else:
                            result = max(v0, min_val)
                            
                    elif method == 'agb_to_co2':
                        carbon_fraction = params.get('carbon_fraction', 0.47)
                        v0 = operand_values[0]
                        factor = carbon_fraction * (44.0 / 12.0)
                        if isinstance(v0, list):
                            result = [x * factor for x in v0]
                        else:
                            result = v0 * factor

                    elif method == 'add': # Basic support
                         result = sum(operand_values)

                    else:
                        raise ValueError(f"Unknown method '{method}' in step {step_id}")
                    
                    context[output_key] = result
                    
                    display_result = result if not isinstance(result, list) else f"Array(len={len(result)}, sum={sum(result):.2f})"
                    trace.append({
                        "step_id": step_id,
                        "description": step_desc,
                        "formula": f"{method}({', '.join(step_inputs)})",
                        "result": display_result,
                        "unit": step.get('output_unit', '')
                    })
                    
                except Exception as e:
                     raise ValueError(f"Error in step {step_id}: {e}")
            
            # Identify Basis for Deductions (usually the last step's output)
            base_amount_key = steps[-1]['output']
            base_amount = context.get(base_amount_key, 0.0)
            if isinstance(base_amount, list):
                base_amount = sum(base_amount)

        else:
            # Legacy Eval Mode (Keep for backward compatibility during migration)
            for step in methodology.get('steps', []):
                step_id = step['id']
                formula = step['formula']
                try:
                    result = simpleeval.simple_eval(formula, names=context)
                    context[step_id] = result
                    trace.append({
                        "step_id": step_id,
                        "description": step.get('description'),
                        "formula": formula,
                        "result": result,
                        "unit": step.get('output_unit')
                    })
                except Exception as e:
                    raise ValueError(f"Calculation error in step '{step_id}': {e}")
            
            if trace:
                base_amount = trace[-1]['result']
            else:
                base_amount = 0.0

        # Apply Deductions
        deductions_def = methodology.get('deductions', [])
        deduction_results = []
        total_deduction_amount = 0

        # Handle Dict format (New) vs List format (Old)
        if isinstance(deductions_def, dict):
            # New format: { 'uncertainty': 0.05, ... }
            for name, val in deductions_def.items():
                amount = base_amount * val
                total_deduction_amount += amount
                deduction_results.append({
                    "id": name,
                    "name": name.capitalize(),
                    "type": "percentage",
                    "value": val,
                    "amount": amount
                })
        else:
            # Old format: List of dicts
            for deduction in deductions_def:
                d_id = deduction['id']
                d_type = deduction['type']
                d_val = deduction['value']
                
                amount = 0
                if d_type == 'percentage':
                    amount = base_amount * d_val
                elif d_type == 'fixed':
                    amount = d_val
                
                total_deduction_amount += amount
                deduction_results.append({
                    "id": d_id,
                    "name": deduction['name'],
                    "type": d_type,
                    "value": d_val,
                    "amount": amount
                })

        net_co2e = base_amount - total_deduction_amount

        return {
            "methodology_id": method_id,
            "inputs": inputs,
            "trace": trace,
            "gross_pre_deduction": base_amount,
            "deductions": deduction_results,
            "net_co2e": net_co2e
        }
