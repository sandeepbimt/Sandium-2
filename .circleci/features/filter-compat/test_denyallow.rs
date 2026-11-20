// Run via test_popup_matcher.py <patched-adblock-crate> --cases test_denyallow.rs.
use adblock::{Engine, filters::network::NetworkFilter, request::Request};

fn case(rules: &str, source: &str, target: &str, third: bool, kind: &str, expected: bool) {
    let url = format!("https://{target}/resource");
    let request = Request::preparsed(&url, target, source, kind, third, "GET");
    let engine = Engine::new_with_list_text(rules);
    let mut fresh = Engine::default();
    fresh.deserialize(&engine.serialize()).unwrap();
    for matcher in [&engine, &fresh] {
        assert_eq!(matcher.check_network_request(&request).should_block(), expected,
                   "{rules}: {kind} from {source} to {target}");
    }
}

fn main() {
    // A deployed rule in uAssets; includes comma options on both sides of denyallow.
    let rule = "*$script,3p,denyallow=cloudflare.com|fastcomments.com|googleapis.com|addtoany.com,from=bluemediafile.sbs|igg-games.com";
    for target in ["cloudflare.com", "cdn.cloudflare.com", "a.b.googleapis.com"] {
        case(rule, "igg-games.com", target, true, "script", false);
    }
    for target in ["ad.example", "notcloudflare.com", "cloudflare.com.ad.example"] {
        case(rule, "www.igg-games.com", target, true, "script", true);
    }
    case(rule, "other.example", "ad.example", true, "script", false);
    case(rule, "igg-games.com", "igg-games.com", false, "script", false);
    case(rule, "igg-games.com", "ad.example", true, "image", false);
    case(&format!("{rule}\n@@||ad.example^$script"), "igg-games.com", "ad.example", true, "script", false);
    case(&format!("{rule},important\n@@||ad.example^$script"), "igg-games.com", "ad.example", true, "script", true);
    let source = "source.example";
    let to = "*$script,to=ADS.EXAMPLE|tracker.example|~safe.ads.example";
    case(to, source, "a.ads.example", true, "script", true);
    case(to, source, "www.ads.example.", true, "script", true);
    case("*$script,to=127.0.0.1", source, "127.0.0.1", true, "script", true);
    case("*$script,to=127.0.0.1", source, "127.0.0.2", true, "script", false);
    case(rule, "igg-games.com.", "ad.example", true, "script", true);
    case(to, source, "cdn.safe.ads.example", true, "script", false);
    case(to, source, "tracker.example", true, "script", true);
    case(to, source, "fakeads.example", true, "script", false);
    case("*$script,to=~allowed.example", source, "sub.allowed.example", true, "script", false);
    case("*$script,to=~allowed.example", source, "ad.example", true, "script", true);
    let allow = "*$script\n@@*$script,domain=SOURCE.EXAMPLE|~skip.source.example,denyallow=AD.EXAMPLE";
    case(allow, source, "allowed.example", true, "script", false);
    case(allow, source, "ad.example", true, "script", true);
    case(allow, "skip.source.example", "allowed.example", true, "script", true);
    // Canonical sorted and deduplicated destination hash sets survive badfilter.
    let distinct = "*$script,to=ad.example\n*$script,to=allowed.example,badfilter";
    case(distinct, source, "ad.example", true, "script", true);
    case("*$script,to=ad.example\n*$script,to=~ad.example,badfilter", source, "ad.example", true, "script", true);
    case("*$script,to=ad.example\n*$script,badfilter", source, "ad.example", true, "script", true);
    case("*$script,denyallow=a.example|b.example,from=source.example\n*$from=source.example,script,badfilter,denyallow=b.example|a.example|a.example", source, "ad.example", true, "script", false);
    case("*$script,denyallow=a.example,from=source.example\n*$script,to=~a.example,from=source.example,badfilter", source, "ad.example", true, "script", true);
    case("*$script,to=a.example\n*$script,to=b.example", source, "a.example", true, "script", true);
    case("*$script,to=a.example\n*$script,to=b.example", source, "b.example", true, "script", true);
    case("*$script,to=a.example\n*$script,to=b.example", source, "c.example", true, "script", false);
    for bad in [
        "*$script,denyallow=good.example", "*$script,domain=a.example,denyallow=",
        "*$script,domain=,denyallow=x.example", "*$script,~domain=source.example,denyallow=x.example",
        "*$script,domain=a.example,~denyallow=x.example", "*$script,domain=a.example,denyallow=~ok.example",
        "*$script,domain=a.example,denyallow=good.example|/ad/", "*$script,domain=a.example,denyallow=good.example|foo.*",
        "*$script,domain=a.example,denyallow=good.example|", "*$script,domain=a.example,denyallow=..example",
        "*$script,domain=a.example,denyallow=-bad.example", "*$script,domain=a.example,denyallow=https://good.example",
        "*$script,domain=source.example|~/excluded/,denyallow=a.example",
        "*$script,domain=source.example,denyallow=a.example,to=b.example",
        "*$script,to=a.example,domain=source.example,denyallow=b.example",
        "*$script,to=a.example,to=b.example", "*$script,~to=x.example",
        "*$script,to=0.1", "*$script,to=127.1", "*$script,to=0x7f000001",
        "*$script,to=010.001.000.001",
        "*$script,to=/foo/|a.example", "*$script,to=foo.*|a.example",
    ] {
        assert!(NetworkFilter::parse(bad, false, Default::default()).is_err(), "{bad}");
        case(bad, source, "ad.example", true, "script", false);
    }
    println!("Native destination-rule regression checks passed on fresh and restored engines.");
}
