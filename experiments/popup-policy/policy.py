"""Inactive lifecycle prototype. NOT an adblock parser or production matcher.

An injected matcher must implement real engine semantics, including explicit
popup/popunder types and exceptions. This prototype tests safe context handling
without changing shipped browser behavior.
"""
from dataclasses import dataclass, replace
from enum import Enum


class Kind(Enum):
    POPUP = 'popup'
    POPUNDER = 'popunder'


class Verdict(Enum):
    ALLOW = 'allow'
    BLOCK = 'block'
    DEFER = 'defer'
    CANCEL = 'cancel'


@dataclass(frozen=True)
class Context:
    target: str
    frame_opener: str
    root_opener: str
    kind: Kind


@dataclass(frozen=True)
class Match:
    blocked: bool = False
    excepted: bool = False
    important: bool = False

    def verdict(self):
        return Verdict.BLOCK if self.important or (self.blocked and not self.excepted) else Verdict.ALLOW


class Candidate:
    """One opening navigation only, with stale-completion protection.

    Popunder classification is external and explicit. This code never guesses
    it from foreground/background disposition or closes an opener tab.
    """
    def __init__(self, context: Context, native_allowed: bool, shields_enabled: bool):
        if not context.frame_opener or not context.root_opener:
            raise ValueError('resolved opener provenance required')
        self.context = context
        self.native_allowed = native_allowed
        self.shields_enabled = shields_enabled
        self.generation = 0
        self.active = True

    def begin(self, target: str):
        if not self.active:
            return Verdict.CANCEL, None
        if not self.native_allowed:
            return Verdict.BLOCK, None
        self.generation += 1
        self.context = replace(self.context, target=target)
        if not self.shields_enabled:
            return Verdict.ALLOW, None
        # Token contains immutable context for work on the engine sequence.
        return Verdict.DEFER, (self.generation, self.context)

    def complete(self, token, result: Match):
        if not self.active or token is None or token[0] != self.generation:
            return Verdict.CANCEL
        self.generation += 1  # one completion per deferred request
        return result.verdict()

    def invalidate(self):
        # Call on destruction, user-initiated replacement navigation, or final
        # opening-navigation completion. Future navigations are not popups.
        self.active = False
        self.generation += 1
