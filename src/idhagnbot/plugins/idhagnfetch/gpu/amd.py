import re
import subprocess as sp
from pathlib import Path

from idhagnbot.plugins.idhagnfetch.gpu.common import Info

# 核显读不到其中一部分文件
PERCENT_FILE = "gpu_busy_percent"
MEM_PERCENT_FILE = "mem_busy_percent"
MEM_USED_FILE = "mem_info_vram_used"
MEM_TOTAL_FILE = "mem_info_vram_total"
CLK_FILE = "freq1_input"
MEM_CLK_FILE = "freq2_input"
TEMP_FILE = "temp1_input"
JUNCTION_TEMP_FILE = "temp2_input"
MEM_TEMP_FILE = "temp3_input"
VDD_FILE = "in0_input"
UEVENT_FILE = "uevent"


def read(root: Path) -> Info:
  device = root / "device"
  pci = None
  with (device / UEVENT_FILE).open() as f:
    for i in f:
      if i.startswith("PCI_SLOT_NAME="):
        pci = i[14:-1]
        break
  if pci is None:
    raise RuntimeError(f"无法获取PCI槽：{root.name}")
  proc = sp.run(["lspci", "-s", pci], check=True, capture_output=True, text=True)
  model = proc.stdout
  model = re.sub(r".*\[AMD/ATI\] (.*) \(rev [0-9a-f]{2}\)\n", r"\1", model)
  if (left := model.rfind("[")) != -1 and (right := model.rfind("]")) != -1:
    model = model[left + 1 : right]
  hwmon = device / "hwmon"
  hwmon = hwmon / next(hwmon.iterdir()).name
  with (device / PERCENT_FILE).open() as f:
    percent = int(f.read())
  try:
    with (device / MEM_PERCENT_FILE).open() as f:
      mem_percent = int(f.read())
  except FileNotFoundError:
    with (device / MEM_USED_FILE).open() as f:
      mem_used = int(f.read())
    with (device / MEM_TOTAL_FILE).open() as f:
      mem_total = int(f.read())
    mem_percent = int(mem_used / mem_total * 100)
  with (hwmon / CLK_FILE).open() as f:
    clk = int(f.read())
  with (hwmon / TEMP_FILE).open() as f:
    temp = int(f.read()) // 1000
  return Info(False, "AMD/ATI " + model, percent, mem_percent, clk, temp)
