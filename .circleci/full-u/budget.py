"""Dynamic one-hour preservation budget; estimates never extend the deadline."""
import math

def plan(start,now,source_bytes,free_bytes,history=None):
 for name,value in [('start',start),('now',now),('source_bytes',source_bytes),('free_bytes',free_bytes)]:
  if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('invalid '+name)
 if now<start:raise ValueError('clock reversed')
 # Padded archive/upload observations are floors, not promises of throughput.
 archive=max(900,math.ceil(source_bytes/80_000_000));upload=max(480,math.ceil(source_bytes/80_000_000))
 provenance=['conservative full-archive floors; no target158 timings yet']
 for sample in history or []:
  if not sample.get('provenance'):raise ValueError('missing measurement provenance')
  for key in ('source_bytes','archive_seconds','upload_seconds'):
   if type(sample.get(key)) not in (int,float) or not math.isfinite(sample[key]) or sample[key]<=0:raise ValueError('invalid measured history')
  scale=source_bytes/sample['source_bytes']*1.25
  archive=max(archive,math.ceil(sample['archive_seconds']*scale));upload=max(upload,math.ceil(sample['upload_seconds']*scale))
  provenance.append(sample['provenance'])
 # No fixed first-stage720s: derive the work window entirely from remaining time.
 reserve=archive+upload+240+60+300
 remaining=max(0,math.floor(start+3600-now));work=max(0,remaining-reserve)
 disk_required=math.ceil(source_bytes*1.05)+9*1024**3
 return dict(deadline=start+3600,remaining_seconds=remaining,work_seconds=work if work>=60 else 0,
             archive_seconds=archive,upload_seconds=upload,reserve_seconds=reserve,
             disk_required_bytes=disk_required,free_bytes=free_bytes,
             can_work=work>=60 and free_bytes>=disk_required+8*1024**3,
             can_capture=remaining>=reserve-60 and free_bytes>=disk_required,provenance=provenance)
