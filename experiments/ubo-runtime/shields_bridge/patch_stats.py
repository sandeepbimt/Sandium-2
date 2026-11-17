"""Attach actual upstream uBO network block outcomes to local Shields telemetry."""
from pathlib import Path

def replace_once(text, before, after):
    if after in text:
        return text
    if text.count(before) != 1:
        raise ValueError('Unexpected uBO stats anchor: ' + before[:80])
    return text.replace(before, after)

def patch_stats(bundle, source):
    target = bundle / 'js/traffic.js'
    text = target.read_text()
    before = "import µb from './background.js';"
    text = replace_once(text, before, before + "\nimport { blockReporter as sandiumBlockReporter } from './sandium-stats.js';")
    before = '    const result = pageStore.filterRequest(fctxt);'
    after = before + '\n    if ( result === 1 ) { sandiumBlockReporter.report(details); }'
    text = replace_once(text, before, after)
    # Root-frame strict blocking is reported only if upstream actually cancels.
    # Native page-epoch validation may reject it after navigation; no replay.
    before = '        return onBeforeRootFrameRequest(fctxt);'
    after = '''        const sandiumRootResult = onBeforeRootFrameRequest(fctxt);
        if ( sandiumRootResult?.cancel === true ) { sandiumBlockReporter.report(details); }
        return sandiumRootResult;'''
    text = replace_once(text, before, after)
    target.write_text(text)
    (bundle / 'js/sandium-stats.js').write_bytes((source / 'sandium-stats.js').read_bytes())
