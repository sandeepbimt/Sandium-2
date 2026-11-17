#ifndef BRAVE_BROWSER_EXTENSIONS_SANDIUM_UBO_STARTUP_H_
#define BRAVE_BROWSER_EXTENSIONS_SANDIUM_UBO_STARTUP_H_
namespace content { class NavigationThrottleRegistry; }
namespace sandium_ubo {
void AddStartupNavigationThrottle(content::NavigationThrottleRegistry&);
}
#endif
