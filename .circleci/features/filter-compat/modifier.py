"""Keep redirect substitutions and request blocking in separate native rule buckets."""

from native_edits import apply_or_verify, plan_vendor_edits


def edits():
    parser = "filters/abstract_network.rs"
    builder = "filters/fb_network_builder.rs"
    match = "blocker.rs"
    return [
        (
            parser,
            "parse_filter_options(raw_options)?",
            "parse_filter_options(raw_options, exception)?",
        ),
        (
            parser,
            "    raw_options: &'a str,\n) -> Result<Vec<NetworkFilterOption",
            "    raw_options: &'a str,\n    exception: bool,\n) -> Result<Vec<NetworkFilterOption",
        ),
        (
            parser,
            """                // Ignore this filter if no redirection resource is specified
                if value.is_empty() {""",
            """                // A valueless exception cancels all normal substitutions. An
                // explicit empty assignment is invalid, as is a bare block rule.
                if value.is_empty() && !(exception && raw_option == "redirect") {""",
        ),
        (
            parser,
            """            ("redirect-rule", false) => {
                if value.is_empty() {""",
            """            ("redirect-rule", false) => {
                if value.is_empty() && !(exception && raw_option == "redirect-rule") {""",
        ),
        (
            builder,
            """                NetworkFilterListId::Redirects,
                builder,
            );
        }""",
            """                NetworkFilterListId::Redirects,
                builder,
            );
            // A redirect exception cancels only the modifier. Only positive
            // $redirect also contributes an independent network blocking rule.
            if filter.is_exception() || !filter.also_block_redirect() {
                return;
            }
        }""",
        ),
        (
            builder,
            """        } else if (filter.is_redirect() && filter.also_block_redirect()) || !filter.is_redirect() {
            FilterId::Filters
        } else {
            return;
        };""",
            """        } else {
            FilterId::Filters
        };""",
        ),
        (
            match,
            "        // 1. Exceptions - can bail immediately if found\n"
            "        // 2. Find highest priority non-exception redirect",
            "        // Named exceptions cancel that exact directive. A bare exception\n"
            "        // cancels all normal directives. Important substitutions take precedence.",
        ),
        (
            match,
            "            let mut exceptions = vec![];\n            for redirect_filter",
            "            let mut exceptions = vec![];\n            let mut except_all = false;\n"
            "            for redirect_filter",
        ),
        (
            match,
            "                    exceptions.push(redirect);",
            "                    except_all |= redirect.is_empty();\n                    exceptions.push(redirect);",
        ),
        (
            match,
            "                    && !exceptions.contains(&redirect)",
            "                    && (redirect_filter.filter_mask.is_important()\n"
            "                        || (!except_all && !exceptions.contains(&redirect)))",
        ),
        (
            match,
            """                    if let Some((_, p1)) = resource_and_priority {
                        if priority > p1 {
                            resource_and_priority = Some((resource, priority));
                        }
                    } else {
                        resource_and_priority = Some((resource, priority));
                    }""",
            """                    let rank = (redirect_filter.filter_mask.is_important(), priority);
                    if resource_and_priority.is_none_or(|(_, previous)| rank > previous) {
                        resource_and_priority = Some((resource, rank));
                    }""",
        ),
    ]


def plan(core):
    return plan_vendor_edits(core, edits(), "redirect modifier")


if __name__ == "__main__":
    apply_or_verify(plan, __doc__)
