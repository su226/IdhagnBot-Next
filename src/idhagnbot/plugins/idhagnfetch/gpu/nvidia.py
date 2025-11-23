import subprocess as sp
from pathlib import Path

from idhagnbot.plugins.idhagnfetch.gpu.common import Info


def read(root: Path) -> Info:
  cur_pci = None
  with (root / "device" / "uevent").open() as f:
    for i in f:
      if i.startswith("PCI_SLOT_NAME="):
        cur_pci = i[14:]
        break
  if cur_pci is None:
    raise RuntimeError(f"无法获取PCI槽：{root.name}")
  proc = sp.run(
    [
      "nvidia-smi",
      "--query-gpu=pci.bus_id,name,clocks.sm,temperature.gpu,utilization.gpu,utilization.memory",
      "--format=csv",
    ],
    check=True,
    capture_output=True,
    text=True,
  )
  info = None
  for raw_info in proc.stdout.splitlines()[1:]:
    pci, *info = raw_info.split(", ")
    if pci[4:] == cur_pci:
      break
  if info is None:
    raise RuntimeError(f"无法获取状态：{root.name}")
  name, clk, temp, percent, mem_percent = info
  return Info(
    False,
    name,
    int(percent[:-2]),
    int(mem_percent[:-2]),
    int(clk[:-4]) * 1000000,
    int(temp),
  )
