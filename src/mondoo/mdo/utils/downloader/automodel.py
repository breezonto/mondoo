from transformers import AutoModel, AutoTokenizer
import torch
import os

# Model configuration
LOCAL_MODEL_DIR = "/home/easyai/workspace/models"
model_name = "BAAI/bge-base-zh-v1.5"
save_path = os.path.join(LOCAL_MODEL_DIR, "embedding/BAAI-bge-base-zh-v1.5")

IF_TEST = False

# Make sure the save path exists
os.makedirs(save_path, exist_ok=True)

# Load tokenizer and model
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModel.from_pretrained(
    model_name,
    trust_remote_code=True,
    use_safetensors=True  # BGE provides safetensors weights
)

# Save locally
tokenizer.save_pretrained(save_path)
model.save_pretrained(save_path)

# Move model to GPU if available and set evaluation mode
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device).eval()
print(f"Model loaded on {device}:")
print(model)

# Optional test embedding
if IF_TEST:
    prompt = "谨慎投资类项目"
    print("Test prompt:", prompt)
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        embeddings = model(**inputs).last_hidden_state.mean(dim=1)  # simple mean pooling
    print("Embedding vector size:", embeddings.shape)
