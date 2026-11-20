// Run with test_popup_matcher.py <patched-adblock-crate> --cases test_token_index.rs.
use adblock::{Engine, request::Request, utils::fast_hash};

fn main() {
    // These different URL tokens land in the same word and bit for every
    // bitmap size used by the prefilter. The exact rule lookup must separate them.
    let present = "sponsoritem";
    let absent = "unrelated21896";
    assert_eq!(fast_hash(present) as u16, fast_hash(absent) as u16);
    let rules = format!("/{present}/$image\n*$script,domain=publisher.example\n*$3p,media");
    let fresh = Engine::new_with_list_text(rules);
    let mut cached = Engine::default();
    cached.deserialize(&fresh.serialize()).unwrap();
    for matcher in [&fresh, &cached] {
        for (token, source, kind, third, want) in [
            (present, "other.example", "image", true, true),
            (absent, "other.example", "image", true, false),
            ("x", "sub.publisher.example", "script", true, true),
            ("x", "other.example", "script", true, false),
            ("x", "other.example", "media", true, true),
            ("x", "media.example", "media", false, false),
        ] {
            let url = format!("https://media.example/{token}/file");
            let req = Request::preparsed(&url, "media.example", source, kind, third, "GET");
            assert_eq!(matcher.check_network_request(&req).should_block(), want, "{url} {kind}");
        }
    }
    println!("URL, source-domain, fallback-token and collision checks passed");
}
