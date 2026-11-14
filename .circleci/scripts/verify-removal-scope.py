#!/usr/bin/env python3
"""Prevent Removal jobs from selecting or publishing removal checkpoint heads."""
import os

SCOPE = 'sandium-exp-single-v1-bridge-crash01'
BRANCH = 'experiment/sandium-overnight-removal'

def verify(env):
    if env.get('SANDIUM_EXPERIMENT_SCOPE') != SCOPE:
        raise ValueError('Removal product requires its dedicated checkpoint namespace')
    if env.get('CIRCLE_BRANCH') != BRANCH:
        raise ValueError('Removal product requires its dedicated branch')

if __name__ == '__main__':
    verify(os.environ)
    print('SANDIUM_REMOVAL_SCOPE=PASS; UI checkpoint namespace is not writable here')
