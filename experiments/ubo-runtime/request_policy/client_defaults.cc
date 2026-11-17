// Default embedder capabilities remain disabled.
bool ExtensionsAPIClient::SupportsPrivateWebRequestPolicy(
    const ExtensionId&) const {
  return false;
}

bool ExtensionsAPIClient::ReportPrivateBlockedResource(
    const ExtensionId&, content::WebContents*, const GURL&) const {
  return false;
}

base::DictValue ExtensionsAPIClient::GetPrivateFilterLists(
    content::BrowserContext*, const ExtensionId&) const {
  return {};
}

void ExtensionsAPIClient::AugmentWebRequestEventForExtension(
    content::BrowserContext*, const WebRequestInfo&, const ExtensionId&,
    bool, base::DictValue&) const {}
