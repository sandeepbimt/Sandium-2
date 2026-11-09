use adblock::{Engine, lists::{FilterSet, ParseOptions}};
use std::{env, fs, path::PathBuf};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args_os().skip(1);
    let output = PathBuf::from(args.next().ok_or("missing output DAT path")?);
    let inputs: Vec<PathBuf> = args.map(PathBuf::from).collect();
    if inputs.len() != 27 {
        return Err(format!("expected 27 redistributable list inputs, got {}", inputs.len()).into());
    }

    let mut filter_set = FilterSet::new(false);
    for path in &inputs {
        let rules = fs::read_to_string(path)?;
        if rules.trim().len() < 100 {
            return Err(format!("filter source is unexpectedly small: {}", path.display()).into());
        }
        filter_set.add_filter_list(rules, ParseOptions::default());
    }

    let engine = Engine::new_with_filter_set(filter_set);
    let debug = engine.get_debug_info();
    if debug.source_info.len() != inputs.len() {
        return Err(format!("engine source count mismatch: {} != {}", debug.source_info.len(), inputs.len()).into());
    }
    let network_rules: u64 = debug.source_info.iter().map(|s| u64::from(s.network_filter_count)).sum();
    let cosmetic_rules: u64 = debug.source_info.iter().map(|s| u64::from(s.cosmetic_filter_count)).sum();
    if network_rules == 0 || debug.flatbuffer_size == 0 {
        return Err("generated engine contains no network filters or flatbuffer data".into());
    }

    let dat = engine.serialize();
    if dat.len() < 1024 {
        return Err(format!("serialized DAT is implausibly small: {} bytes", dat.len()).into());
    }
    // Prove that the exact runtime crate version can deserialize the generated
    // artifact before the APK asset can be published.
    let mut verification_engine = Engine::default();
    verification_engine.deserialize(&dat)?;

    if let Some(parent) = output.parent() {
        fs::create_dir_all(parent)?;
    }
    let temporary = output.with_extension("dat.tmp");
    fs::write(&temporary, &dat)?;
    fs::rename(&temporary, &output)?;

    println!("SANDIUM_DAT_SOURCE_COUNT={}", debug.source_info.len());
    println!("SANDIUM_DAT_NETWORK_RULES={}", network_rules);
    println!("SANDIUM_DAT_COSMETIC_RULES={}", cosmetic_rules);
    println!("SANDIUM_DAT_BYTES={}", dat.len());
    println!("SANDIUM_DAT_ROUNDTRIP=PASS adblock=0.13.3");
    Ok(())
}
