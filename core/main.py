import os
from dotenv import load_dotenv
from core.engine import RLMEngine

load_dotenv()

def main():
    engine = RLMEngine(
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("VAULT_PATH", "./vault/history.txt"),
        os.getenv("CACHE_PATH", "./vault/ai_fixes.json"),
    )
    
    # Test with a dummy log
    sample_error = "ConnectionTimeout: Target 10.0.0.5:8080 unreachable."
    report = engine.debug(sample_error)
    print(f"Engine Diagnosis: {report}")

if __name__ == "__main__":
    main()
