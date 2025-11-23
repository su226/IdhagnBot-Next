import subprocess as sp
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Info:
  unknown: bool
  model: str
  percent: int
  mem_percent: int
  clk: int
  temp: int


def read(root: Path) -> Info:
  pci = None
  with (root / "device" / "uevent").open() as f:
    for i in f:
      if i.startswith("PCI_SLOT_NAME="):
        pci = i[14:-1]
        break
  if pci is None:
    raise RuntimeError(f"无法获取PCI槽：{root.name}")
  proc = sp.run(["lspci", "-s", pci], check=True, capture_output=True, text=True)
  model = proc.stdout
  model = model[model.find(": ") + 2 : -10]
  return Info(True, model, 0, 0, 0, 0)
