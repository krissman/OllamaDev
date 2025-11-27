# Configuration for OllamaDev

# --- Ollama API Settings ---
OLLAMA_BASE_URL = "http://10.73.78.161:11434"
OLLAMA_GENERATE_ENDPOINT = f"{OLLAMA_BASE_URL}/api/generate"

# --- LLM Model Selection ---
# Use a strong code model available on your local Ollama instance.
# Example models: codellama:7b-instruct, mixtral:8x7b-instruct-v0.1-q4_0
DEFAULT_MODEL = "qwen3-coder:30b"
