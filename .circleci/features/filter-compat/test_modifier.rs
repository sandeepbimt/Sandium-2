// Run via test_popup_matcher.py <patched-adblock-crate> --cases test_modifier.rs.
use adblock::resources::{MimeType, Resource, ResourceType};
use adblock::{Engine, request::Request};

fn resource(name: &str, base64: &str) -> Resource {
    Resource {
        name: name.into(), aliases: vec![], kind: ResourceType::Mime(MimeType::TextPlain),
        content: base64.into(), dependencies: vec![], permission: Default::default(),
    }
}

fn check(rules: &[&str], blocked: bool, exception: bool, substitution: Option<&str>) {
    let req = Request::preparsed("https://www.google-analytics.com/analytics.js",
        "www.google-analytics.com", "www.stern.de", "script", true, "GET");
    let mut built = Engine::new_with_list_text(rules.join("\n"));
    let mut restored = Engine::default();
    restored.deserialize(&built.serialize()).unwrap();
    for matcher in [&mut built, &mut restored] {
        matcher.use_resources([resource("google-analytics.com/analytics.js", "QQ=="),
                               resource("alternate.js", "Qg==")]);
        let result = matcher.check_network_request_subset(&req, false, true);
        assert_eq!((result.should_block(), result.exception.is_some(), result.redirect.as_deref()),
                   (blocked, exception, substitution), "{rules:?}");
    }
}

fn main() {
    // Actual uAssets modifier exception and the corresponding resource directive.
    let except = "@@||google-analytics.com/analytics.js$script,redirect-rule=google-analytics.com/analytics.js:5,domain=stern.de";
    let block = "||google-analytics.com^$script";
    let replace = "||google-analytics.com/analytics.js$script,redirect-rule=google-analytics.com/analytics.js:5";
    let alternate = "||google-analytics.com^$script,redirect-rule=alternate.js:3";
    let a = Some("data:text/plain;base64,QQ==");
    let b = Some("data:text/plain;base64,Qg==");
    check(&[block, replace], true, false, a);
    check(&[block, replace, except], true, false, None);
    check(&[block, replace, except, alternate], true, false, b);
    check(&[except], false, false, None);
    check(&[block, except], true, false, None);
    check(&[block, replace, "@@||google-analytics.com^$redirect-rule"], true, false, None);
    check(&[block, replace, alternate, "@@||google-analytics.com^$redirect"], true, false, None);
    check(&[block, replace, "@@||google-analytics.com^$redirect-rule="], true, false, a);
    check(&[block, replace, "@@||google-analytics.com^$redirect="], true, false, a);
    check(&[block, replace, "@@||google-analytics.com^$redirect-rule=alternate.js:3"], true, false, a);
    check(&[block, replace, "@@||google-analytics.com^$redirect=google-analytics.com/analytics.js:5"],
          true, false, None);
    check(&[block, replace, "@@||google-analytics.com^$redirect-rule=google-analytics.com/analytics.js"],
          true, false, a);
    let combined = "||google-analytics.com/analytics.js$redirect=google-analytics.com/analytics.js:5";
    check(&[combined, except], true, false, None);
    check(&[block, "@@||google-analytics.com^$script"], false, true, None);
    check(&[replace], false, false, a);
    let important = "||google-analytics.com^$script,redirect-rule=alternate.js:1,important";
    check(&[important], false, false, b);
    check(&[block, replace, important], true, false, b);
    check(&[block, replace, important, "@@||google-analytics.com^$redirect-rule"], true, false, b);
    check(&[block, important, "@@||google-analytics.com^$redirect-rule=alternate.js:1"], true, false, b);
    check(&["||google-analytics.com^$redirect"], false, false, None);
    check(&["||google-analytics.com^$redirect-rule"], false, false, None);
    println!("Redirect modifier checks passed on fresh and deserialized engines");
}
