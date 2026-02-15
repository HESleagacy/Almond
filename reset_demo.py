import json
import os

VAULT_PATH = "vault/ai_fixes.json"

def reset_demo():
    print(f"Resetting {VAULT_PATH} for fresh demo...")
    
    if not os.path.exists(VAULT_PATH):
        print("Vault file not found. Nothing to reset.")
        return

    try:
        with open(VAULT_PATH, "r") as f:
            data = json.load(f)
        
        # Filter out the "Deadlock" entry or any entry with id "491daac04090"
        # Since the ID might change if generated again, we filter by signature "Deadlock"
        original_count = len(data)
        new_data = [
            item for item in data 
            if item.get("error_signature") != "Deadlock"
        ]
        
        if len(new_data) < original_count:
            print(f"Removed {original_count - len(new_data)} entries (Deadlock fix).")
            with open(VAULT_PATH, "w") as f:
                json.dump(new_data, f, indent=2)
            print("Reset Complete. Tier 3 will now synthesize from scratch.")
        else:
            print("No 'Deadlock' entries found. Already clean.")

    except Exception as e:
        print(f"Error resetting demo: {e}")

if __name__ == "__main__":
    reset_demo()
