import re
import sys
from pathlib import Path

from idhagnbot.plugins.idhagnfetch.gpu import amd, nvidia
from idhagnbot.plugins.idhagnfetch.gpu.common import Info
from idhagnbot.plugins.idhagnfetch.gpu.common import read as read_unknown

VENDORS = {
  # 0x8086: intel,
  0x10DE: nvidia,
  0x1002: amd,
}


def get_gpu_info() -> list[Info]:
  if sys.platform != "linux":
    return []
  gpus = [i for i in Path("/sys/class/drm").iterdir() if re.match(r"^card\d+$", i.name)]
  result = []
  for i in gpus:
    with (i / "device" / "vendor").open() as f:
      vendor = int(f.read()[2:-1], 16)
    try:
      result.append(VENDORS[vendor].read(i))
    except Exception:
      result.append(read_unknown(i))
  return result
