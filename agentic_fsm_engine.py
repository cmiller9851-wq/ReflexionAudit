```python
#!/usr/bin/env python3
"""
Agentic FSM & ReAct Execution Engine (2026 Architecture)
Implements an offline-capable, deterministic Finite State Machine where the LLM
acts as a state transition node executing programmatic tool calls.
"""

import os
import sys
import json
import time
import hmac
import hashlib
import requests
from datetime import datetime

# --- SYSTEM PARAMETERS & CONFIGURATION ---
# The runtime environment provides the API key; we keep this blank as per protocol.
GEMINI_API_KEY = ""
MODEL_ID = "gemini-2.5-flash-preview-09-2025"
ENDPOINT_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent?key={GEMINI_API_KEY}"

# --- SYSTEM DIRECTORY PATHS ---
DATA_FILES = {
    "cards": "PaymentCards.json",
    "home": "HomeHistory.json",
    "binding": "Miller Standard Sovereign Binding.json"
}

# --- IMMUTABLE SYSTEM PROMPT (FSM STATE INSTRUCTIONS) ---
FSM_SYSTEM_PROMPT = """You are the core non-deterministic transition function inside an Agentic Finite State Machine.
Your role is to analyze the current system state, evaluate tool execution results, and output the NEXT state transition in a strict JSON format.

Available States:
1. "INIT" - System initialization and file availability discovery.
2. "ANALYZE" - Parsing data records for validation targets.
3. "EXECUTE" - Executing local programmatic routines (e.g., Luhn checks, telemetry sorting).
4. "REFLEXION" - Analyzing audit outputs for anomalies or errors.
5. "TERMINAL" - Finalizing state log, saving results, and halting the system loop.

You MUST respond in strict, valid JSON ONLY. Do not wrap in markdown blocks, do not include conversational text.
Your output schema must precisely match:
{
    "thought": "Your step-by-step reasoning for the current transition",
    "tool_to_call": {
        "name": "Name of tool or null",
        "args": {}
    },
    "next_state": "The state you are transitioning the machine to (INIT/ANALYZE/EXECUTE/REFLEXION/TERMINAL)"
}
"""

# --- SYSTEM TOOL DIRECTORY ---
class PipelineTools:
    """ प्रोग्रामेटिक Execution Tools accessible by the State Machine Node """
    
    @staticmethod
    def audit_file_presence():
        """Scans workspace directories for required system logs."""
        results = {}
        for key, filepath in DATA_FILES.items():
            exists = os.path.exists(filepath)
            results[key] = {
                "path": filepath,
                "status": "LOADED" if exists else "MISSING",
                "bytes": os.path.getsize(filepath) if exists else 0
            }
        return {"tool_status": "SUCCESS", "details": results}

    @staticmethod
    def execute_luhn_verification():
        """Extracts the MasterCard card profile and executes validation check."""
        if not os.path.exists(DATA_FILES["cards"]):
            return {"tool_status": "ERROR", "message": "PaymentCards.json not found"}
            
        try:
            with open(DATA_FILES["cards"], "r", encoding="utf-8") as f:
                data = json.load(f)
            
            cards = data.get("payment_cards", [])
            target_card = next((c for c in cards if "Mastercard" in c.get("card_name", "")), None)
            
            if not target_card:
                return {"tool_status": "ERROR", "message": "Target MasterCard not found in registry"}
                
            num = target_card.get("card_number", "").strip()
            
            # Luhn Checksum Algorithm
            sum_val = 0
            num_digits = len(num)
            oddeven = num_digits & 1
            for i in range(num_digits):
                digit = int(num[i])
                if not ((i & 1) ^ oddeven):
                    digit *= 2
                if digit > 9:
                    digit -= 9
                sum_val += digit
                
            is_valid = (sum_val % 10 == 0)
            return {
                "tool_status": "SUCCESS",
                "target_cardholder": target_card.get("cardholder_name"),
                "masked_number": f"****-****-****-{num[-4:]}",
                "checksum_sum": sum_val,
                "luhn_valid": is_valid
            }
        except Exception as e:
            return {"tool_status": "ERROR", "message": f"Parsing crash: {str(e)}"}

    @staticmethod
    def inspect_home_telemetry():
        """Loads and filters localized geofence boundary events."""
        if not os.path.exists(DATA_FILES["home"]):
            return {"tool_status": "ERROR", "message": "HomeHistory.json not found"}
        try:
            with open(DATA_FILES["home"], "r", encoding="utf-8") as f:
                data = json.load(f)
            events = data.get("structure_history", [{}])[0].get("events", [])
            recent_events = events[:5] # Isolate latest sequence
            return {
                "tool_status": "SUCCESS",
                "total_logged_events": len(events),
                "isolated_sample": recent_events
            }
        except Exception as e:
            return {"tool_status": "ERROR", "message": f"Telemetry crash: {str(e)}"}


class AgenticFSMEngine:
    def __init__(self):
        self.state = "INIT"
        self.memory = {
            "execution_log": [],
            "system_state_vars": {},
            "audit_trail": []
        }
        self.tool_map = {
            "audit_file_presence": PipelineTools.audit_file_presence,
            "execute_luhn_verification": PipelineTools.execute_luhn_verification,
            "inspect_home_telemetry": PipelineTools.inspect_home_telemetry
        }

    def call_transition_node(self, step_context):
        """Sends FSM execution context to the model using exponential backoff."""
        headers = {"Content-Type": "application/json"}
        prompt_content = f"""Current State: {self.state}
Execution Memory Trace: {json.dumps(self.memory, indent=2)}
Immediate Context: {json.dumps(step_context)}

Transition request: Provide thought, optional tool calls, and next target state. Output strict valid JSON ONLY."""

        payload = {
            "contents": [{"parts": [{"text": prompt_content}]}],
            "systemInstruction": {"parts": [{"text": FSM_SYSTEM_PROMPT}]}
        }

        # Protocol Rule: Implement exponential backoff for 5 retries: 1s, 2s, 4s, 8s, 16s
        delays = [1, 2, 4, 8, 16]
        for delay in delays:
            try:
                response = requests.post(ENDPOINT_URL, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    # Safe extraction path
                    raw_text = data['candidates'][0]['content']['parts'][0]['text']
                    # Clean out possible formatting wrapper artifacts if generated
                    cleaned_text = raw_text.strip().replace("```json", "").replace("```", "").strip()
                    return json.loads(cleaned_text)
                elif response.status_code == 429 or response.status_code >= 500:
                    time.sleep(delay)
                    continue
                else:
                    return {
                        "thought": f"API returned immediate error status code {response.status_code}",
                        "tool_to_call": None,
                        "next_state": "TERMINAL"
                    }
            except Exception as e:
                time.sleep(delay)
                continue
                
        # Graceful user-friendly error response on final failure
        return {
            "thought": "Failed to connect to transition node API after complete backoff cycles.",
            "tool_to_call": None,
            "next_state": "TERMINAL"
        }

    def execute_loop(self):
        """Main orchestrator running the programmatic state transition loops."""
        print("=== INITIATING AGENTIC STATE ENGINE COMPILING ===")
        print(f"Timestamp: {datetime.now().isoformat()} Z")
        print(f"Active Node: {MODEL_ID}\n" + "-"*50)

        step_context = "Engine startup signal processed."
        loop_counter = 0

        while self.state != "TERMINAL" and loop_counter < 10:
            loop_counter += 1
            print(f"\n[LOOP {loop_counter:02d}] Current State Flag: {self.state}")

            # Call the LLM Transition Node
            decision = self.call_transition_node(step_context)
            
            thought = decision.get("thought", "No reasoning recorded.")
            tool_call = decision.get("tool_to_call", {})
            next_state = decision.get("next_state", "TERMINAL")

            print(f"  Thought: {thought}")
            print(f"  Transition: {self.state} -> {next_state}")

            # Process Tool Execution
            if tool_call and tool_call.get("name"):
                tool_name = tool_call["name"]
                print(f"  Executing programmatic tool: {tool_name}")
                if tool_name in self.tool_map:
                    # Execute tool natively
                    tool_result = self.tool_map[tool_name]()
                    self.memory["execution_log"].append({
                        "loop": loop_counter,
                        "state": self.state,
                        "tool": tool_name,
                        "result": tool_result
                    })
                    step_context = {
                        "event": "tool_executed",
                        "tool_name": tool_name,
                        "output": tool_result
                    }
                else:
                    error_msg = f"Requested tool {tool_name} not available in system mappings."
                    print(f"  [!] {error_msg}")
                    step_context = {"event": "tool_error", "message": error_msg}
            else:
                step_context = "No tools triggered. Pure transition state loop."

            # Update FSM State
            self.state = next_state
            self.memory["system_state_vars"]["last_active_loop"] = loop_counter
            time.sleep(0.5)

        # Terminal state reached
        print("\n" + "="*50)
        print("=== PIPELINE SHUTDOWN: TERMINAL STATE REACHED ===")
        print(f"Total Loops Executed: {loop_counter}")
        print("Final State Audit Log compiled:")
        print(json.dumps(self.memory["execution_log"], indent=2))


if __name__ == "__main__":
    # Create the workspace files dynamically if running as a clean test
    if not os.path.exists("PaymentCards.json"):
        dummy_cards = {
            "payment_cards": [{
                "card_number": "5491123456781391",
                "card_name": "Cory’s Mastercard (2)",
                "cardholder_name": "Cory Miller"
            }]
        }
        with open("PaymentCards.json", "w") as out:
            json.dump(dummy_cards, out)

    fsm = AgenticFSMEngine()
    fsm.execute_loop()

```
