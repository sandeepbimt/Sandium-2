"""Skip binary searches for request tokens absent from both indexes of a filter list."""

from native_edits import apply_or_verify, plan_vendor_edits


def edits():
    rules = "network_filter_list.rs"
    blocker = "blocker.rs"
    return [
        (
            rules,
            "/// Internal structure to keep track of a collection of network filters.",
            """/// A missing bit proves neither index contains this token. Collisions still
/// go through the existing exact lookup. Rebuilt from the actual FlatBuffer
/// indexes, including when an engine is deserialized.
pub(crate) struct TokenPresence(Box<[u64]>);

impl TokenPresence {
    pub(crate) fn new(list: fb::NetworkFilterList<'_>) -> Self {
        let patterns = list.filter_map_index();
        let domains = list.opt_domains_map_index();
        let count = patterns.len() + domains.len();
        // Power of two for the lookup mask, at most 8 KiB per list.
        let words = count.div_ceil(8).clamp(1, 1024).next_power_of_two();
        let mut buckets = vec![0u64; words].into_boxed_slice();
        for hash in patterns.iter().chain(domains.iter()) {
            let word = (hash as usize >> 6) & (words - 1);
            buckets[word] |= 1u64 << (hash & 63);
        }
        Self(buckets)
    }

    #[inline]
    fn may_contain(&self, hash: ShortHash) -> bool {
        let word = (hash as usize >> 6) & (self.0.len() - 1);
        self.0[word] & (1u64 << (hash & 63)) != 0
    }
}

/// Internal structure to keep track of a collection of network filters.""",
        ),
        (
            rules,
            "pub(crate) struct NetworkFilterList<'a> {",
            "pub(crate) struct NetworkFilterList<'a> {\n    pub(crate) token_presence: &'a TokenPresence,",
        ),
        (
            rules,
            "            if let Some(iter) = filter_map.get(to_short_hash(*token)) {",
            """            let hash = to_short_hash(*token);
            if !self.token_presence.may_contain(hash) {
                continue;
            }
            if let Some(iter) = filter_map.get(hash) {""",
        ),
        (
            blocker,
            "use crate::network_filter_list::NetworkFilterList;",
            "use crate::network_filter_list::{NetworkFilterList, TokenPresence};",
        ),
        (
            blocker,
            "pub struct Blocker {",
            "pub struct Blocker {\n    token_presence: Box<[TokenPresence]>,",
        ),
        (
            blocker,
            "        NetworkFilterList {\n            list:",
            "        let index = id as usize;\n        NetworkFilterList {\n            token_presence: &self.token_presence[index],\n            list:",
        ),
        (blocker, ".get(id as usize),", ".get(index),"),
        (
            blocker,
            "    pub(crate) fn from_context(filter_data_context: FilterDataContextRef) -> Self {\n        Self {",
            """    pub(crate) fn from_context(filter_data_context: FilterDataContextRef) -> Self {
        let token_presence = filter_data_context.memory.root().network_rules().iter()
            .map(TokenPresence::new).collect();
        Self {
            token_presence,""",
        ),
    ]


def plan(core):
    return plan_vendor_edits(core, edits(), "request token index")


if __name__ == "__main__":
    apply_or_verify(plan, __doc__)
