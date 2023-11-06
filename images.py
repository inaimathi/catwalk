import torch
from diffusers import DiffusionPipeline, StableDiffusionPipeline

import util


def load_model(name, gpu="1080", loras=[]):
    if name.endswith("safetensors"):
        pipe = StableDiffusionPipeline.from_single_file(name)
    else:
        pipe = DiffusionPipeline.from_pretrained(name, torch_dtype=torch.float16, use_safetensors=True, variant="fp16")
    for l in loras:
        pipe.load_lora_weights(l)
    util.to_gpu(pipe, gpu)
    return pipe

def generate_image(
        prompt, negative_prompt=None,
        steps=50, width=1024, height=1024, seed=None,
        model="stabilityai/stable-diffusion-xl-base-1.0",
        loras=[],
        gpu="1080"):
    pipe = load_model(model, loras=loras, gpu=gpu)
    inp = {
        "prompt": prompt, "negative_prompt": negative_prompt,
        "num_inference_steps": steps,
        "width": width, "height": height
    }
    if seed is not None:
        gen = torch.Generator(util.dev_by(gpu)).manual_seed(seed)
        inp["generator"] = gen
    if len(loras) > 0:
        inp["cross_attention_kwargs"] = {"scale": 0.5}
    if negative_prompt is not None:
        inp["negative_prompt"] = negative_prompt
    images = pipe(**inp).images
    fname = util.fresh_file("image-", ".png")
    images[0].save(fname)
    return fname
