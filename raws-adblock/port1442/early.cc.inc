#if BUILDFLAG(IS_ANDROID)
  if (ShouldBlockSandiumAdTab(opener, opener_url, opener_top_level_frame_url,
                              target_url, disposition)) return false;
#endif
