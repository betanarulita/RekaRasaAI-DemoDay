"""Channel guidance and deterministic composition of versioned copy over an image."""
from __future__ import annotations

import base64
import re
import unicodedata
from io import BytesIO
from xml.sax.saxutils import escape


CHANNELS = {
    "Instagram": {"ratio": "portrait", "direction": "Write for a visual feed but do not invent an image deliverable. Let the caption support the Planner's angle with a specific opening and a natural rhythm; keep it concise when the idea is simple. If an image or carousel is requested, make the copy work with the visual and keep slide text distinct from the caption."},
    "TikTok": {"ratio": "story", "direction": "For a video script, write a shootable sequence with visual action, spoken or on-screen lines, and pacing that differs from a caption. Open with an image, action, useful detail, or line that fits the idea, not a default question. Use conversational language; a CTA is optional. For a requested photo post, separate on-image copy from caption."},
    "Facebook": {"ratio": "square", "direction": "Use a conversational post suited to sharing context or inviting a real response. Keep the ask proportionate to the goal; do not append a sales CTA by default. Pair with an image only when the format requests it."},
    "Threads": {"ratio": "portrait", "direction": "Write like a concise conversational thought or a short, connected thread. Make one clear point and leave room for a genuine reply when engagement is the goal. Do not reuse an Instagram caption structure or add an image unless requested."},
    "X": {"ratio": "landscape", "direction": "Write a direct standalone thought or a coherent numbered thread when the idea needs room. Prefer a concrete observation over a promotional opener. Keep image copy separate when an image is requested."},
    "Marketplace": {"ratio": "square", "direction": "Use a clear product title and scannable factual listing language. Include only sourced attributes. Never invent price, discount, stock, shipping, or certification; omit missing details."},
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
    "for each requested channel with that exact channel name in platform. In normal chat, choose text-first "
    "deliverables unless the brief explicitly requests an image/gambar, photo/foto, poster, visual, or other image output; "
    "never choose an image solely because a channel is visual. For an explicit image request, choose an image-oriented "
    "task such as image post, photo post, static ad, product hero, or video cover, not only a script. "
    "Adapt text structure to each channel and do not force TikTok to mean video. "
    "Split a campaign bundle into channel-specific tasks when multiple channels are requested. Do not claim media was generated or published. "
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


def _quiet_text_anchor(image: bytes, width: int, height: int, box_width: int, box_height: int) -> tuple[str, float]:
    """Place exact copy in a visually quiet area instead of a fixed footer band."""
    candidates = {
        "top_left": (0.06, 0.06, "start"), "top_center": (0.5, 0.06, "middle"), "top_right": (0.94, 0.06, "end"),
        "center_left": (0.06, 0.5, "start"), "center": (0.5, 0.5, "middle"), "center_right": (0.94, 0.5, "end"),
        "bottom_left": (0.06, 0.94, "start"), "bottom_center": (0.5, 0.94, "middle"), "bottom_right": (0.94, 0.94, "end"),
    }
    try:
        from PIL import Image, ImageFilter, ImageStat

        with Image.open(BytesIO(image)) as source:
            source.load()
            gray = source.convert("L").resize((96, 96))
            edge = gray.filter(ImageFilter.FIND_EDGES)
            crop_w = max(1, min(96, round(box_width / width * 96)))
            crop_h = max(1, min(96, round(box_height / height * 96)))
            ranked = []
            for name, (x_ratio, y_ratio, alignment) in candidates.items():
                x = round(x_ratio * 96 - (crop_w if alignment == "end" else crop_w / 2 if alignment == "middle" else 0))
                y = round(y_ratio * 96 - (crop_h if y_ratio > 0.5 else 0 if y_ratio < 0.5 else crop_h / 2))
                x, y = min(max(0, x), 96 - crop_w), min(max(0, y), 96 - crop_h)
                region = (x, y, x + crop_w, y + crop_h)
                texture = ImageStat.Stat(gray.crop(region)).stddev[0]
                edges = ImageStat.Stat(edge.crop(region)).mean[0]
                luminance = ImageStat.Stat(gray.crop(region)).mean[0]
                ranked.append((texture + edges * 0.35, name, luminance))
            _, anchor, luminance = min(ranked)
            return anchor, luminance
    except Exception:
        return "bottom_left", 96.0


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
        padding_x = round(width * .045)
        padding_y = round(width * .035)
        available = round(width * .82)
        scale = min(width / 1024, height / 1024 * 1.3)
        rows = []
        for key, base_size in (("headline", 64), ("body", 38), ("cta", 34)):
            font_size = round(base_size * scale)
            longest_word = max((_units(word) for word in copy.get(key, "").split()), default=1)
            fitted = min(font_size, int(available / longest_word))
            if fitted < font_size * .8:
                raise CompositionError("A word is too long for readable image copy. Edit the draft instead of clipping it.")
            font_size = fitted
            lines = _wrap(copy.get(key, ""), available / font_size)
            if lines:
                rows.append((key, font_size, lines))
        needed = 2 * padding_y + sum(len(lines) * size * (1.16 if key == "headline" else 1.3) + 12 * scale for key, size, lines in rows)
        if needed > height * .64:
            raise CompositionError("The copy does not fit this canvas. Shorten the labelled blocks or choose a taller canvas; no text was clipped.")
        max_line = max((_units(line) * size for _, size, lines in rows for line in lines), default=available * .6)
        card_width = min(width - 2 * padding_x, round(max_line + 2 * padding_x))
        card_height = round(needed)
        anchor, luminance = _quiet_text_anchor(image, width, height, card_width, card_height)
        alignment, x_ratio, y_ratio = {
            "top_left": ("start", .06, .06), "top_center": ("middle", .5, .06), "top_right": ("end", .94, .06),
            "center_left": ("start", .06, .5), "center": ("middle", .5, .5), "center_right": ("end", .94, .5),
            "bottom_left": ("start", .06, .94), "bottom_center": ("middle", .5, .94), "bottom_right": ("end", .94, .94),
        }[anchor]
        box_x = round(width * x_ratio - (card_width if alignment == "end" else card_width / 2 if alignment == "middle" else 0))
        box_y = round(height * y_ratio - (card_height if y_ratio > .5 else 0 if y_ratio < .5 else card_height / 2))
        box_x, box_y = min(max(0, box_x), width - card_width), min(max(0, box_y), height - card_height)
        light_backing = luminance > 145
        panel = "#172b31" if light_backing else "#fffaf1"
        ink = "#fffaf1" if light_backing else "#172b31"
        text_anchor = "middle" if alignment == "middle" else alignment
        text_x = box_x + card_width // 2 if alignment == "middle" else box_x + padding_x if alignment == "start" else box_x + card_width - padding_x
        radius = round(min(width, height) * .035)
        elements.append(f'<rect x="{box_x}" y="{box_y}" width="{card_width}" height="{card_height}" rx="{radius}" fill="{panel}" fill-opacity=".91"/>')
        y = box_y + padding_y
        for key, font_size, lines in rows:
            for line in lines:
                y += font_size * (1.16 if key == "headline" else 1.3)
                family = "Georgia, serif" if key == "headline" else "Arial, sans-serif"
                weight = 700 if key != "body" else 400
                elements.append(f'<text x="{text_x}" y="{round(y)}" text-anchor="{text_anchor}" fill="{ink}" font-family="{family}" font-size="{font_size}" font-weight="{weight}">{escape(line)}</text>')
            y += 12 * scale
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
