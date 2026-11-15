// Copyright 2026 Sandium Authors. BSD-style license.
#ifndef THIRD_PARTY_BLINK_RENDERER_CORE_DOM_SANDIUM_ELEMENT_COLORS_H_
#define THIRD_PARTY_BLINK_RENDERER_CORE_DOM_SANDIUM_ELEMENT_COLORS_H_

#include <cstdint>
#include <optional>
#include "third_party/blink/renderer/core/core_export.h"
#include "third_party/blink/renderer/platform/heap/collection_support/heap_vector.h"
#include "third_party/blink/renderer/platform/heap/garbage_collected.h"
#include "third_party/blink/renderer/platform/supplementable.h"

namespace blink {
class ComputedStyleBuilder;
class Document;
class Element;

// Manual top-document overrides. Not a selector engine or persistence layer.
// Only a trusted browser-owned session may call Preview/Commit/Cancel.
class CORE_EXPORT SandiumElementColors final
    : public GarbageCollected<SandiumElementColors>,
      public Supplement<Document> {
 public:
  static const char kSupplementName[];
  static SandiumElementColors& From(Document&);
  static SandiumElementColors* GetIfExists(Document&);
  explicit SandiumElementColors(Document&);
  bool Preview(Element&, int property, uint32_t rgb);
  bool Commit(Element&, int property, uint32_t rgb);
  void CancelPreview();
  void Clear();
  void Remove(Element&);
  void Apply(Element&, ComputedStyleBuilder&);
  void Trace(Visitor*) const override;

 private:
  class Entry final : public GarbageCollected<Entry> {
   public:
    explicit Entry(Element* element) : element(element) {}
    void Trace(Visitor* visitor) const { visitor->Trace(element); }
    WeakMember<Element> element;
    std::optional<uint32_t> foreground;
    std::optional<uint32_t> background;
  };
  bool Eligible(const Element&) const;
  static bool Valid(int property, uint32_t rgb);
  static void Invalidate(Element&);
  static void ApplyEntry(const Entry&, ComputedStyleBuilder&);
  void Prune();
  HeapVector<Member<Entry>> saved_;
  Member<Entry> preview_;
};
}  // namespace blink
#endif
