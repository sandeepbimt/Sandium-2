#!/usr/bin/env python3
"""Prevent UI-only jobs from selecting or publishing removal checkpoint heads."""
import os

SCOPE = 'sandium-exp-single-v1-bridge-ui1088'
BRANCH = 'experiment/sandium-ui-only'

def verify(env):
    if env.get('SANDIUM_EXPERIMENT_SCOPE') != SCOPE:
        raise ValueError('UI-only product requires its dedicated checkpoint namespace')
    if env.get('CIRCLE_BRANCH') != BRANCH:
        raise ValueError('UI-only product requires its dedicated branch')

if __name__ == '__main__':
    verify(os.environ)
    print('SANDIUM_UI_ONLY_SCOPE=PASS; removal checkpoint namespace is not writable here')
