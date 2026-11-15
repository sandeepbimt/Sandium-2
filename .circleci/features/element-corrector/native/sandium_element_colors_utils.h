// Copyright 2026 Sandium Authors. BSD-style license.
#ifndef BRAVE_BROWSER_ANDROID_COSMETIC_FILTERS_SANDIUM_ELEMENT_COLORS_UTILS_H_
#define BRAVE_BROWSER_ANDROID_COSMETIC_FILTERS_SANDIUM_ELEMENT_COLORS_UTILS_H_
#include <cstdint>
namespace content {class WebContents;}
namespace sandium {
void NotifyElementColorSelection(content::WebContents*,int64_t);
void NotifyElementColorSessionEnded(content::WebContents*,int64_t);
}
#endif
