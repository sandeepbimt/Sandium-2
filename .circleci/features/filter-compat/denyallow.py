"""Enable ordinary network rules with plain ASCII hostname destinations."""

from native_edits import apply_or_verify, plan_vendor_edits


def edits():
    abstract = "filters/abstract_network.rs"
    net = "filters/network.rs"
    flat = "filters/fb_network.rs"
    builder = "filters/fb_network_builder.rs"
    return [
        (
            abstract,
            "    To(Vec<(bool, &'a str)>),",
            """    To(Vec<(bool, &'a str)>),
    Denyallow(Vec<(bool, &'a str)>),""",
        ),
        (
            abstract,
            "fn parse_filter_options<'a>(",
            """// Do not partially interpret a scoped rule. In particular the upstream domain
// parser drops regex entries, which could turn a restriction into a wider rule.
fn plain_destination_hosts(value: &str, allow_negation: bool) -> bool {
    value.split('|').all(|entry| {
        let host = if allow_negation { entry.strip_prefix('~').unwrap_or(entry) } else { entry };
        // URL canonicalization rewrites numeric hosts such as 127.1 and 0x7f01.
        // Accept those rules only when the spelling is canonical dotted IPv4.
        let last = host.rsplit('.').next().unwrap_or("");
        let numeric = last.bytes().all(|c| c.is_ascii_digit()) ||
            last.strip_prefix("0x").or_else(|| last.strip_prefix("0X"))
                .is_some_and(|n| n.bytes().all(|c| c.is_ascii_hexdigit()));
        if numeric { return host.parse::<std::net::Ipv4Addr>().is_ok(); }
        !host.is_empty() && host.len() <= 253 && host.split('.').all(|label| {
            !label.is_empty() && label.len() <= 63
                && !label.starts_with('-') && !label.ends_with('-')
                && label.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'-')
        })
    })
}

fn supported_destination_context(options: &str, denyallow: bool) -> bool {
    let mut has_source = false;
    let mut has_target = false;
    for part in options.split(',') {
        let (key, value) = part.split_once('=').unwrap_or((part, ""));
        match key {
            "domain" | "from" => {
                if has_source || !plain_destination_hosts(value, true) { return false; }
                has_source = true;
            }
            "to" | "denyallow" => {
                if has_target || !plain_destination_hosts(value, key == "to") { return false; }
                has_target = true;
            }
            "redirect" | "redirect-rule" | "removeparam" => {
                if value.is_empty() { return false; }
            }
            // Other options in this subset are flags validated by the normal
            // parser. Refuse assigned or behavioral options it could approximate.
            _ if part.contains('=') || part.starts_with("~~")
                || matches!(key.trim_start_matches('~'), "generichide" | "ghide" | "csp") => return false,
            _ => {}
        }
    }
    has_target && (!denyallow || has_source)
}

fn parse_filter_options<'a>(""",
        ),
        (
            abstract,
            '            ("to", _) => NetworkFilterOption::To(parse_pipe_delimited_domains(value)?),',
            """            ("to" | "denyallow", false) => {
                let denyallow = option == "denyallow";
                if !supported_destination_context(raw_options, denyallow) {
                    return Err(NetworkFilterError::NoSupportedDomains);
                }
                let domains = value.split('|').map(|entry| match entry.strip_prefix('~') {
                    Some(host) => (false, host),
                    None => (!denyallow, entry),
                }).collect();
                if denyallow {
                    NetworkFilterOption::Denyallow(domains)
                } else {
                    NetworkFilterOption::To(domains)
                }
            }""",
        ),
        (
            net,
            "    const BAD_FILTER = 1 << 0;",
            """    // Keep denyallow and equivalent-looking to rules distinct for badfilter.
    const DENYALLOW = 1 << 6;
    const BAD_FILTER = 1 << 0;""",
        ),
        (
            net,
            "        const IS_EXCEPTION = 1 << 22;",
            """        const IS_EXCEPTION = 1 << 22;
        const HAS_DESTINATION = 1 << 23;""",
        ),
        (
            net,
            """    domains: Vec<(bool, &str)>,
    opt_domains:""",
            """    domains: Vec<(bool, &str)>,
    fold_case: bool,
    opt_domains:""",
        ),
        (
            net,
            "        let domain_hash = utils::fast_hash(domain);",
            """        let domain = if fold_case { cow_ascii_lowercase(domain) } else { Cow::Borrowed(domain) };
        let domain_hash = utils::fast_hash(&domain);""",
        ),
        (
            net,
            """            validate_options(&options)?;""",
            """            validate_options(&options)?;
            let has_destination = options.iter().any(|o| matches!(o,
                NetworkFilterOption::To(_) | NetworkFilterOption::Denyallow(_)));
            mask.set(NetworkFilterMask::HAS_DESTINATION, has_destination);""",
        ),
        (
            net,
            """                            &mut opt_domains,""",
            """                            has_destination,
                            &mut opt_domains,""",
        ),
        (
            net,
            """            options.into_iter().for_each(|option| {""",
            """            options.into_iter().for_each(|option| {
                if matches!(option, NetworkFilterOption::Denyallow(_)) {
                    features_mask.insert(NetworkFilterFeaturesMask::DENYALLOW);
                }""",
        ),
        (
            net,
            "                    NetworkFilterOption::To(domains) => {",
            """                    NetworkFilterOption::To(domains) | NetworkFilterOption::Denyallow(domains) => {""",
        ),
        (
            net,
            """                            &mut opt_to_domains,""",
            """                            true,
                            &mut opt_to_domains,""",
        ),
        (
            net,
            """        compute_filter_id(
            self.modifier_option,""",
            """        let id = compute_filter_id(
            self.modifier_option,""",
        ),
        (
            net,
            """            self.opt_not_domains.as_ref(),
        )
    }""",
            """            self.opt_not_domains.as_ref(),
        );
        if !self.has_to_option() {
            return id;
        }
        // Include polarity and the individual list boundaries in the identity.
        let mut hasher = FxHasher::default();
        hasher.write_u64(id);
        // The base identity already contains both source lists consecutively.
        hasher.write_usize(self.opt_domains.as_ref().map_or(0, Vec::len));
        std::hash::Hash::hash(&self.opt_to_domains, &mut hasher);
        std::hash::Hash::hash(&self.opt_not_to_domains, &mut hasher);
        hasher.finish()
    }""",
        ),
        (
            builder,
            """        // For now, filters with $to options are parsed but ignored
        // to preserve existing matching behavior.
        if filter.has_to_option() {
            return;
        }

        // Redirects are independent of blocking behavior.""",
            """        // Validated destination restrictions survive FlatBuffer serialization.
        // Redirects are independent of blocking behavior.""",
        ),
        (
            "request.rs",
            "        let source_hostname_hashes = if !source_hostname.is_empty() {",
            """        // A trailing DNS root dot denotes the same publisher for domain rules.
        let source_hostname = source_hostname.strip_suffix('.').unwrap_or(source_hostname);
        let source_hostname_hashes = if !source_hostname.is_empty() {""",
        ),
        (
            "optimizer.rs",
            "        && filter.opt_not_domains.is_none()",
            """        && filter.opt_not_domains.is_none()
        && !filter.has_to_option()""",
        ),
        (
            flat,
            """    #[inline(always)]
    pub fn hostname(&self)""",
            """    fn matches_destination(&self, hostname: &str) -> bool {
        let included = self.fb_filter.opt_to_domains().map(fb_vector_to_slice);
        let excluded = self.fb_filter.opt_not_to_domains().map(fb_vector_to_slice);
        let mut hit = included.is_none();
        let mut suffix = hostname.trim_end_matches('.');
        while !suffix.is_empty() {
            if let Some(&index) = self.filter_data_context.unique_domains_hashes_map.get(
                &crate::utils::fast_hash(suffix)
            ) {
                if excluded.is_some_and(|set| crate::utils::bin_lookup(set, index)) { return false; }
                hit |= included.is_some_and(|set| crate::utils::bin_lookup(set, index));
            }
            let Some((_, parent)) = suffix.split_once('.') else { break; };
            suffix = parent;
        }
        hit
    }

    #[inline(always)]
    pub fn hostname(&self)""",
        ),
        (
            flat,
            """        check_pattern(
            self.mask,""",
            """        if self.mask.contains(NetworkFilterMask::HAS_DESTINATION)
            && !self.matches_destination(&request.hostname) {
            return false;
        }
        check_pattern(
            self.mask,""",
        ),
    ]


def plan(core):
    return plan_vendor_edits(core, edits(), "destination matcher")


if __name__ == "__main__":
    apply_or_verify(plan, __doc__)
