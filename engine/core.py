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
                    
                    if method == 'multiply':
                        val = 1.0
                        for v in operand_values:
                            val *= v
                        result = val
                        
                    elif method == 'subtract':
                        # First minus the rest
                        if len(operand_values) > 0:
                            result = operand_values[0]
                            for v in operand_values[1:]:
                                result -= v
                        else:
                            result = 0.0
                    
                    elif method == 'add': # Basic support
                         result = sum(operand_values)

                    else:
                        raise ValueError(f"Unknown method '{method}' in step {step_id}")
                    
                    context[output_key] = result
                    
                    trace.append({
                        "step_id": step_id,
                        "description": step_desc,
                        "formula": f"{method}({', '.join(step_inputs)})",
                        "result": result,
                        "unit": step.get('output_unit', '')
                    })
                    
                except Exception as e:
                     raise ValueError(f"Error in step {step_id}: {e}")
            
            # Identify Basis for Deductions (usually the last step's output)
            base_amount_key = steps[-1]['output']
            base_amount = context.get(base_amount_key, 0.0)

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
