#!/usr/bin/env python3
"""Opt-in tracing only: distinguish filter generation from renderer submission.

No filter rules, permissions, script contents, URLs or popup policies are changed.
The events require brave.adblock tracing; they do not prove scriptlet execution.
"""
from pathlib import Path
import subprocess
import sys

PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'
ENGINE = 'components/brave_shields/content/browser/ad_block_engine_wrapper.cc'
RENDERER = 'components/cosmetic_filters/renderer/cosmetic_filters_js_handler.cc'


def insert(source, anchor, addition):
    if addition in source:
        return source
    if source.count(anchor) != 1:
        raise RuntimeError('filter diagnostics: pinned anchor mismatch')
    return source.replace(anchor, anchor + addition, 1)


ENGINE_ADDITION = '''
  // Sandium diagnostics: sizes only, never log rule text or website content.
  // A nonempty payload proves generation, not successful scriptlet execution.
  const auto* sandium_default_script = resources.FindString("injected_script");
  const auto* sandium_additional_script =
      additional_resources.FindString("injected_script");
  TRACE_EVENT2("brave.adblock", "SandiumScriptletSources",
               "default_bytes", sandium_default_script
                   ? sandium_default_script->size() : 0u,
               "additional_bytes", sandium_additional_script
                   ? sandium_additional_script->size() : 0u);
'''
MERGED_ADDITION = '''
  const auto* sandium_merged_script = resources.FindString("injected_script");
  TRACE_EVENT1("brave.adblock", "SandiumScriptletMerged",
               "bytes", sandium_merged_script
                   ? sandium_merged_script->size() : 0u);
'''
RENDERER_ADDITION = '''
  // Submission is deliberately distinct from successful execution. Existing
  // nested EvaluateScript events identify whether the main world was entered.
  const auto* sandium_script_text =
      resources_dict_->FindString("injected_script");
  TRACE_EVENT2("brave.adblock", "SandiumScriptletRendererInput",
               "is_string", sandium_script_text != nullptr,
               "bytes", sandium_script_text ? sandium_script_text->size() : 0u);
'''
SUBMIT_ADDITION = '''
    TRACE_EVENT1("brave.adblock", "SandiumScriptletSubmit",
                 "serialized_bytes", scriptlet_script.size());'''


def engine(s):
    s = insert(s, '      additional_filters_engine_->UrlCosmeticResources(url);\n', ENGINE_ADDITION)
    return insert(s, '                     /*force_hide=*/true);\n', MERGED_ADDITION)


def renderer(s):
    s = insert(s, '  base::Value* injected_script = resources_dict_->Find("injected_script");\n', RENDERER_ADDITION)
    return insert(s, '  if (!scriptlet_script.empty()) {', SUBMIT_ADDITION)


TRANSFORMS = {ENGINE: engine, RENDERER: renderer}


def apply(core):
    outputs = {p: f((core / p).read_text()) for p, f in TRANSFORMS.items()}
    for p, data in outputs.items():
        (core / p).write_text(data)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: apply-sandium-filter-diagnostics.py <brave-core>')
    core = Path(sys.argv[1]).resolve()
    if subprocess.check_output(['git', '-C', str(core), 'rev-parse', 'HEAD'], text=True).strip() != PIN:
        sys.exit('filter diagnostics requires pinned Brave core ' + PIN)
    apply(core)
    print('SANDIUM_FILTER_DIAGNOSTICS=PASS trace_only=no_policy_change')
