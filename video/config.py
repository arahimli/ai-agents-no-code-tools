import os
import torch
from loguru import logger

device = "cpu"
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")
    num_cores = os.cpu_count()
    if os.path.exists("/sys/fs/cgroup/cpu.max"):
        with open("/sys/fs/cgroup/cpu.max", "r") as f:
            line = f.readline()
            if len(line.split()) == 2:
                if line.split()[0] == "max":
                    logger.info(
                        "File /sys/fs/cgroup/cpu.max has max value, using os.cpu_count()"
                    )
                else:
                    cpu_max = int(line.split()[0])
                    cpu_period = int(line.split()[1])
                    num_cores = cpu_max // cpu_period
                    logger.info("Using {} cores", num_cores)
            else:
                logger.warning(
                    "File /sys/fs/cgroup/cpu.max does not have 2 values, using os.cpu_count()"
                )
    else:
        logger.info("File /sys/fs/cgroup/cpu.max not found, using os.cpu_count()")

    num_threads = os.environ.get("NUM_THREADS", num_cores * 1.5)
    torch.set_num_threads(int(num_threads))

map_location = torch.device(device)

torch_load_original = torch.load


def patched_torch_load(*args, **kwargs):
    if "map_location" not in kwargs:
        kwargs["map_location"] = map_location
    return torch_load_original(*args, **kwargs)


torch.load = patched_torch_load
