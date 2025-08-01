import re
from typing import Optional

NAMES = {
  0x000000: "CSS: black",
  0xc0c0c0: "CSS: silver",
  0x808080: "CSS: gray",
  0xffffff: "CSS: white",
  0x800000: "CSS: maroon",
  0xff0000: "CSS: red",
  0x800080: "CSS: purple",
  0xff00ff: "CSS: fuchsia",
  0x008000: "CSS: green",
  0x00ff00: "CSS: lime",
  0x808000: "CSS: olive",
  0xffff00: "CSS: yellow",
  0x000080: "CSS: navy",
  0x0000ff: "CSS: blue",
  0x008080: "CSS: teal",
  0x00ffff: "CSS: aqua",
  0xffa500: "CSS2: orange",
  0xf0f8ff: "CSS3: aliceblue",
  0xfaebd7: "CSS3: antiquewhite",
  0x7fffd4: "CSS3: aquamarine",
  0xf0ffff: "CSS3: azure",
  0xf5f5dc: "CSS3: beige",
  0xffe4c4: "CSS3: bisque",
  0xffebcd: "CSS3: blanchedalmond",
  0x8a2be2: "CSS3: blueviolet",
  0xa52a2a: "CSS3: brown",
  0xdeb887: "CSS3: burlywood",
  0x5f9ea0: "CSS3: cadetblue",
  0x7fff00: "CSS3: chartreuse",
  0xd2691e: "CSS3: chocolate",
  0xff7f50: "CSS3: coral",
  0x6495ed: "CSS3: cornflowerblue",
  0xfff8dc: "CSS3: cornsilk",
  0xdc143c: "CSS3: crimson",
  0x00008b: "CSS3: darkblue",
  0x008b8b: "CSS3: darkcyan",
  0xb8860b: "CSS3: darkgoldenrod",
  0xa9a9a9: "CSS3: darkgray",
  0x006400: "CSS3: darkgreen",
  0xbdb76b: "CSS3: darkkhaki",
  0x8b008b: "CSS3: darkmagenta",
  0x556b2f: "CSS3: darkolivegreen",
  0xff8c00: "CSS3: darkorange",
  0x9932cc: "CSS3: darkorchid",
  0x8b0000: "CSS3: darkred",
  0xe9967a: "CSS3: darksalmon",
  0x8fbc8f: "CSS3: darkseagreen",
  0x483d8b: "CSS3: darkslateblue",
  0x2f4f4f: "CSS3: darkslategray",
  0x00ced1: "CSS3: darkturquoise",
  0x9400d3: "CSS3: darkviolet",
  0xff1493: "CSS3: deeppink",
  0x00bfff: "CSS3: deepskyblue",
  0x696969: "CSS3: dimgray",
  0x1e90ff: "CSS3: dodgerblue",
  0xb22222: "CSS3: firebrick",
  0xfffaf0: "CSS3: floralwhite",
  0x228b22: "CSS3: forestgreen",
  0xdcdcdc: "CSS3: gainsboro",
  0xf8f8ff: "CSS3: ghostwhite",
  0xffd700: "CSS3: gold",
  0xdaa520: "CSS3: goldenrod",
  0xadff2f: "CSS3: greenyellow",
  0xf0fff0: "CSS3: honeydew",
  0xff69b4: "CSS3: hotpink",
  0xcd5c5c: "CSS3: indianred",
  0x4b0082: "CSS3: indigo",
  0xfffff0: "CSS3: ivory",
  0xf0e68c: "CSS3: khaki",
  0xe6e6fa: "CSS3: lavender",
  0xfff0f5: "CSS3: lavenderblush",
  0x7cfc00: "CSS3: lawngreen",
  0xfffacd: "CSS3: lemonchiffon",
  0xadd8e6: "CSS3: lightblue",
  0xf08080: "CSS3: lightcoral",
  0xe0ffff: "CSS3: lightcyan",
  0xfafad2: "CSS3: lightgoldenrodyellow",
  0xd3d3d3: "CSS3: lightgray",
  0x90ee90: "CSS3: lightgreen",
  0xffb6c1: "CSS3: lightpink",
  0xffa07a: "CSS3: lightsalmon",
  0x20b2aa: "CSS3: lightseagreen",
  0x87cefa: "CSS3: lightskyblue",
  0x778899: "CSS3: lightslategray",
  0xb0c4de: "CSS3: lightsteelblue",
  0xffffe0: "CSS3: lightyellow",
  0x32cd32: "CSS3: limegreen",
  0xfaf0e6: "CSS3: linen",
  0x66cdaa: "CSS3: mediumaquamarine",
  0x0000cd: "CSS3: mediumblue",
  0xba55d3: "CSS3: mediumorchid",
  0x9370db: "CSS3: mediumpurple",
  0x3cb371: "CSS3: mediumseagreen",
  0x7b68ee: "CSS3: mediumslateblue",
  0x00fa9a: "CSS3: mediumspringgreen",
  0x48d1cc: "CSS3: mediumturquoise",
  0xc71585: "CSS3: mediumvioletred",
  0x191970: "CSS3: midnightblue",
  0xf5fffa: "CSS3: mintcream",
  0xffe4e1: "CSS3: mistyrose",
  0xffe4b5: "CSS3: moccasin",
  0xffdead: "CSS3: navajowhite",
  0xfdf5e6: "CSS3: oldlace",
  0x6b8e23: "CSS3: olivedrab",
  0xff4500: "CSS3: orangered",
  0xda70d6: "CSS3: orchid",
  0xeee8aa: "CSS3: palegoldenrod",
  0x98fb98: "CSS3: palegreen",
  0xafeeee: "CSS3: paleturquoise",
  0xdb7093: "CSS3: palevioletred",
  0xffefd5: "CSS3: papayawhip",
  0xffdab9: "CSS3: peachpuff",
  0xcd853f: "CSS3: peru",
  0xffc0cb: "CSS3: pink",
  0xdda0dd: "CSS3: plum",
  0xb0e0e6: "CSS3: powderblue",
  0xbc8f8f: "CSS3: rosybrown",
  0x4169e1: "CSS3: royalblue",
  0x8b4513: "CSS3: saddlebrown",
  0xfa8072: "CSS3: salmon",
  0xf4a460: "CSS3: sandybrown",
  0x2e8b57: "CSS3: seagreen",
  0xfff5ee: "CSS3: seashell",
  0xa0522d: "CSS3: sienna",
  0x87ceeb: "CSS3: skyblue",
  0x6a5acd: "CSS3: slateblue",
  0x708090: "CSS3: slategray",
  0xfffafa: "CSS3: snow",
  0x00ff7f: "CSS3: springgreen",
  0x4682b4: "CSS3: steelblue",
  0xd2b48c: "CSS3: tan",
  0xd8bfd8: "CSS3: thistle",
  0xff6347: "CSS3: tomato",
  0x40e0d0: "CSS3: turquoise",
  0xee82ee: "CSS3: violet",
  0xf5deb3: "CSS3: wheat",
  0xf5f5f5: "CSS3: whitesmoke",
  0x9acd32: "CSS3: yellowgreen",
  0x663399: "CSS4: rebeccapurple",
  0xffebee: "Material Design: Red 50",
  0xffcdd2: "Material Design: Red 100",
  0xef9a9a: "Material Design: Red 200",
  0xe57373: "Material Design: Red 300",
  0xef5350: "Material Design: Red 400",
  0xf44336: "Material Design: Red 500",
  0xe53935: "Material Design: Red 600",
  0xd32f2f: "Material Design: Red 700",
  0xc62828: "Material Design: Red 800",
  0xb71c1c: "Material Design: Red 900",
  0xff8a80: "Material Design: Red A100",
  0xff5252: "Material Design: Red A200",
  0xff1744: "Material Design: Red A400",
  0xd50000: "Material Design: Red A700",
  0xfce4ec: "Material Design: Pink 50",
  0xf8bbd0: "Material Design: Pink 100",
  0xf48fb1: "Material Design: Pink 200",
  0xf06292: "Material Design: Pink 300",
  0xec407a: "Material Design: Pink 400",
  0xe91e63: "Material Design: Pink 500",
  0xd81b60: "Material Design: Pink 600",
  0xc2185b: "Material Design: Pink 700",
  0xad1457: "Material Design: Pink 800",
  0x880e4f: "Material Design: Pink 900",
  0xff80ab: "Material Design: Pink A100",
  0xff4081: "Material Design: Pink A200",
  0xf50057: "Material Design: Pink A400",
  0xc51162: "Material Design: Pink A700",
  0xf3e5f5: "Material Design: Purple 50",
  0xe1bee7: "Material Design: Purple 100",
  0xce93d8: "Material Design: Purple 200",
  0xba68c8: "Material Design: Purple 300",
  0xab47bc: "Material Design: Purple 400",
  0x9c27b0: "Material Design: Purple 500",
  0x8e24aa: "Material Design: Purple 600",
  0x7b1fa2: "Material Design: Purple 700",
  0x6a1b9a: "Material Design: Purple 800",
  0x4a148c: "Material Design: Purple 900",
  0xea80fc: "Material Design: Purple A100",
  0xe040fb: "Material Design: Purple A200",
  0xd500f9: "Material Design: Purple A400",
  0xaa00ff: "Material Design: Purple A700",
  0xede7f6: "Material Design: Deep Purple 50",
  0xd1c4e9: "Material Design: Deep Purple 100",
  0xb39ddb: "Material Design: Deep Purple 200",
  0x9575cd: "Material Design: Deep Purple 300",
  0x7e57c2: "Material Design: Deep Purple 400",
  0x673ab7: "Material Design: Deep Purple 500",
  0x5e35b1: "Material Design: Deep Purple 600",
  0x512da8: "Material Design: Deep Purple 700",
  0x4527a0: "Material Design: Deep Purple 800",
  0x311b92: "Material Design: Deep Purple 900",
  0xb388ff: "Material Design: Deep Purple A100",
  0x7c4dff: "Material Design: Deep Purple A200",
  0x651fff: "Material Design: Deep Purple A400",
  0x6200ea: "Material Design: Deep Purple A700",
  0xe8eaf6: "Material Design: Indigo 50",
  0xc5cae9: "Material Design: Indigo 100",
  0x9fa8da: "Material Design: Indigo 200",
  0x7986cb: "Material Design: Indigo 300",
  0x5c6bc0: "Material Design: Indigo 400",
  0x3f51b5: "Material Design: Indigo 500",
  0x3949ab: "Material Design: Indigo 600",
  0x303f9f: "Material Design: Indigo 700",
  0x283593: "Material Design: Indigo 800",
  0x1a237e: "Material Design: Indigo 900",
  0x8c9eff: "Material Design: Indigo A100",
  0x536dfe: "Material Design: Indigo A200",
  0x3d5afe: "Material Design: Indigo A400",
  0x304ffe: "Material Design: Indigo A700",
  0xe3f2fd: "Material Design: Blue 50",
  0xbbdefb: "Material Design: Blue 100",
  0x90caf9: "Material Design: Blue 200",
  0x64b5f6: "Material Design: Blue 300",
  0x42a5f5: "Material Design: Blue 400",
  0x2196f3: "Material Design: Blue 500",
  0x1e88e5: "Material Design: Blue 600",
  0x1976d2: "Material Design: Blue 700",
  0x1565c0: "Material Design: Blue 800",
  0x0d47a1: "Material Design: Blue 900",
  0x82b1ff: "Material Design: Blue A100",
  0x448aff: "Material Design: Blue A200",
  0x2979ff: "Material Design: Blue A400",
  0x2962ff: "Material Design: Blue A700",
  0xe1f5fe: "Material Design: Light Blue 50",
  0xb3e5fc: "Material Design: Light Blue 100",
  0x81d4fa: "Material Design: Light Blue 200",
  0x4fc3f7: "Material Design: Light Blue 300",
  0x29b6f6: "Material Design: Light Blue 400",
  0x03a9f4: "Material Design: Light Blue 500",
  0x039be5: "Material Design: Light Blue 600",
  0x0288d1: "Material Design: Light Blue 700",
  0x0277bd: "Material Design: Light Blue 800",
  0x01579b: "Material Design: Light Blue 900",
  0x80d8ff: "Material Design: Light Blue A100",
  0x40c4ff: "Material Design: Light Blue A200",
  0x00b0ff: "Material Design: Light Blue A400",
  0x0091ea: "Material Design: Light Blue A700",
  0xe0f7fa: "Material Design: Cyan 50",
  0xb2ebf2: "Material Design: Cyan 100",
  0x80deea: "Material Design: Cyan 200",
  0x4dd0e1: "Material Design: Cyan 300",
  0x26c6da: "Material Design: Cyan 400",
  0x00bcd4: "Material Design: Cyan 500",
  0x00acc1: "Material Design: Cyan 600",
  0x0097a7: "Material Design: Cyan 700",
  0x00838f: "Material Design: Cyan 800",
  0x006064: "Material Design: Cyan 900",
  0x84ffff: "Material Design: Cyan A100",
  0x18ffff: "Material Design: Cyan A200",
  0x00e5ff: "Material Design: Cyan A400",
  0x00b8d4: "Material Design: Cyan A700",
  0xe0f2f1: "Material Design: Teal 50",
  0xb2dfdb: "Material Design: Teal 100",
  0x80cbc4: "Material Design: Teal 200",
  0x4db6ac: "Material Design: Teal 300",
  0x26a69a: "Material Design: Teal 400",
  0x009688: "Material Design: Teal 500",
  0x00897b: "Material Design: Teal 600",
  0x00796b: "Material Design: Teal 700",
  0x00695c: "Material Design: Teal 800",
  0x004d40: "Material Design: Teal 900",
  0xa7ffeb: "Material Design: Teal A100",
  0x64ffda: "Material Design: Teal A200",
  0x1de9b6: "Material Design: Teal A400",
  0x00bfa5: "Material Design: Teal A700",
  0xe8f5e9: "Material Design: Green 50",
  0xc8e6c9: "Material Design: Green 100",
  0xa5d6a7: "Material Design: Green 200",
  0x81c784: "Material Design: Green 300",
  0x66bb6a: "Material Design: Green 400",
  0x4caf50: "Material Design: Green 500",
  0x43a047: "Material Design: Green 600",
  0x388e3c: "Material Design: Green 700",
  0x2e7d32: "Material Design: Green 800",
  0x1b5e20: "Material Design: Green 900",
  0xb9f6ca: "Material Design: Green A100",
  0x69f0ae: "Material Design: Green A200",
  0x00e676: "Material Design: Green A400",
  0x00c853: "Material Design: Green A700",
  0xf1f8e9: "Material Design: Light Green 50",
  0xdcedc8: "Material Design: Light Green 100",
  0xc5e1a5: "Material Design: Light Green 200",
  0xaed581: "Material Design: Light Green 300",
  0x9ccc65: "Material Design: Light Green 400",
  0x8bc34a: "Material Design: Light Green 500",
  0x7cb342: "Material Design: Light Green 600",
  0x689f38: "Material Design: Light Green 700",
  0x558b2f: "Material Design: Light Green 800",
  0x33691e: "Material Design: Light Green 900",
  0xccff90: "Material Design: Light Green A100",
  0xb2ff59: "Material Design: Light Green A200",
  0x76ff03: "Material Design: Light Green A400",
  0x64dd17: "Material Design: Light Green A700",
  0xf9fbe7: "Material Design: Lime 50",
  0xf0f4c3: "Material Design: Lime 100",
  0xe6ee9c: "Material Design: Lime 200",
  0xdce775: "Material Design: Lime 300",
  0xd4e157: "Material Design: Lime 400",
  0xcddc39: "Material Design: Lime 500",
  0xc0ca33: "Material Design: Lime 600",
  0xafb42b: "Material Design: Lime 700",
  0x9e9d24: "Material Design: Lime 800",
  0x827717: "Material Design: Lime 900",
  0xf4ff81: "Material Design: Lime A100",
  0xeeff41: "Material Design: Lime A200",
  0xc6ff00: "Material Design: Lime A400",
  0xaeea00: "Material Design: Lime A700",
  0xfffde7: "Material Design: Yellow 50",
  0xfff9c4: "Material Design: Yellow 100",
  0xfff59d: "Material Design: Yellow 200",
  0xfff176: "Material Design: Yellow 300",
  0xffee58: "Material Design: Yellow 400",
  0xffeb3b: "Material Design: Yellow 500",
  0xfdd835: "Material Design: Yellow 600",
  0xfbc02d: "Material Design: Yellow 700",
  0xf9a825: "Material Design: Yellow 800",
  0xf57f17: "Material Design: Yellow 900",
  0xffff8d: "Material Design: Yellow A100",
  0xffea00: "Material Design: Yellow A400",
  0xffd600: "Material Design: Yellow A700",
  0xfff8e1: "Material Design: Amber 50",
  0xffecb3: "Material Design: Amber 100",
  0xffe082: "Material Design: Amber 200",
  0xffd54f: "Material Design: Amber 300",
  0xffca28: "Material Design: Amber 400",
  0xffc107: "Material Design: Amber 500",
  0xffb300: "Material Design: Amber 600",
  0xffa000: "Material Design: Amber 700",
  0xff8f00: "Material Design: Amber 800",
  0xff6f00: "Material Design: Amber 900",
  0xffe57f: "Material Design: Amber A100",
  0xffd740: "Material Design: Amber A200",
  0xffc400: "Material Design: Amber A400",
  0xffab00: "Material Design: Amber A700",
  0xfff3e0: "Material Design: Orange 50",
  0xffe0b2: "Material Design: Orange 100",
  0xffcc80: "Material Design: Orange 200",
  0xffb74d: "Material Design: Orange 300",
  0xffa726: "Material Design: Orange 400",
  0xff9800: "Material Design: Orange 500",
  0xfb8c00: "Material Design: Orange 600",
  0xf57c00: "Material Design: Orange 700",
  0xef6c00: "Material Design: Orange 800",
  0xe65100: "Material Design: Orange 900",
  0xffd180: "Material Design: Orange A100",
  0xffab40: "Material Design: Orange A200",
  0xff9100: "Material Design: Orange A400",
  0xff6d00: "Material Design: Orange A700",
  0xfbe9e7: "Material Design: Deep Orange 50",
  0xffccbc: "Material Design: Deep Orange 100",
  0xffab91: "Material Design: Deep Orange 200",
  0xff8a65: "Material Design: Deep Orange 300",
  0xff7043: "Material Design: Deep Orange 400",
  0xff5722: "Material Design: Deep Orange 500",
  0xf4511e: "Material Design: Deep Orange 600",
  0xe64a19: "Material Design: Deep Orange 700",
  0xd84315: "Material Design: Deep Orange 800",
  0xbf360c: "Material Design: Deep Orange 900",
  0xff9e80: "Material Design: Deep Orange A100",
  0xff6e40: "Material Design: Deep Orange A200",
  0xff3d00: "Material Design: Deep Orange A400",
  0xdd2c00: "Material Design: Deep Orange A700",
  0xefebe9: "Material Design: Brown 50",
  0xd7ccc8: "Material Design: Brown 100",
  0xbcaaa4: "Material Design: Brown 200",
  0xa1887f: "Material Design: Brown 300",
  0x8d6e63: "Material Design: Brown 400",
  0x795548: "Material Design: Brown 500",
  0x6d4c41: "Material Design: Brown 600",
  0x5d4037: "Material Design: Brown 700",
  0x4e342e: "Material Design: Brown 800",
  0x3e2723: "Material Design: Brown 900",
  0xfafafa: "Material Design: Grey 50",
  0xeeeeee: "Material Design: Grey 200",
  0xe0e0e0: "Material Design: Grey 300",
  0xbdbdbd: "Material Design: Grey 400",
  0x9e9e9e: "Material Design: Grey 500",
  0x757575: "Material Design: Grey 600",
  0x616161: "Material Design: Grey 700",
  0x424242: "Material Design: Grey 800",
  0x212121: "Material Design: Grey 900",
  0xeceff1: "Material Design: Blue Grey 50",
  0xcfd8dc: "Material Design: Blue Grey 100",
  0xb0bec5: "Material Design: Blue Grey 200",
  0x90a4ae: "Material Design: Blue Grey 300",
  0x78909c: "Material Design: Blue Grey 400",
  0x607d8b: "Material Design: Blue Grey 500",
  0x546e7a: "Material Design: Blue Grey 600",
  0x455a64: "Material Design: Blue Grey 700",
  0x37474f: "Material Design: Blue Grey 800",
  0x263238: "Material Design: Blue Grey 900",
}

VALUES = {
  "black": 0x000000,
  "silver": 0xc0c0c0,
  "gray": 0x808080,
  "white": 0xffffff,
  "maroon": 0x800000,
  "red": 0xff0000,
  "purple": 0x800080,
  "fuchsia": 0xff00ff,
  "green": 0x008000,
  "lime": 0x00ff00,
  "olive": 0x808000,
  "yellow": 0xffff00,
  "navy": 0x000080,
  "blue": 0x0000ff,
  "teal": 0x008080,
  "aqua": 0x00ffff,
  "orange": 0xffa500,
  "aliceblue": 0xf0f8ff,
  "antiquewhite": 0xfaebd7,
  "aquamarine": 0x7fffd4,
  "azure": 0xf0ffff,
  "beige": 0xf5f5dc,
  "bisque": 0xffe4c4,
  "blanchedalmond": 0xffebcd,
  "blueviolet": 0x8a2be2,
  "brown": 0xa52a2a,
  "burlywood": 0xdeb887,
  "cadetblue": 0x5f9ea0,
  "chartreuse": 0x7fff00,
  "chocolate": 0xd2691e,
  "coral": 0xff7f50,
  "cornflowerblue": 0x6495ed,
  "cornsilk": 0xfff8dc,
  "crimson": 0xdc143c,
  "cyan": 0x00ffff,
  "darkblue": 0x00008b,
  "darkcyan": 0x008b8b,
  "darkgoldenrod": 0xb8860b,
  "darkgray": 0xa9a9a9,
  "darkgreen": 0x006400,
  "darkgrey": 0xa9a9a9,
  "darkkhaki": 0xbdb76b,
  "darkmagenta": 0x8b008b,
  "darkolivegreen": 0x556b2f,
  "darkorange": 0xff8c00,
  "darkorchid": 0x9932cc,
  "darkred": 0x8b0000,
  "darksalmon": 0xe9967a,
  "darkseagreen": 0x8fbc8f,
  "darkslateblue": 0x483d8b,
  "darkslategray": 0x2f4f4f,
  "darkslategrey": 0x2f4f4f,
  "darkturquoise": 0x00ced1,
  "darkviolet": 0x9400d3,
  "deeppink": 0xff1493,
  "deepskyblue": 0x00bfff,
  "dimgray": 0x696969,
  "dimgrey": 0x696969,
  "dodgerblue": 0x1e90ff,
  "firebrick": 0xb22222,
  "floralwhite": 0xfffaf0,
  "forestgreen": 0x228b22,
  "gainsboro": 0xdcdcdc,
  "ghostwhite": 0xf8f8ff,
  "gold": 0xffd700,
  "goldenrod": 0xdaa520,
  "greenyellow": 0xadff2f,
  "grey": 0x808080,
  "honeydew": 0xf0fff0,
  "hotpink": 0xff69b4,
  "indianred": 0xcd5c5c,
  "indigo": 0x4b0082,
  "ivory": 0xfffff0,
  "khaki": 0xf0e68c,
  "lavender": 0xe6e6fa,
  "lavenderblush": 0xfff0f5,
  "lawngreen": 0x7cfc00,
  "lemonchiffon": 0xfffacd,
  "lightblue": 0xadd8e6,
  "lightcoral": 0xf08080,
  "lightcyan": 0xe0ffff,
  "lightgoldenrodyellow": 0xfafad2,
  "lightgray": 0xd3d3d3,
  "lightgreen": 0x90ee90,
  "lightgrey": 0xd3d3d3,
  "lightpink": 0xffb6c1,
  "lightsalmon": 0xffa07a,
  "lightseagreen": 0x20b2aa,
  "lightskyblue": 0x87cefa,
  "lightslategray": 0x778899,
  "lightslategrey": 0x778899,
  "lightsteelblue": 0xb0c4de,
  "lightyellow": 0xffffe0,
  "limegreen": 0x32cd32,
  "linen": 0xfaf0e6,
  "magenta": 0xff00ff,
  "mediumaquamarine": 0x66cdaa,
  "mediumblue": 0x0000cd,
  "mediumorchid": 0xba55d3,
  "mediumpurple": 0x9370db,
  "mediumseagreen": 0x3cb371,
  "mediumslateblue": 0x7b68ee,
  "mediumspringgreen": 0x00fa9a,
  "mediumturquoise": 0x48d1cc,
  "mediumvioletred": 0xc71585,
  "midnightblue": 0x191970,
  "mintcream": 0xf5fffa,
  "mistyrose": 0xffe4e1,
  "moccasin": 0xffe4b5,
  "navajowhite": 0xffdead,
  "oldlace": 0xfdf5e6,
  "olivedrab": 0x6b8e23,
  "orangered": 0xff4500,
  "orchid": 0xda70d6,
  "palegoldenrod": 0xeee8aa,
  "palegreen": 0x98fb98,
  "paleturquoise": 0xafeeee,
  "palevioletred": 0xdb7093,
  "papayawhip": 0xffefd5,
  "peachpuff": 0xffdab9,
  "peru": 0xcd853f,
  "pink": 0xffc0cb,
  "plum": 0xdda0dd,
  "powderblue": 0xb0e0e6,
  "rosybrown": 0xbc8f8f,
  "royalblue": 0x4169e1,
  "saddlebrown": 0x8b4513,
  "salmon": 0xfa8072,
  "sandybrown": 0xf4a460,
  "seagreen": 0x2e8b57,
  "seashell": 0xfff5ee,
  "sienna": 0xa0522d,
  "skyblue": 0x87ceeb,
  "slateblue": 0x6a5acd,
  "slategray": 0x708090,
  "slategrey": 0x708090,
  "snow": 0xfffafa,
  "springgreen": 0x00ff7f,
  "steelblue": 0x4682b4,
  "tan": 0xd2b48c,
  "thistle": 0xd8bfd8,
  "tomato": 0xff6347,
  "turquoise": 0x40e0d0,
  "violet": 0xee82ee,
  "wheat": 0xf5deb3,
  "whitesmoke": 0xf5f5f5,
  "yellowgreen": 0x9acd32,
  "rebeccapurple": 0x663399,
  "red50": 0xffebee,
  "red100": 0xffcdd2,
  "red200": 0xef9a9a,
  "red300": 0xe57373,
  "red400": 0xef5350,
  "red500": 0xf44336,
  "red600": 0xe53935,
  "red700": 0xd32f2f,
  "red800": 0xc62828,
  "red900": 0xb71c1c,
  "redA100": 0xff8a80,
  "redA200": 0xff5252,
  "redA400": 0xff1744,
  "redA700": 0xd50000,
  "pink50": 0xfce4ec,
  "pink100": 0xf8bbd0,
  "pink200": 0xf48fb1,
  "pink300": 0xf06292,
  "pink400": 0xec407a,
  "pink500": 0xe91e63,
  "pink600": 0xd81b60,
  "pink700": 0xc2185b,
  "pink800": 0xad1457,
  "pink900": 0x880e4f,
  "pinkA100": 0xff80ab,
  "pinkA200": 0xff4081,
  "pinkA400": 0xf50057,
  "pinkA700": 0xc51162,
  "purple50": 0xf3e5f5,
  "purple100": 0xe1bee7,
  "purple200": 0xce93d8,
  "purple300": 0xba68c8,
  "purple400": 0xab47bc,
  "purple500": 0x9c27b0,
  "purple600": 0x8e24aa,
  "purple700": 0x7b1fa2,
  "purple800": 0x6a1b9a,
  "purple900": 0x4a148c,
  "purpleA100": 0xea80fc,
  "purpleA200": 0xe040fb,
  "purpleA400": 0xd500f9,
  "purpleA700": 0xaa00ff,
  "deeppurple50": 0xede7f6,
  "deeppurple100": 0xd1c4e9,
  "deeppurple200": 0xb39ddb,
  "deeppurple300": 0x9575cd,
  "deeppurple400": 0x7e57c2,
  "deeppurple500": 0x673ab7,
  "deeppurple600": 0x5e35b1,
  "deeppurple700": 0x512da8,
  "deeppurple800": 0x4527a0,
  "deeppurple900": 0x311b92,
  "deeppurpleA100": 0xb388ff,
  "deeppurpleA200": 0x7c4dff,
  "deeppurpleA400": 0x651fff,
  "deeppurpleA700": 0x6200ea,
  "indigo50": 0xe8eaf6,
  "indigo100": 0xc5cae9,
  "indigo200": 0x9fa8da,
  "indigo300": 0x7986cb,
  "indigo400": 0x5c6bc0,
  "indigo500": 0x3f51b5,
  "indigo600": 0x3949ab,
  "indigo700": 0x303f9f,
  "indigo800": 0x283593,
  "indigo900": 0x1a237e,
  "indigoA100": 0x8c9eff,
  "indigoA200": 0x536dfe,
  "indigoA400": 0x3d5afe,
  "indigoA700": 0x304ffe,
  "blue50": 0xe3f2fd,
  "blue100": 0xbbdefb,
  "blue200": 0x90caf9,
  "blue300": 0x64b5f6,
  "blue400": 0x42a5f5,
  "blue500": 0x2196f3,
  "blue600": 0x1e88e5,
  "blue700": 0x1976d2,
  "blue800": 0x1565c0,
  "blue900": 0x0d47a1,
  "blueA100": 0x82b1ff,
  "blueA200": 0x448aff,
  "blueA400": 0x2979ff,
  "blueA700": 0x2962ff,
  "lightblue50": 0xe1f5fe,
  "lightblue100": 0xb3e5fc,
  "lightblue200": 0x81d4fa,
  "lightblue300": 0x4fc3f7,
  "lightblue400": 0x29b6f6,
  "lightblue500": 0x03a9f4,
  "lightblue600": 0x039be5,
  "lightblue700": 0x0288d1,
  "lightblue800": 0x0277bd,
  "lightblue900": 0x01579b,
  "lightblueA100": 0x80d8ff,
  "lightblueA200": 0x40c4ff,
  "lightblueA400": 0x00b0ff,
  "lightblueA700": 0x0091ea,
  "cyan50": 0xe0f7fa,
  "cyan100": 0xb2ebf2,
  "cyan200": 0x80deea,
  "cyan300": 0x4dd0e1,
  "cyan400": 0x26c6da,
  "cyan500": 0x00bcd4,
  "cyan600": 0x00acc1,
  "cyan700": 0x0097a7,
  "cyan800": 0x00838f,
  "cyan900": 0x006064,
  "cyanA100": 0x84ffff,
  "cyanA200": 0x18ffff,
  "cyanA400": 0x00e5ff,
  "cyanA700": 0x00b8d4,
  "teal50": 0xe0f2f1,
  "teal100": 0xb2dfdb,
  "teal200": 0x80cbc4,
  "teal300": 0x4db6ac,
  "teal400": 0x26a69a,
  "teal500": 0x009688,
  "teal600": 0x00897b,
  "teal700": 0x00796b,
  "teal800": 0x00695c,
  "teal900": 0x004d40,
  "tealA100": 0xa7ffeb,
  "tealA200": 0x64ffda,
  "tealA400": 0x1de9b6,
  "tealA700": 0x00bfa5,
  "green50": 0xe8f5e9,
  "green100": 0xc8e6c9,
  "green200": 0xa5d6a7,
  "green300": 0x81c784,
  "green400": 0x66bb6a,
  "green500": 0x4caf50,
  "green600": 0x43a047,
  "green700": 0x388e3c,
  "green800": 0x2e7d32,
  "green900": 0x1b5e20,
  "greenA100": 0xb9f6ca,
  "greenA200": 0x69f0ae,
  "greenA400": 0x00e676,
  "greenA700": 0x00c853,
  "lightgreen50": 0xf1f8e9,
  "lightgreen100": 0xdcedc8,
  "lightgreen200": 0xc5e1a5,
  "lightgreen300": 0xaed581,
  "lightgreen400": 0x9ccc65,
  "lightgreen500": 0x8bc34a,
  "lightgreen600": 0x7cb342,
  "lightgreen700": 0x689f38,
  "lightgreen800": 0x558b2f,
  "lightgreen900": 0x33691e,
  "lightgreenA100": 0xccff90,
  "lightgreenA200": 0xb2ff59,
  "lightgreenA400": 0x76ff03,
  "lightgreenA700": 0x64dd17,
  "lime50": 0xf9fbe7,
  "lime100": 0xf0f4c3,
  "lime200": 0xe6ee9c,
  "lime300": 0xdce775,
  "lime400": 0xd4e157,
  "lime500": 0xcddc39,
  "lime600": 0xc0ca33,
  "lime700": 0xafb42b,
  "lime800": 0x9e9d24,
  "lime900": 0x827717,
  "limeA100": 0xf4ff81,
  "limeA200": 0xeeff41,
  "limeA400": 0xc6ff00,
  "limeA700": 0xaeea00,
  "yellow50": 0xfffde7,
  "yellow100": 0xfff9c4,
  "yellow200": 0xfff59d,
  "yellow300": 0xfff176,
  "yellow400": 0xffee58,
  "yellow500": 0xffeb3b,
  "yellow600": 0xfdd835,
  "yellow700": 0xfbc02d,
  "yellow800": 0xf9a825,
  "yellow900": 0xf57f17,
  "yellowA100": 0xffff8d,
  "yellowA200": 0xffff00,
  "yellowA400": 0xffea00,
  "yellowA700": 0xffd600,
  "amber50": 0xfff8e1,
  "amber100": 0xffecb3,
  "amber200": 0xffe082,
  "amber300": 0xffd54f,
  "amber400": 0xffca28,
  "amber500": 0xffc107,
  "amber600": 0xffb300,
  "amber700": 0xffa000,
  "amber800": 0xff8f00,
  "amber900": 0xff6f00,
  "amberA100": 0xffe57f,
  "amberA200": 0xffd740,
  "amberA400": 0xffc400,
  "amberA700": 0xffab00,
  "orange50": 0xfff3e0,
  "orange100": 0xffe0b2,
  "orange200": 0xffcc80,
  "orange300": 0xffb74d,
  "orange400": 0xffa726,
  "orange500": 0xff9800,
  "orange600": 0xfb8c00,
  "orange700": 0xf57c00,
  "orange800": 0xef6c00,
  "orange900": 0xe65100,
  "orangeA100": 0xffd180,
  "orangeA200": 0xffab40,
  "orangeA400": 0xff9100,
  "orangeA700": 0xff6d00,
  "deeporange50": 0xfbe9e7,
  "deeporange100": 0xffccbc,
  "deeporange200": 0xffab91,
  "deeporange300": 0xff8a65,
  "deeporange400": 0xff7043,
  "deeporange500": 0xff5722,
  "deeporange600": 0xf4511e,
  "deeporange700": 0xe64a19,
  "deeporange800": 0xd84315,
  "deeporange900": 0xbf360c,
  "deeporangeA100": 0xff9e80,
  "deeporangeA200": 0xff6e40,
  "deeporangeA400": 0xff3d00,
  "deeporangeA700": 0xdd2c00,
  "brown50": 0xefebe9,
  "brown100": 0xd7ccc8,
  "brown200": 0xbcaaa4,
  "brown300": 0xa1887f,
  "brown400": 0x8d6e63,
  "brown500": 0x795548,
  "brown600": 0x6d4c41,
  "brown700": 0x5d4037,
  "brown800": 0x4e342e,
  "brown900": 0x3e2723,
  "gray50": 0xfafafa,
  "gray100": 0xf5f5f5,
  "gray200": 0xeeeeee,
  "gray300": 0xe0e0e0,
  "gray400": 0xbdbdbd,
  "gray500": 0x9e9e9e,
  "gray600": 0x757575,
  "gray700": 0x616161,
  "gray800": 0x424242,
  "gray900": 0x212121,
  "grey50": 0xfafafa,
  "grey100": 0xf5f5f5,
  "grey200": 0xeeeeee,
  "grey300": 0xe0e0e0,
  "grey400": 0xbdbdbd,
  "grey500": 0x9e9e9e,
  "grey600": 0x757575,
  "grey700": 0x616161,
  "grey800": 0x424242,
  "grey900": 0x212121,
  "bluegray50": 0xeceff1,
  "bluegray100": 0xcfd8dc,
  "bluegray200": 0xb0bec5,
  "bluegray300": 0x90a4ae,
  "bluegray400": 0x78909c,
  "bluegray500": 0x607d8b,
  "bluegray600": 0x546e7a,
  "bluegray700": 0x455a64,
  "bluegray800": 0x37474f,
  "bluegray900": 0x263238,
  "bluegrey50": 0xeceff1,
  "bluegrey100": 0xcfd8dc,
  "bluegrey200": 0xb0bec5,
  "bluegrey300": 0x90a4ae,
  "bluegrey400": 0x78909c,
  "bluegrey500": 0x607d8b,
  "bluegrey600": 0x546e7a,
  "bluegrey700": 0x455a64,
  "bluegrey800": 0x37474f,
  "bluegrey900": 0x263238,
}

LONG_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
SHORT_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3})$")
RGB_RE = re.compile(
  r"^rgb\s*\(\s*"
  r"(2(?:5[0-5]|[0-4]\d)|1\d\d|[1-9]?\d)\s*(?:,|\s)\s*"
  r"(2(?:5[0-5]|[0-4]\d)|1\d\d|[1-9]?\d)\s*(?:,|\s)\s*"
  r"(2(?:5[0-5]|[0-4]\d)|1\d\d|[1-9]?\d)\s*\)$")
HSL_RE = re.compile(
  r"^hsl\s*\(\s*"
  r"(\d+(?:\.\d+)?)(?:deg)?\s*(?:,|\s)\s*"
  r"(100(?:\.0+)?|[1-9]\d(?:\.\d+)?)%\s*(?:,|\s)\s*"
  r"(100(?:\.0+)?|[1-9]\d(?:\.\d+)?)%\s*\)$")

RGB = tuple[int, int, int]


def parse(src: str) -> Optional[int]:
  if src in VALUES:
    return VALUES[src]
  if match := LONG_HEX_RE.match(src):
    return int(match[1], 16)
  if match := SHORT_HEX_RE.match(src):
    v = int(match[1], 16)
    r = v >> 8
    g = (v >> 4) & 0xf
    b = v & 0xf
    return r << 20 | r << 16 | g << 12 | g << 8 | b << 4 | b
  if match := RGB_RE.match(src):
    r = int(match[1])
    g = int(match[2])
    b = int(match[3])
    return r << 16 | g << 8 | b
  if match := HSL_RE.match(src):
    h = float(match[1]) % 360 / 360
    s = float(match[2]) / 100
    l = float(match[3]) / 100
    return hsl2rgb(h, s, l)
  return None


def _hue2rgb(p: float, q: float, t: float) -> float:
  if t < 0:
    t += 1
  if t > 1:
    t -= 1
  if t < 1 / 6:
    return p + (q - p) * 6 * t
  if t < 1 / 2:
    return q
  if t < 2 / 3:
    return p + (q - p) * (2 / 3 - t) * 6
  return p


def hsl2rgb(h: float, s: float, l: float) -> int:
  if s == 0:
    r = g = b = l
  else:
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = _hue2rgb(p, q, h + 1 / 3)
    g = _hue2rgb(p, q, h)
    b = _hue2rgb(p, q, h - 1 / 3)
  return round(r * 255) << 16 | round(g * 255) << 8 | round(b * 255)


def rgb2hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
  r_ = r / 255
  g_ = g / 255
  b_ = b / 255
  cmin = min(r_, g_, b_)
  cmax = max(r_, g_, b_)
  delta = cmax - cmin

  if delta == 0:
    h = 0.0
  elif cmax == r_:
    h = ((g_ - b_) / delta) % 6
  elif cmax == g_:
    h = (b_ - r_) / delta + 2
  else:
    h = (r_ - g_) / delta + 4
  h = h * 60
  if h < 0:
    h += 360
  l = (cmax + cmin) / 2
  s = 0.0 if delta == 0 else delta / (1 - abs(2 * l - 1))

  return (h, s, l)


def split_rgb(v: int) -> RGB:
  return (v >> 16 & 0xff, v >> 8 & 0xff, v & 0xff)


def luminance(r: int, g: int, b: int) -> float:
  return 0.3 * (r / 255) + 0.59 * (g / 255) + 0.11 * (b / 255)


def blend(fg: RGB, bg: RGB, r: float, gamma: float = 2) -> RGB:
  igamma = 1 / gamma
  r2 = 1 - r
  return (
    int(((fg[0] / 255) ** gamma * r + (bg[0] / 255) ** gamma * r2) ** igamma * 255),
    int(((fg[1] / 255) ** gamma * r + (bg[1] / 255) ** gamma * r2) ** igamma * 255),
    int(((fg[2] / 255) ** gamma * r + (bg[2] / 255) ** gamma * r2) ** igamma * 255),
  )
