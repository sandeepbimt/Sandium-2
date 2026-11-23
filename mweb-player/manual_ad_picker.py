"""Scoped source changes for explicit, exact-page-element ad picks."""
from glue import once

PICKER = 'chrome/renderer/raws_element_picker_donor.h'
POLICY = 'chrome/browser/raws/raw_element_rule_policy.h'
RENDERER = 'chrome/renderer/chrome_render_frame_observer.cc'
OWNERS = {
    PICKER: 'd2483e071fae0ba82c153e2f6360502675a2ada56df7193499a04190e1b402bd',
    POLICY: '6e9d9622b987bd9fc92b704be2d37942f1b3fb8a351fc97760182c2c90dad891',
    RENDERER: '20aaba181642b68583841c48a800ea343b804eb09229416638d8643e373def71',
}

LOCATOR = r'''  const selectorOf = element => {
    if (!element || !element.isConnected || element.getRootNode() !== document)
      return '';
    const steps = [];
    for (let node = element; node; node = node.parentElement) {
      const token = node.id;
      if (identifier.test(token)) {
        const matches = document.querySelectorAll('#' + token);
        if (matches.length === 1 && matches[0] === node)
          return ['#' + token, ...steps.reverse()].join(' > ');
      }
      if (node === root) return [':root', ...steps.reverse()].join(' > ');
      const parent = node.parentElement;
      if (!parent || steps.length >= 128) return '';
      let index = 1;
      for (let sibling = node.previousElementSibling; sibling;
           sibling = sibling.previousElementSibling) {
        if (++index > 1000000) return '';
      }
      const tag = safeTag.test(node.localName) ? node.localName : '*';
      steps.push(tag + ':nth-child(' + index + ')');
    }
    return '';
  };
  const previewMatches = (node, selector) => {
    if (!selector || selector.length > maxSelectorBytes || selectorOf(node) !== selector)
      return null;
    const matches = document.querySelectorAll(selector);
    return matches.length === 1 && matches[0] === node ? [node] : null;
  };
'''

GRAMMAR = r'''inline constexpr size_t kMaxPickedSelectorBytes = 4096;

constexpr bool IsPickerTag(std::string_view tag) {
  if (tag.empty() || tag.size() >= 32 ||
      tag.front() < 'a' || tag.front() > 'z') return false;
  for (char ch : tag) {
    if (!(ch >= 'a' && ch <= 'z') && !(ch >= '0' && ch <= '9') &&
        ch != '-') return false;
  }
  return true;
}

constexpr bool IsPickerPath(std::string_view selector) {
  constexpr std::string_view separator = " > ";
  constexpr std::string_view nth = ":nth-child(";
  const auto first = selector.find(separator);
  const auto anchor = selector.substr(0, first);
  if (anchor != ":root" &&
      (!anchor.starts_with('#') || !IsElementRuleIdentifier(anchor.substr(1))))
    return false;
  if (first == selector.npos) return anchor == ":root";
  selector.remove_prefix(first + separator.size());
  for (size_t steps = 0; steps < 128; ++steps) {
    const auto end = selector.find(separator);
    const auto step = selector.substr(0, end);
    const auto marker = step.find(nth);
    if (marker == step.npos || !step.ends_with(')')) return false;
    const auto tag = step.substr(0, marker);
    if (tag != "*" && !IsPickerTag(tag)) return false;
    const auto number = step.substr(marker + nth.size(),
                                    step.size() - marker - nth.size() - 1);
    if (number.empty() || number.size() > 7 || number.front() == '0' ||
        (number.size() == 7 && number != "1000000")) return false;
    for (char ch : number)
      if (ch < '0' || ch > '9') return false;
    if (end == selector.npos) return true;
    selector.remove_prefix(end + separator.size());
  }
  return false;
}

// Accept existing ID/class saves plus canonical exact structural locators.
// Never allow declarations, arbitrary CSS, commas or arbitrary pseudo-classes.
constexpr bool IsSafePickedSelector(std::string_view selector) {
  if (selector.empty() || selector.size() > kMaxPickedSelectorBytes) return false;
  if (selector.starts_with(":root") || selector.find(" > ") != selector.npos)
    return IsPickerPath(selector);
  if (selector.starts_with('#')) return IsElementRuleIdentifier(selector.substr(1));
  const auto dot = selector.find('.');
  return dot != selector.npos && IsPickerTag(selector.substr(0, dot)) &&
         IsElementRuleIdentifier(selector.substr(dot + 1));
}

'''


def replace_between(s, start, end, new):
    if s.count(start) != 1 or s.count(end) != 1:
        raise ValueError('unexpected picker source')
    return s[:s.index(start)] + new + s[s.index(end, s.index(start)):]


def transform(path, data):
    s = data.decode()
    if path == PICKER:
        s = replace_between(s, '  // Existing RawS safe-selection contract', '  const identifier = ',
                            '  // Explicit manual picking is independent of automatic cosmetics.\n')
        s = once(s, '  const maxPreviewMatches = 20;', '  const maxSelectorBytes = 4096;')
        s = replace_between(s, '  const selectorOf = element => {', '  const candidateAt = node => {', LOCATOR)
        s = once(s, '  let picked = null, initialTap = null, waitForChange = null;',
                 '  let picked = null, lastHit = null, initialTap = null, waitForChange = null;')
        s = once(s, '    picked = candidateAt(selected);', '''    // First tap is exact. A second tap on the same hit deliberately moves
    // the preview to its parent; the separate Block button still confirms it.
    const target = selected && selected === lastHit && picked?.node?.parentElement
        ? picked.node.parentElement : selected;
    lastHit = selected;
    picked = candidateAt(target);''')
    elif path == POLICY:
        s = replace_between(s, '// Picker output is a single stable ID',
                            'inline std::string BuildPickedSelectorStyles(', GRAMMAR)
    elif path == RENDERER:
        s = once(s, 'selector->size() > 96', 'selector->size() > 4096')
        s = once(s, 'selector->size() <= 96', 'selector->size() <= 4096')
        s = once(s, 'frame->GetEmbeddingToken() != token || css.size() > 4096) return;',
                 '// At most 32 validated 4096-byte paths plus fixed CSS declarations.\n'
                 '      frame->GetEmbeddingToken() != token || css.size() > 132096) return;')
    else:
        raise ValueError('unknown manual ad picker source: ' + path)
    return s.encode()
