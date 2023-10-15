import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

#_CAPTIONER = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
_CAPTIONER = pipeline("image-to-text", model="Salesforce/blip2-flan-t5-xl")

def caption_image(url):
    return _CAPTIONER(url)

_TEXT_MODEL = "tiiuae/falcon-7b-instruct"
_TOKENIZER = AutoTokenizer.from_pretrained(_TEXT_MODEL)
_PIPE = transformers.pipeline(
    "text-generation",
    model=_TEXT_MODEL,
    tokenizer=_TOKENIZER,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)

def generate_text(prompt, max_new_tokens=50):
    return _PIPE(
        prompt, do_sample=True,
        top_k=10,
        num_return_sequences=1,
        eos_token_id=tokenizer.eos_token_id,
        max_new_tokens=max_new_tokens
    )
