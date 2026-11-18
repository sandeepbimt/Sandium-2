"""Small, exact-source checked infrastructure adapter, not browser behavior."""
SISO_MAIN='build/config/siso/main.star'
ANCHOR='    step_config = __unset_timeout(ctx, step_config)\n'
BLOCK='''
    # RawS BuildBuddy: preserve canonical paths and materialize working_directory.
    for rule in step_config["rules"]:
        if rule.get("remote", False):
            rule["canonicalize_dir"] = True
            inputs = rule.get("inputs", [])
            if "./args.gn" not in inputs:
                inputs.append("./args.gn")
            rule["inputs"] = inputs
'''

def patched_siso(original):
    if original.count(ANCHOR)!=1 or BLOCK in original:
        raise ValueError('Unsupported upstream Siso insertion point; review Chromium upgrade')
    return original.replace(ANCHOR,ANCHOR+BLOCK,1)

def apply_siso(src, original):
    target=src/SISO_MAIN
    expected=patched_siso(original)
    actual=target.read_text()
    if actual not in (original,expected):
        raise ValueError('Unexpected Siso source changes; refusing compatibility patch')
    if actual!=expected:target.write_text(expected)
    return expected
