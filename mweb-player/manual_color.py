"""Exact RawS #1514 postimage edits for manual, user-picked element colors."""

OWNERS = {
    'chrome/renderer/chrome_render_frame_observer.cc':
        '20aaba181642b68583841c48a800ea343b804eb09229416638d8643e373def71',
    'third_party/blink/renderer/core/dom/sandium_element_colors.cc':
        '620a1db8a67d0d6c6c789f1e263cf9a4f946721223ec61bba6fc920d3d7000af',
}

RENDERER, BLINK = OWNERS


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f'missing or ambiguous anchor: {old[:100]!r}')
    return text.replace(old, new, 1)


def transform(path: str, data: bytes) -> bytes:
    text = data.decode('utf-8')
    if path == RENDERER:
        text = once(text, '''  // Blink's CanSandiumCorrectColor already rejects shadow trees,
  // frames, editable/interactive elements, insecure documents and forced colors.
  // A missing durable path does not preclude editing the exact in-document node.
  if (!candidate && ElementTag(node).empty()) return false;
''', '''  // Blink checks document and shadow boundaries, not the element's type.
  // Without a verified durable identity, keep this exact node for this visit.
''')
    elif path == BLINK:
        start = 'bool SandiumElementColors::Eligible(const Element& element) const {'
        end = 'bool SandiumElementColors::CanCorrect(const Element& element) const {'
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError('missing or ambiguous Blink eligibility method')
        begin = text.index(start)
        stop = text.index(end, begin)
        original = text[begin:stop]
        if ('IsEditable(element)' not in original or
                'ElementTraversal::DescendantsOf(element)' not in original):
            raise ValueError('unexpected Blink eligibility policy')
        text = once(text, original, '''bool SandiumElementColors::Eligible(const Element& element) const {
  const Document& document = element.GetDocument();
  // A browser-owned manual selection may style any hit element in the active
  // page document. Never enter a separate document or an internal shadow tree.
  return &document == GetSupplementable() && document.IsInOutermostMainFrame() &&
         document.IsActive() && document.Url().ProtocolIsInHttpFamily() &&
         element.isConnected() && !element.IsInShadowTree();
}
''')
        for include in ('dom/element_traversal.h', 'editing/editing_utilities.h'):
            text = once(text, f'#include "third_party/blink/renderer/core/{include}"\n', '')
    else:
        raise ValueError('unexpected manual color owner: ' + path)
    return text.encode('utf-8')
