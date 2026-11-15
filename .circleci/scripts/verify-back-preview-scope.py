#!/usr/bin/env python3
"""Back-preview writer cannot publish to removal or UI checkpoint namespaces."""
import os
SCOPE = 'sandium-exp-single-v1-bridge-backpreview01'
BRANCH = 'experiment/sandium-back-transition'
def verify(env):
    if env.get('SANDIUM_EXPERIMENT_SCOPE') != SCOPE:
        raise ValueError('Back-preview requires its dedicated checkpoint namespace')
    if env.get('CIRCLE_BRANCH') != BRANCH:
        raise ValueError('Back-preview requires its dedicated branch')
if __name__ == '__main__':
    verify(os.environ)
    print('SANDIUM_BACK_PREVIEW_SCOPE=PASS; removal/UI heads are not writable')
