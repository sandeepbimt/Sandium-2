#!/usr/bin/env python3
"""Measure only the SanB build mount and CPU/RAM, with no source acquisition."""

import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys

BRANCH = "sanb/official158"
REQUIRED_FREE_BYTES = 130 * 2**30
OUTPUT = ".sanb-capacity-audit-artifacts"


def disk_snapshot(root):
    s = os.statvfs(root)
    base = s.f_frsize or s.f_bsize
    if (base < 1 or s.f_blocks < 1 or not 0 <= s.f_bavail <= s.f_bfree <= s.f_blocks
            or not 0 <= s.f_favail <= s.f_ffree <= s.f_files):
        raise ValueError("Inconsistent capacity counters on exact workspace mount")
    return {
        "disk_total_bytes": s.f_blocks*base,
        "disk_used_bytes": (s.f_blocks-s.f_bfree)*base,
        "disk_free_bytes_user_available": s.f_bavail*base,
        "disk_raw_free_bytes_including_reserved": s.f_bfree*base,
        "inodes_total": s.f_files,
        "inodes_available": s.f_favail,
        "inode_reporting_supported": s.f_files > 0,
        "statvfs_fragment_bytes": base,
    }


def optional(file):
    try:
        with file.open("r", encoding="ascii") as stream:
            value = stream.read(4097)
        return value.strip() if len(value) <= 4096 else None
    except (OSError, UnicodeError):
        return None


def cgroup_chain(base, group):
    if not isinstance(group, str):
        return []
    p = PurePosixPath(group)
    if not p.is_absolute() or ".." in p.parts:
        return []
    base = base.resolve()
    start = (base / Path(*p.parts[1:])).resolve()
    if not start.is_relative_to(base):
        return []
    chain = [start, *start.parents]
    return [candidate for candidate in chain if candidate.is_relative_to(base)]


def positive_number(value):
    return int(value) if value and re.fullmatch(r"[0-9]{1,20}", value) else None


def cgroup_snapshot(proc=Path("/proc"), syscg=Path("/sys/fs/cgroup")):
    raw = optional(proc/"self/cgroup") or ""
    groups = {}
    for line in raw.splitlines():
        fields = line.split(":", 2)
        if len(fields) == 3:
            for ctl in fields[1].split(","):
                groups[ctl] = fields[2]
    cpu_limits = []
    memory_limits = []
    if "" in groups:
        chain = cgroup_chain(syscg, groups[""])
        cpu_seen = False
        memory_seen = False
        for item in chain:
            cpu = (optional(item/"cpu.max") or "").split()
            memory = optional(item/"memory.max")
            if len(cpu) == 2:
                quota, period = map(positive_number,cpu)
                if period and (quota or cpu[0]=="max"):
                    cpu_seen = True
                    if quota:
                        cpu_limits.append((quota,period))
            lim = positive_number(memory)
            if lim or memory=="max":
                memory_seen = True
                if lim:
                    memory_limits.append(lim)
        used = positive_number(optional(chain[0]/"memory.current")) if chain else None
        mode = "v2" if cpu_seen or memory_seen else "unavailable"
    elif "cpu" in groups or "memory" in groups:
        cpu_seen = False
        memory_seen = False
        # v1 controllers may have separate mounts or co-mounted cpu,cpuacct.
        for cpu_root in (syscg/"cpu",syscg/"cpu,cpuacct"):
            for item in cgroup_chain(cpu_root, groups.get("cpu")):
                quota = optional(item/"cpu.cfs_quota_us")
                period = positive_number(optional(item/"cpu.cfs_period_us"))
                q = positive_number(quota)
                if period and (q or quota=="-1"):
                    cpu_seen = True
                    if q:
                        cpu_limits.append((q,period))
        mem_chain = cgroup_chain(syscg/"memory",groups.get("memory"))
        for item in mem_chain:
            lim = positive_number(optional(item/"memory.limit_in_bytes"))
            if lim:
                memory_seen = True
                if lim < 2**60:  # v1 sentinel for no restriction.
                    memory_limits.append(lim)
        used = positive_number(optional(mem_chain[0]/"memory.usage_in_bytes")) if mem_chain else None
        mode = "v1" if cpu_seen or memory_seen else "unavailable"
    else:
        cpu_seen=memory_seen=False
        used=None
        mode="unavailable"
    effective_pair = min(cpu_limits,key=lambda p:p[0]/p[1],default=None)
    return {
        "telemetry": mode,
        "cpu_quota_telemetry_available": cpu_seen,
        "cpu_quota_usec": effective_pair[0] if effective_pair else None,
        "cpu_period_usec": effective_pair[1] if effective_pair else None,
        "cpu_quota_cores": (effective_pair[0]/effective_pair[1]) if effective_pair else None,
        "memory_limit_telemetry_available": memory_seen,
        "memory_limit_bytes": min(memory_limits,default=None),
        "memory_usage_bytes": used,
    }


def host_snapshot():
    raw = optional(Path("/proc/meminfo")) or ""
    matches = {name:int(kib)*1024 for name,kib in
               re.findall(r"^(MemTotal|MemAvailable):\s+(\d+)\s+kB$",raw,re.M)}
    affinity = len(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else None
    return {
        "logical_cpus":os.cpu_count(), "affinity_cpus":affinity,
        "memory_total_bytes":matches.get("MemTotal"),
        "memory_available_bytes":matches.get("MemAvailable"),
        "system":platform.system(), "machine":platform.machine(),
        "kernel":platform.release(), "python":platform.python_version(),
    }


def command(args, root):
    # No inherited application, auth, signing or transport environment.
    env={key:os.environ[key] for key in ("PATH","HOME") if key in os.environ}
    env.update(LC_ALL="C",GIT_ALLOW_PROTOCOL="",GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL="/dev/null",GIT_NO_LAZY_FETCH="1")
    r=subprocess.run(args,cwd=root,env=env,stdin=subprocess.DEVNULL,
                     capture_output=True,timeout=15,check=True)
    if not 0 < len(r.stdout)<=8192:
        raise ValueError("Unexpected capacity command output length")
    return r.stdout.decode("utf-8")


def eligibility(free):
    return free >= REQUIRED_FREE_BYTES


def main(root, environ):
    artifacts=root/OUTPUT
    artifacts.mkdir(mode=0o700)  # Refuse stale receipts or links.
    status={
        "schema":1,"workflow":"SanB","mode":"capacity-audit","measured":False,
        "eligible_for_130_gib":None,"required_free_bytes":REQUIRED_FREE_BYTES,
        "scope":"exact-job workspace before source acquisition",
        "apk_produced":False,"build_admission":False,"compiler_started":False,
        "checkpoint_saved":False,
    }
    try:
        if environ.get("CIRCLE_BRANCH") != BRANCH:
            raise ValueError("Unexpected branch for SanB capacity measurement")
        commit=command(["git","rev-parse","HEAD"],root).strip()
        if re.fullmatch(r"[a-f0-9]{40}",commit) is None or commit!=environ.get("CIRCLE_SHA1"):
            raise ValueError("Unexpected checkout identity for SanB capacity measurement")
        status["checkout"]=commit
        disk=disk_snapshot(root)
        if shutil.disk_usage(root).free != disk["disk_free_bytes_user_available"]:
            # A second glimpse can change under VM activity; keep the
            # unchanged single-call statvfs snapshot as authoritative.
            status["crosscheck"]="available space changed between samples"
        df=command(["df","-B1","--output=source,fstype,size,used,avail,pcent,itotal,iavail,target",
                    "--",str(root)],root)
        print(df,end="",flush=True)
        (artifacts/"df.txt").write_text(df)
        status.update(disk=disk,host=host_snapshot(),cgroup=cgroup_snapshot(),measured=True,
                      result="measurement-complete",eligible_for_130_gib=eligibility(
                          disk["disk_free_bytes_user_available"]))
        print("SANB_CAPACITY measured=true eligible_for_130_gib="
              + str(status["eligible_for_130_gib"]).lower()
              + " disk_free_bytes=" + str(disk["disk_free_bytes_user_available"])
              + " required_free_bytes=" + str(REQUIRED_FREE_BYTES),flush=True)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        status.update(result="measurement-failed",error=type(exc).__name__)
        print("SANB_CAPACITY measured=false eligible_for_130_gib=unknown "
              + type(exc).__name__,file=sys.stderr,flush=True)
        return 1
    finally:
        (artifacts/"status.json").write_text(json.dumps(status,indent=2,sort_keys=True)+"\n")
        # The summary JSON is intentionally limited to public-runtime metrics.
        print(json.dumps(status,sort_keys=True),flush=True)


if __name__=="__main__":
    sys.exit(main(Path.cwd().resolve(),os.environ))
