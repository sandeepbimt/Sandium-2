"""Run native popup regression cases against a patched adblock-rust source checkout.

Usage: python3 test_popup_matcher.py /path/to/patched/adblock-rust
Uses Cargo offline with the checkout's lockfile and Brave's feature selection.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


# These assertions use the same parsed request inputs and public matcher as Brave.
# Matching is entirely offline, including the upstream list examples.
NATIVE_CASES = r'''
use adblock::{Engine, FilterSet, lists::{FilterFormat, ParseOptions}, request::Request};

fn check(
    rules: &str,
    url: &str,
    source: &str,
    third_party: bool,
    kind: &str,
    expected: bool,
) {
    let hostname = url.strip_prefix("https://").unwrap().split('/').next().unwrap();
    let request = Request::preparsed(url, hostname, source, kind, third_party, "GET");
    let engine = Engine::new_with_list_text(rules);
    let mut restored = Engine::default();
    restored.deserialize(&engine.serialize()).unwrap();
    for matcher in [&engine, &restored] {
        let blocked = matcher.check_network_request(&request).should_block();
        assert_eq!(blocked, expected, "{kind} {url} from {source} with {rules}");
    }
}

fn check_host_list() {
    let mut filters = FilterSet::new(false);
    filters.add_filter_list("0.0.0.0 ad.example".to_owned(), ParseOptions {
        format: FilterFormat::Hosts, ..Default::default()
    });
    let engine = Engine::new_with_filter_set(filters);
    let mut restored = Engine::default();
    restored.deserialize(&engine.serialize()).unwrap();
    for matcher in [&engine, &restored] {
        for (kind, expected) in [("popup", false), ("document", true), ("image", true)] {
            let req = Request::preparsed("https://ad.example/pop", "ad.example",
                                         "player.example", kind, true, "GET");
            assert_eq!(matcher.check_network_request(&req).should_block(), expected, "{kind}");
        }
    }
}

fn main() {
    // Examples from uAssets filters/filters.txt, exercised without visiting them.
    let domain_rule = "||adsession.com^$popup";
    let ad = "https://adsession.com/video";
    let opener = "player.example";
    check(domain_rule, ad, opener, true, "popup", true);
    for ordinary in ["document", "subdocument", "other", "script", "image", "media", "xhr"] {
        check(domain_rule, ad, opener, true, ordinary, false);
    }
    for kind in ["popup", "document"] {
        check("||dogsprotectedfeed.info^$popup,doc", "https://dogsprotectedfeed.info/ad",
              opener, true, kind, true);
    }
    let restrict = "*$3p,popup,domain=babesxworld.com";
    check(restrict, ad, "babesxworld.com", true, "popup", true);
    check(restrict, ad, "another.example", true, "popup", false);
    check(restrict, "https://babesxworld.com/stream", "babesxworld.com", false, "popup", false);

    // Exact popup matching, exceptions, negation, and ordinary-request isolation.
    let target = "https://ad.example/pop";
    let allow = "||ad.example^$popup\n@@||ad.example/pop$popup";
    check(allow, target, opener, true, "popup", false);
    check(allow, "https://ad.example/unrelated", opener, true, "popup", true);
    check("||ad.example^$popup,important\n@@||ad.example^$popup",
          target, opener, true, "popup", true);
    let disabled = "||ad.example^$popup,3p\n||ad.example^$3p,popup,badfilter";
    check(disabled, target, opener, true, "popup", false);
    check("||ad.example^$popup,3p", target, opener, true, "popup", true);
    check("||ad.example^$popup\n@@||ad.example^", target, opener, true, "popup", true);
    check("||ad.example^$document\n@@||ad.example^$popup", target, opener, true, "document", true);
    check("||ad.example^$document\n@@||ad.example^$popup,document",
          target, opener, true, "document", false);
    check("||ad.example^$document\n@@||ad.example^", target, opener, true, "document", false);
    check("||ad.example^$~popup", target, opener, true, "popup", false);
    check("||ad.example^$~popup", target, opener, true, "image", true);
    check("||ad.example^$popup,image", target, opener, true, "image", true);
    check("||ad.example^$popup,image", target, opener, true, "popup", true);
    check("||ad.example^$popup,image", target, opener, true, "script", false);
    check("||ad.example^", target, opener, true, "popup", false);
    check("||ad.example^", target, opener, true, "image", true);
    check("||ad.example^$script", target, opener, true, "popup", false);
    check("/ad[0-9]+/o/$popup", "https://ad.example/ad42/o/", opener, true, "popup", true);
    check("/ad[0-9]+/o/$popup", "https://ad.example/adxx/o/", opener, true, "popup", false);
    check("||ad.example^$all", target, opener, true, "popup", true);
    check("||ad.example^$all,~popup", target, opener, true, "popup", false);
    let filtered_opener = "||ad.example^$popup,domain=player.example|~live.player.example";
    check(filtered_opener, target, "embed.player.example", true, "popup", true);
    check(filtered_opener, target, "live.player.example", true, "popup", false);
    check_host_list();
    // EasyPrivacy's generic tracking filter excludes two navigation types.
    let image = "https://wt.soundestlink.com/webtracking/pixel";
    let tracking = "/webtracking/*$~frame,~document,from=~wwwapps.ups.com";
    check(tracking, image, "github.myshopify.com", true, "image", true);
    for kind in ["document", "subdocument", "popup"] {
        check(tracking, image, "github.myshopify.com", true, kind, false);
    }
    check(tracking, image, "wwwapps.ups.com", true, "image", false);
    let except_resources = "||ad.example^$all\n@@||ad.example^$~doc";
    check(except_resources, target, opener, true, "document", true);
    check(except_resources, target, opener, true, "image", false);
    check(except_resources, target, opener, true, "popup", true);
    check("||ad.example^$document,~doc", target, opener, true, "document", false);
    check("||ad.example^$all,~doc", target, opener, true, "popup", true);
    println!("Native request-type checks passed on fresh and deserialized engines");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("crate", type=Path)
    parser.add_argument("--cases", type=Path, help="use an alternate native regression program")
    args = parser.parse_args()
    crate = args.crate.resolve()
    with tempfile.TemporaryDirectory(prefix="sandium-native-popup-") as dirname:
        project = Path(dirname)
        (project / "src").mkdir()
        (project / "src/main.rs").write_text(args.cases.read_text() if args.cases else NATIVE_CASES)
        shutil.copyfile(crate / "Cargo.lock", project / "Cargo.lock")
        (project / "Cargo.toml").write_text(
            '[package]\nname = "sandium-popup-regression"\n'
            'version = "0.1.0"\nedition = "2024"\n'
            '[dependencies]\n'
            f'adblock = {{ path = {json.dumps(str(crate))}, default-features = false, '
            'features = ["full-regex-handling", "debug-info", "css-validation"] }\n'
        )
        subprocess.run(["cargo", "run", "--offline", "--quiet"], cwd=project, check=True)


if __name__ == "__main__":
    main()
