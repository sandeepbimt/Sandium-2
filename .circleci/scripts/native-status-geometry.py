#!/usr/bin/env python3
"""Plan reversible native inset ownership with paint-only status customization.
Called by the whole navigation experiment after ordinary overlays; no independent
build switch or writer. Unknown overlap fails before any source file changes.
"""
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'.circleci/features/native-status-geometry'
REVERSAL=json.loads((DATA/'reversal.json').read_text())
PAINT=json.loads((DATA/'paint.json').read_text())
MARKER='// Sandium native-navigation experiment: status paint only.'

def owned_identifiers(pairs):
    result=set()
    for old,new in pairs:
        old_tokens=set(re.findall(r'\b\w+\b',old))
        for name in re.findall(r'\b\w+\b',new):
            if name not in old_tokens and ('Sandium' in name or 'SANDIUM' in name):result.add(name)
    return result

def transform(name,text,paint=True):
    if not paint and MARKER in text:
        for old,new in reversed(PAINT.get(name,[])):
            if text.count(new)!=1:raise RuntimeError('Unknown legacy status paint: '+name)
            text=text.replace(new,old,1)
        if MARKER in text:raise RuntimeError('Residual legacy status paint: '+name)
    paints=PAINT.get(name,[]) if paint else []
    if MARKER in text:
        if not paints or any(text.count(new)!=1 for old,new in paints):
            raise RuntimeError('Unknown native status paint: '+name)
    else:
        has_overlay = bool(owned_identifiers(REVERSAL[name]) & set(re.findall(r'\b\w+\b',text)))
        for old,new in reversed(REVERSAL[name]) if has_overlay else []:
            count=text.count(new)
            if count==1:text=text.replace(new,old,1)
            elif count>1:raise RuntimeError('Duplicate status overlay: '+name)
            elif text.count(old)!=1:raise RuntimeError('Unknown status overlay: '+name+' '+old[:60])
        for old,new in paints:
            if text.count(old)!=1:raise RuntimeError('Native paint anchor mismatch: '+name)
            text=text.replace(old,new,1)
    forbidden=owned_identifiers(REVERSAL[name])-owned_identifiers(paints)
    remaining=forbidden & set(re.findall(r'\b\w+\b',text))
    if remaining:raise RuntimeError('Partial status geometry reversal: '+name+' '+','.join(sorted(remaining)))
    if name.endswith('/ToolbarPositionController.java') and 'consumeTopInset = false;' in text:
        raise RuntimeError('Residual bottom-toolbar inset suppression: '+name)
    return text

def plan(root,paint=True):
    result={}
    for name in REVERSAL:
        path=root/name
        result[path]=transform(name,path.read_text(),paint=paint)
    return result
