"""Core-node SD workflows. Reference images are encoded, not described from filenames."""

import math


def image_options(mode, strength=None, seed=None):
    if mode not in ("concept", "img2img", "edit"):
        raise ValueError("Choose text-to-image, image-to-image, or protected background editing.")
    if strength is None:
        strength = 0.75 if mode == "edit" else 0.35
    if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not math.isfinite(strength) or not 0.1 <= strength <= 0.85:
        raise ValueError("Image change strength must be between 0.1 and 0.85.")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32):
        raise ValueError("Seed must be an integer between 0 and 4294967295.")
    return float(strength), seed


def build_workflow(checkpoint, prompt, size, negative_prompt, seed, reference_name=None, mask_name=None, strength=0.35):
    width, height = (int(part) for part in size.split("x", 1))
    if not 8 <= width <= 8192 or not 8 <= height <= 8192 or width * height > 24_000_000:
        raise ValueError("Use a photo below 24 megapixels and 8192 pixels per side.")
    if mask_name and not reference_name:
        raise ValueError("A protection mask requires a source photo.")
    mode = "edit" if mask_name else "img2img" if reference_name else "concept"
    strength, seed = image_options(mode, strength, seed)
    if seed is None:
        raise ValueError("Resolve the generation seed before building the workflow.")
    scale = min(1, 512 / max(width, height))
    work_width = max(64, int(width * scale) // 8 * 8)
    work_height = max(64, int(height * scale) // 8 * 8)
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": work_width, "height": work_height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 25, "cfg": 7.0,
              "sampler_name": "euler", "scheduler": "normal", "denoise": strength if reference_name else 1.0,
              "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "15": {"class_type": "ImageScale", "inputs": {"image": ["6", 0], "upscale_method": "lanczos", "width": width, "height": height, "crop": "disabled"}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "rekarasa", "images": ["15", 0]}},
    }
    if reference_name:
        graph["8"] = {"class_type": "LoadImage", "inputs": {"image": reference_name}}
        graph["11"] = {"class_type": "ImageScale", "inputs": {"image": ["8", 0], "upscale_method": "lanczos", "width": work_width, "height": work_height, "crop": "disabled"}}
        graph["4"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["1", 2]}}
    if mask_name:
        graph["9"] = {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}}
        graph["12"] = {"class_type": "MaskToImage", "inputs": {"mask": ["9", 0]}}
        graph["13"] = {"class_type": "ImageScale", "inputs": {"image": ["12", 0], "upscale_method": "nearest-exact", "width": work_width, "height": work_height, "crop": "disabled"}}
        graph["14"] = {"class_type": "ImageToMask", "inputs": {"image": ["13", 0], "channel": "red"}}
        graph["4"] = {"class_type": "VAEEncodeForInpaint", "inputs": {"pixels": ["11", 0], "vae": ["1", 2], "mask": ["14", 0], "grow_mask_by": 0}}
        # Blend at original resolution: protected pixels bypass the diffusion result.
        graph["10"] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": ["8", 0], "source": ["15", 0], "mask": ["9", 0], "x": 0, "y": 0, "resize_source": False}}
        graph["7"]["inputs"]["images"] = ["10", 0]
    return graph
