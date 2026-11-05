"""Render private Slack chart files in the BUSY Bar visual language."""

from datetime import date
from io import BytesIO
import math

from PIL import Image, ImageDraw, ImageFont


def render_chart(
    title: str,
    timezone: str,
    labels: list[str],
    values: list[int | None],
    pending: list[bool] | None = None,
    note: str = "",
) -> bytes:
    """Draw adjoining gradient columns with explicit unknown-data markers.

    Return PNG bytes for authenticated Slack file upload, never a public URL.
    """
    if not values or len(values) != len(labels) or len(values) > 366:
        raise ValueError("Invalid chart series")
    pending = pending or [False] * len(values)
    if len(pending) != len(values):
        raise ValueError("Invalid pending mask")
    image = Image.new("RGB", (1200, 640), "#141414")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=30)
    font = ImageFont.load_default(size=20)
    draw.text((48, 28), title, fill="white", font=title_font)
    draw.text((48, 72), f"Timezone: {timezone}", fill="#b0b0b0", font=font)
    known = [value for value in values if value is not None]
    if any(value < 0 for value in known):
        raise ValueError("Sales cannot be negative")
    maximum = max(known, default=0)
    scale_maximum = max(1, maximum)
    step = max(1, math.ceil(scale_maximum / 4))
    scale_maximum = step * math.ceil(scale_maximum / step)
    left, right, top, bottom = 80, 1152, 130, 520
    for tick in range(0, scale_maximum + 1, step):
        y = bottom - round(tick / scale_maximum * (bottom-top))
        draw.line((left, y, right, y), fill="#303030")
        draw.text((left-12, y), str(tick), anchor="rm", fill="#b0b0b0", font=font)
    for index, value in enumerate(values):
        x0 = left + index * (right-left) // len(values)
        x1 = left + (index+1) * (right-left) // len(values) - 1
        if pending[index]:
            if index % max(1, (len(values)+11)//12) == 0:
                draw.text((x0, bottom+14), labels[index], fill="#606060", font=font)
            continue
        if value is None:
            draw.line((x0, bottom, x1, bottom), fill="#606060")
        else:
            height = max(1, round(value / scale_maximum * (bottom-top)))
            for y in range(bottom-height, bottom):
                ratio = (bottom-1-y) / (bottom-top-1)
                strength = round(ratio * 29) / 29
                color = (round(144+111*strength), round(232-187*strength), round(154-119*strength))
                draw.line((x0, y, x1, y), fill=color)
            if value > 0 and len(values) <= 31:
                text = str(value)
                draw.text(((x0+x1)/2, max(top-24, bottom-height-25)), text,
                    anchor="mt", fill="white", font=font)
        if index % max(1, (len(values)+11)//12) == 0:
            draw.text((x0, bottom+14), labels[index], fill="#b0b0b0", font=font)
    total = sum(known)
    draw.text((48, 590), f"Total: {total:,}    Max: {maximum:,}", fill="white", font=font)
    if note:
        draw.text((650, 590), note, fill="#b0b0b0", font=font)
    elif any(value is None and not future for value, future in zip(values, pending)):
        draw.text((650, 590), "Gray: missing observations", fill="#b0b0b0", font=font)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
