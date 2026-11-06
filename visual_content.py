"""Channel guidance and deterministic composition of versioned copy over an image."""
from __future__ import annotations

import base64
import re
import unicodedata
from xml.sax.saxutils import escape


CHANNELS = {
    "Instagram": {"ratio": "portrait", "direction": "For an image post, lead with a clear visual idea and keep the caption separate. For Reels, write scenes and voiceover; never claim to render video."},
    "TikTok": {"ratio": "story", "direction": "Choose a photo post, cover, or short-video script to fit the brief. A photo post needs concise on-image copy and a separate caption; a video needs a hook, scenes, and voiceover."},
    "Facebook": {"ratio": "square", "direction": "Use an accessible image-led post with a conversational caption and one clear action when an image is requested."},
    "Threads": {"ratio": "portrait", "direction": "Prefer a conversational text post or a short thread; add an image card only when requested or useful. Avoid treating it as an Instagram caption."},
    "X": {"ratio": "landscape", "direction": "Use a concise standalone post or clearly numbered thread. For image-led content, keep the on-image message and post copy separate."},
    "Marketplace": {"ratio": "square", "direction": "Keep titles and listing details factual and scannable. Use a separate product image or image card when requested. Never invent price, discount, stock, or certification."},
}
CHANNEL_ALIASES = {"ig": "Instagram", "fb": "Facebook", "twitter": "X", "x/twitter": "X", "shopee": "Marketplace", "tokopedia": "Marketplace"}


def canonical_channel(value: str) -> str:
    normalized = value.strip().casefold()
    return next((name for name in CHANNELS if name.casefold() == normalized), CHANNEL_ALIASES.get(normalized, value.strip()))


def channel_guidance(platform: str) -> str:
    profile = CHANNELS.get(canonical_channel(platform))
    return profile["direction"] if profile else "Follow the channel named in the brief; do not invent platform requirements."


PLANNER_CHANNEL_INSTRUCTIONS = (
    " When the user requests caption only, use format Caption only and produce only accompanying post text, not an image task or script. "
    " Channel preferences are optional and separate from output formats. If supplied, create at least one task "
    "for each requested channel with that exact channel name in platform. Within one to six tasks, choose the "
    "deliverable for each channel from the brief: image post, photo post, static ad, product hero, video cover, "
    "video script, listing, or text post. An image request must produce an image-oriented task, not only a script. "
    "Do not force TikTok to mean video: a photo post or cover is also possible. Split a campaign bundle into "
    "channel-specific tasks when multiple channels are requested. Do not claim media was generated or published. "
    "Channel directions are editorial suggestions, not platform policy or guaranteed performance. "
    "Tone describes brand voice, not the publishing destination. The task platform and output format "
    "determine structure; apply the brand voice within them. A concise tone does not turn an Instagram "
    "task into an X post. For multiple channels keep the brand voice consistent while adapting each "
    "task structure. If tone text names a different channel, preserve its voice qualities without "
    "changing the requested destination or importing that other channel's format."
)


def is_image_format(output_format: str) -> bool:
    return bool(re.search(r"poster|static ad|image|photo|cover|banner|kartu|gambar|visual", output_format, re.I))


IMAGE_COPY_INSTRUCTIONS = (
    " For this image deliverable, label separate HEADLINE, BODY, CTA, CAPTION, and VISUAL blocks. "
    "HEADLINE is at most 70 characters, BODY 160, CTA 40; these three are the exact text to overlay. "
    "CAPTION is separate accompanying post copy; VISUAL describes only the base image with no text, logos, "
    "certification badges, or invented product packaging. Keep all claims in every block source-grounded. "
    "Treat overlay text as a quick visual hierarchy, not a paragraph: HEADLINE carries one main message, "
    "BODY uses only the few short phrases essential to understand that message, and CTA is one brief action. "
    "The character limits are ceilings, not targets; do not fill them. Aim for substantially less text on the "
    "image than in its accompanying explanatory caption when the brief calls for explanation. "
    "CAPTION supplies useful context, supporting details and a natural next step suited to the requested "
    "platform, audience and brand voice. Do not repeat the entire overlay word for word or pad a simple "
    "caption just to make it longer. Let the brief determine structure: no fixed grand-opening template, "
    "mandatory emojis, event fields, discounts or other campaign elements unless relevant and sourced. "
    "Keep material offer qualifications beside the offer on the image when omitting them would mislead; "
    "never hide them only in the caption to save space. Do not infer event or offer dates from task deadlines. "
    "For a single image keep the actual product photo visually dominant. Prefer a headline of roughly "
    "three to seven words when natural for the language and brief; this is editorial guidance, not a reason "
    "to remove essential qualifiers. Follow supplied brand colors and visual identity, not automatic "
    "food/organic color stereotypes. Visual directions must not request invented certification badges, "
    "testimonials or best-seller emblems, and exact lettering belongs in the overlay, not the base generator. "
    "Short copy is legitimate: do not pad it with invented benefits to reach a length. "
    "For a text-free product hero image, omit HEADLINE/BODY/CTA and provide CAPTION and VISUAL only."
)


class CompositionError(ValueError):
    pass


BLOCK = re.compile(r"^\s*(?:[>#*\-]\s*)*(HEADLINE|BODY|CTA|CAPTION|VISUAL(?: DIRECTION)?)\s*\**\s*:\s*\**\s*(.*)$", re.I)
LIMITS = {"headline": 80, "body": 180, "cta": 50}


def draft_image_blocks(content: str) -> dict[str, str]:
    blocks: dict[str, list[str]] = {}
    active = None
    content = re.sub(r"\\(?:r\\n|n)(?=(?:HEADLINE|BODY|CTA|CAPTION|VISUAL(?: DIRECTION)?)\s*:)", "\n", content, flags=re.I)
    for line in content.splitlines():
        match = BLOCK.match(line)
        if match:
            active = match[1].lower().replace(" direction", "")
            if active in blocks:
                raise CompositionError(f"The draft repeats {active.upper()}. Use one labelled block per field.")
            blocks[active] = [match[2].strip()]
        elif active and line.strip():
            blocks[active].append(line.strip())
    return {key: " ".join(value).strip() for key, value in blocks.items()}


def extract_image_copy(content: str) -> dict[str, str]:
    """Copy exact labelled text; never paraphrase, truncate, or accept HTML markup."""
    blocks = draft_image_blocks(content)
    copy = {key: blocks.get(key, "") for key in LIMITS}
    for key, value in copy.items():
        if len(value) > LIMITS[key]:
            raise CompositionError(f"{key.upper()} has {len(value)} characters; use at most {LIMITS[key]}. Edit the draft, then review it again.")
        if any(unicodedata.category(char) == "Cc" for char in value):
            raise CompositionError("On-image copy contains unsupported control characters.")
    if any(copy.values()) and not copy["headline"]:
        raise CompositionError("Add a labelled HEADLINE or remove all on-image copy for a text-free visual.")
    return copy


def _units(text: str) -> float:
    return sum(1 if unicodedata.east_asian_width(char) in ("W", "F") or char in "MWmw@%" else .75 if char.isupper() else .65 for char in text)


def _wrap(text: str, width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        if _units(word) > width:
            raise CompositionError("A word is too long for the canvas. Edit the draft instead of clipping the copy.")
        candidate = (current + " " + word).strip()
        if current and _units(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def composition_svg(image: bytes, media_type: str, size: str, copy: dict[str, str], overlays: list[dict] | None = None) -> bytes:
    if media_type not in ("image/png", "image/jpeg"):
        raise CompositionError("Only PNG and JPEG base images can be composed.")
    try:
        width, height = (int(part) for part in size.split("x"))
    except (ValueError, AttributeError):
        raise CompositionError("The stored canvas dimensions are invalid.")
    if not (256 <= width <= 4096 and 256 <= height <= 4096):
        raise CompositionError("The canvas dimensions are outside the supported range.")
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<title>AI-generated visual with versioned copy</title>',
                f'<image width="{width}" height="{height}" preserveAspectRatio="xMidYMid slice" href="data:{media_type};base64,{base64.b64encode(image).decode()}"/>']
    if any(copy.values()):
        padding = round(width * .06)
        available = width - 2 * padding
        scale = min(width / 1024, height / 1024 * 1.3)
        rows = []
        for key, base_size in (("headline", 56), ("body", 42), ("cta", 40)):
            font_size = round(base_size * scale)
            longest_word = max((_units(word) for word in copy.get(key, "").split()), default=1)
            fitted = min(font_size, int(available / longest_word))
            if fitted < font_size * .8:
                raise CompositionError("A word is too long for readable image copy. Edit the draft instead of clipping it.")
            font_size = fitted
            lines = _wrap(copy.get(key, ""), available / font_size)
            if lines:
                rows.append((key, font_size, lines))
        needed = 2 * padding + sum(len(lines) * size * 1.3 + 16 * scale for _, size, lines in rows)
        if needed > height * .64:
            raise CompositionError("The copy does not fit this canvas. Shorten the labelled blocks or choose a taller canvas; no text was clipped.")
        top = round(height - needed)
        elements.append(f'<rect y="{top}" width="{width}" height="{height-top}" fill="#173528"/>')
        y = top + padding
        for key, font_size, lines in rows:
            for line in lines:
                y += font_size * 1.3
                elements.append(f'<text x="{padding}" y="{round(y)}" fill="#ffffff" font-family="Arial, sans-serif" font-size="{font_size}" font-weight="{700 if key != "body" else 400}">{escape(line)}</text>')
            y += 16 * scale
    anchors = {
        "top_left": ("start", 0.06, 0.08), "top_center": ("middle", 0.5, 0.08), "top_right": ("end", 0.94, 0.08),
        "center_left": ("start", 0.06, 0.5), "center": ("middle", 0.5, 0.5), "center_right": ("end", 0.94, 0.5),
        "bottom_left": ("start", 0.06, 0.88), "bottom_center": ("middle", 0.5, 0.88), "bottom_right": ("end", 0.94, 0.88),
    }
    if overlays and len(overlays) > 8:
        raise CompositionError("Keep up to eight added labels in one image. Remove a label before adding another.")
    for overlay in overlays or []:
        text = overlay.get("text", "") if isinstance(overlay, dict) else ""
        position = overlay.get("position", "top_right") if isinstance(overlay, dict) else "top_right"
        if not isinstance(text, str) or not text.strip() or len(text) > 80 or position not in anchors:
            raise CompositionError("Chat edits must have readable text and a supported position.")
        alignment, x_ratio, y_ratio = anchors[position]
        font_size = max(28, round(min(width, height) * 0.055))
        max_units = max(5, (width * 0.62) / font_size)
        lines = _wrap(text.strip(), max_units)
        if len(lines) > 3:
            raise CompositionError("That text is too long for an image label. Shorten it in the edit chat.")
        line_height = round(font_size * 1.18)
        padding_x, padding_y = round(font_size * 0.42), round(font_size * 0.24)
        box_width = max(round(font_size * _units(line) + padding_x * 2) for line in lines)
        box_height = line_height * len(lines) + padding_y * 2
        x = round(width * x_ratio)
        y = round(height * y_ratio)
        box_x = x - box_width if alignment == "end" else x - box_width // 2 if alignment == "middle" else x
        box_y = y if "top" in position else y - box_height if "bottom" in position else y - box_height // 2
        box_x = min(max(0, box_x), width - box_width)
        box_y = min(max(0, box_y), height - box_height)
        text_x = box_x + padding_x if alignment == "start" else box_x + box_width - padding_x if alignment == "end" else box_x + box_width // 2
        baselines = [box_y + padding_y + font_size + index * line_height for index in range(len(lines))]
        elements.append(f'<g><rect x="{box_x}" y="{box_y}" width="{box_width}" height="{box_height}" rx="{round(font_size * .28)}" fill="#173528" fill-opacity=".94"/>')
        for line, baseline in zip(lines, baselines):
            elements.append(f'<text x="{text_x}" y="{baseline}" text-anchor="{alignment}" fill="#ffffff" font-family="Arial, sans-serif" font-size="{font_size}" font-weight="700">{escape(line)}</text>')
        elements.append("</g>")
    elements.append("</svg>")
    return "".join(elements).encode("utf-8")
