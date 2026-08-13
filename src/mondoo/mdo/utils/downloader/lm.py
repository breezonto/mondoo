from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer, TextStreamer
import sys

model_name = "deepseek-ai/DeepSeek-OCR"
save_path = f"/home/breeze/workspace/models/deepseek-ai/DeepSeek-OCR"

IF_TEST = False
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
# model = AutoModelForCausalLM.from_pretrained(
#     model_name,
#     device_map="auto",           # auto-dispatch to GPU if available
#     torch_dtype="auto",          # use float16 if supported
# )
model = AutoModel.from_pretrained(
    model_name, 
    _attn_implementation='flash_attention_2', 
    trust_remote_code=True, 
    use_safetensors=True)

tokenizer.save_pretrained(save_path)
model.save_pretrained(save_path)
import torch
model = model.eval().cuda().to(torch.bfloat16)
print(model)

if IF_TEST is True:
    prompt = "Write a short poem about the sea."
    print("Prompt:", prompt)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    print("Answer:")
    streamer = TextStreamer(tokenizer, skip_special_tokens=True, skip_prompt=True)
    output = model.generate(**inputs, streamer=streamer, max_new_tokens=500)
    print(f"Size of tokens generated: {len(output[0])}")
    print(output.shape)

# streamer = TextIteratorStreamer(tokenizer, skip_special_tokens=True)

# Chat interface
# prompt = "Write a short poem about the sea."
# print("Prompt:", prompt)
# inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
# _ = model.generate(**inputs, 
#                    max_new_tokens=500,
#                    streamer=streamer)
