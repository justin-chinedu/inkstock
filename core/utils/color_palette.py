import json
import requests


def gen_svg_template(width: int, height: int, colors: list[list[int]]) -> str:
    unit_width = width / len(colors)
    colors_hex = list(map(lambda rgb: '#{:02x}{:02x}{:02x}'.format(*rgb), colors))
    svg = """<svg
           width="{width}px"
           height="{height}px"
           viewBox="0 0 {width} {height}"
           version="1.1"
           id="inkstock_colorio"
           xmlns="http://www.w3.org/2000/svg"
           xmlns:svg="http://www.w3.org/2000/svg">
             <g id="palette">
             {rects}
             </g>
        </svg>
     """
    rect = """<rect
       style="fill:{fill};stroke:#000000;stroke-width:0;"
       id="{rect_id}"
       width="{width}"
       height="{height}"
       x="{position}"
       y="0"
    />"""

    rects = ""
    for index, color in enumerate(colors_hex):
        rect_format = rect.format(rect_id=f"rect{index}", width=unit_width, height=height, fill=color,
                                  position=unit_width * index) + "\n"
        rects = rects + rect_format + "\n"
    result = svg.format(width=width, height=height, rects=rects)
    return result


def fetch_palette_from_colors(colors: list[list[int]], no_of_colors: int = 5,
                              model: str = "default") -> list[list[int]]:
    colors_req = []

    for index in range(no_of_colors):
        if index < len(colors):
            colors_req.append(colors[index])
        else:
            colors_req.append("N")

    data = {
        "model": model,
        "input": colors_req
    }
    resp = requests.post('http://colormind.io/api/', data=json.dumps(data))
    return resp.json()["result"]


def fetch_palette_random(model: str = "default") -> list[list[int]]:
    data = {
        "model": model
    }
    resp = requests.post('http://colormind.io/api/', data=json.dumps(data))
    return resp.json()["result"]


def gen_random_svg_palettes(no_of_palettes: int) -> list[str]:
    svgs = []
    for index in range(no_of_palettes):
        palette = fetch_palette_random()
        svg = gen_svg_template(72, 48, palette)
        svgs.append(svg)
    return svgs


def gen_random_svg_palette() -> str:
    palette = fetch_palette_random()
    svg = gen_svg_template(72, 48, palette)
    return svg


def gen_svg_palette(pref_colors: list[list[int]]) -> str:
    palette = fetch_palette_from_colors(colors=pref_colors)
    svg = gen_svg_template(72, 48, palette)
    return svg

# if __name__ == '__main__':
#     svgs = gen_random_svg_palettes(6)
#     for svg in svgs:
#         with open(f"/sdcard/swatch{str(id(svg))}.svg", mode="w+") as f:
#             f.writelines(svg)
