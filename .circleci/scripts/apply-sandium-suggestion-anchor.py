#!/usr/bin/env python3
"""Pinned short suggestion group placement. Native handlers and ranking unchanged."""
from pathlib import Path
import subprocess
import sys
PIN = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
CHANGES = [('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdownEmbedder.java',
  '    boolean isPhoneStyleWindow();',
  '    // SANDIUM_SUGGESTION_EDIT_00\n'
  '    boolean isPhoneStyleWindow();\n'
  '\n'
  '    /** Whether ranked suggestions should sit next to a bottom phone omnibox. */\n'
  '    default boolean shouldAnchorSuggestionsToBottom() { return false; }'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/OmniboxSuggestionsDropdownEmbedderImpl.java',
  '    public boolean isPhoneStyleWindow() {',
  '    // SANDIUM_SUGGESTION_EDIT_01\n'
  '    public boolean shouldAnchorSuggestionsToBottom() {\n'
  '        return isPhoneStyleWindow()\n'
  '                && mControlsPositionSupplier.get() == ControlsPosition.BOTTOM;\n'
  '    }\n'
  '\n'
  '    @Override\n'
  '    public boolean isPhoneStyleWindow() {'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsContainer.java',
  '        mOmniboxAlignment = omniboxAlignment;',
  '    // SANDIUM_SUGGESTION_EDIT_02\n'
  '        mOmniboxAlignment = omniboxAlignment;\n'
  '        mDropdown.setAnchorSuggestionsToBottom(mEmbedder != null\n'
  '                && mEmbedder.shouldAnchorSuggestionsToBottom());'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsContainer.java',
  '            mOmniboxAlignment = mEmbedder.addAlignmentObserver(mOmniboxAlignmentObserver);',
  '    // SANDIUM_SUGGESTION_EDIT_03\n'
  '            mOmniboxAlignment = mEmbedder.addAlignmentObserver(mOmniboxAlignmentObserver);\n'
  '            mDropdown.setAnchorSuggestionsToBottom(\n'
  '                    mEmbedder.shouldAnchorSuggestionsToBottom());'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java',
  '    public void setVerticalPadding(@Px int topPadding, @Px int bottomPadding) {',
  '    // SANDIUM_SUGGESTION_EDIT_04\n'
  '    // SANDIUM_BOTTOM_RANKED_SUGGESTIONS_V2: rank 0 nearest the bottom omnibox.\n'
  '    void setAnchorSuggestionsToBottom(boolean enabled) {\n'
  '        if (mLayoutScrollListener.getReverseLayout() == enabled) return;\n'
  '        mLayoutScrollListener.setReverseLayout(enabled);\n'
  '        mLayoutScrollListener.scrollToPositionWithOffset(0, 0);\n'
  '        mLayoutScrollListener.resetScrollState();\n'
  '        requestLayout();\n'
  '    }\n'
  '\n'
  '    public void setVerticalPadding(@Px int topPadding, @Px int bottomPadding) {'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java',
  '            return updateKeyboardVisibilityAndScroll(resultingDeltaY, requestedDeltaY);',
  '    // SANDIUM_SUGGESTION_EDIT_05\n'
  '            // Native keyboard state tracks movement away from ranked item zero,\n'
  '            // which is visually at the bottom when layout is reversed.\n'
  '            if (getReverseLayout()) {\n'
  '                return -updateKeyboardVisibilityAndScroll(-resultingDeltaY, -requestedDeltaY);\n'
  '            }\n'
  '            return updateKeyboardVisibilityAndScroll(resultingDeltaY, requestedDeltaY);'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java',
  '        boolean isGoDownKey = KeyNavigationUtil.isGoDown(event);\n'
  '        boolean isGoUpKey = KeyNavigationUtil.isGoUp(event);',
  '    // SANDIUM_SUGGESTION_EDIT_06\n'
  '        boolean isGoDownKey = mLayoutScrollListener.getReverseLayout()\n'
  '                ? KeyNavigationUtil.isGoUp(event) : KeyNavigationUtil.isGoDown(event);\n'
  '        boolean isGoUpKey = mLayoutScrollListener.getReverseLayout()\n'
  '                ? KeyNavigationUtil.isGoDown(event) : KeyNavigationUtil.isGoUp(event);'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java',
  '    public void setVerticalPadding(@Px int topPadding, @Px int bottomPadding) {',
  '    // SANDIUM_SUGGESTION_EDIT_07\n'
  '    static boolean isBottomRanked(RecyclerView parent) {\n'
  '        return parent.getLayoutManager() instanceof LinearLayoutManager manager\n'
  '                && manager.getReverseLayout();\n'
  '    }\n'
  '\n'
  '    private void updateSandiumRounding(View child) {\n'
  '        if (child instanceof '
  'org.chromium.chrome.browser.omnibox.suggestions.base.BaseSuggestionView<?> suggestion) {\n'
  '            suggestion.setSandiumReverseRounding(mLayoutScrollListener.getReverseLayout());\n'
  '        }\n'
  '    }\n'
  '\n'
  '    public void setVerticalPadding(@Px int topPadding, @Px int bottomPadding) {'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java',
  '        mLayoutScrollListener.setReverseLayout(enabled);',
  '    // SANDIUM_SUGGESTION_EDIT_08\n'
  '        mLayoutScrollListener.setReverseLayout(enabled);\n'
  '        for (int i = 0; i < getChildCount(); i++) updateSandiumRounding(getChildAt(i));\n'
  '        invalidateItemDecorations();'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java',
  '    public void onChildAttachedToWindow(View child) {',
  '    // SANDIUM_SUGGESTION_EDIT_09\n'
  '    public void onChildAttachedToWindow(View child) {\n'
  '        updateSandiumRounding(child);'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java',
  '    public void onChildDetachedFromWindow(View child) {',
  '    // SANDIUM_SUGGESTION_EDIT_10\n'
  '    public void onChildDetachedFromWindow(View child) {\n'
  '        if (child instanceof '
  'org.chromium.chrome.browser.omnibox.suggestions.base.BaseSuggestionView<?> suggestion) {\n'
  '            suggestion.setSandiumReverseRounding(false);\n'
  '        }'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/base/BaseSuggestionView.java',
  '    private int mLastTouchMetaState;',
  '    // SANDIUM_SUGGESTION_EDIT_11\n'
  '    private int mLastTouchMetaState;\n'
  '    private boolean mSandiumReverseRounding;\n'
  '    private boolean mSandiumLogicalRoundTop;\n'
  '    private boolean mSandiumLogicalRoundBottom;\n'
  '\n'
  '    @Override\n'
  '    public void setRoundingEdges(boolean top, boolean bottom) {\n'
  '        mSandiumLogicalRoundTop = top;\n'
  '        mSandiumLogicalRoundBottom = bottom;\n'
  '        super.setRoundingEdges(mSandiumReverseRounding ? bottom : top,\n'
  '                mSandiumReverseRounding ? top : bottom);\n'
  '    }\n'
  '\n'
  '    public void setSandiumReverseRounding(boolean reverse) {\n'
  '        if (mSandiumReverseRounding == reverse) return;\n'
  '        mSandiumReverseRounding = reverse;\n'
  '        setRoundingEdges(mSandiumLogicalRoundTop, mSandiumLogicalRoundBottom);\n'
  '    }'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/HeaderDecoration.java',
  '            outRect.top = mHeaderHeight;',
  '    // SANDIUM_SUGGESTION_EDIT_12\n'
  '            if (OmniboxSuggestionsDropdown.isBottomRanked(parent)) outRect.bottom = '
  'mHeaderHeight;\n'
  '            else outRect.top = mHeaderHeight;'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/HeaderDecoration.java',
  '            float y =\n'
  '                    (child.getTop() + child.getTranslationY())\n'
  '                            - (mHeaderHeight / 2f)\n'
  '                            - ((fm.bottom + fm.top) / 2f);',
  '    // SANDIUM_SUGGESTION_EDIT_13\n'
  '            RecyclerView.LayoutParams lp = (RecyclerView.LayoutParams) '
  'child.getLayoutParams();\n'
  '            float edge = OmniboxSuggestionsDropdown.isBottomRanked(parent)\n'
  '                    ? child.getBottom() + lp.bottomMargin + mHeaderHeight / 2f\n'
  '                    : child.getTop() - lp.topMargin - mHeaderHeight / 2f;\n'
  '            float y = edge + child.getTranslationY() - ((fm.bottom + fm.top) / 2f);'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/GroupSeparatorDecoration.java',
  '            outRect.top = mSeparatorHeight;',
  '    // SANDIUM_SUGGESTION_EDIT_14\n'
  '            if (OmniboxSuggestionsDropdown.isBottomRanked(parent)) outRect.bottom = '
  'mSeparatorHeight;\n'
  '            else outRect.top = mSeparatorHeight;'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/GroupSeparatorDecoration.java',
  '                    int centerY = child.getTop() - lp.topMargin - mSeparatorHeight / 2;',
  '    // SANDIUM_SUGGESTION_EDIT_15\n'
  '                    float centerY = (OmniboxSuggestionsDropdown.isBottomRanked(parent)\n'
  '                            ? child.getBottom() + lp.bottomMargin + mSeparatorHeight / 2f\n'
  '                            : child.getTop() - lp.topMargin - mSeparatorHeight / 2f)\n'
  '                            + child.getTranslationY();'),
 ('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/SuggestionHorizontalDivider.java',
  '            float bottom = child.getY() + child.getHeight();',
  '    // SANDIUM_SUGGESTION_EDIT_16\n'
  '            float bottom = OmniboxSuggestionsDropdown.isBottomRanked(parent)\n'
  '                    ? child.getY() + mHeight : child.getY() + child.getHeight();')]

def transform(s, old, new):
    marker = new.splitlines()[0].strip()
    if s.count(marker) == 1: return s
    if marker in s: raise RuntimeError("duplicate suggestion marker")
    if s.count(old)!=1: raise RuntimeError("suggestion anchor mismatch")
    return s.replace(old,new,1)

def plan(root):
    out={}
    for rel,old,new in CHANGES:
        p=root/rel
        out[p]=transform(out.get(p,p.read_text()),old,new)
    return out

if __name__=="__main__":
    root=Path(sys.argv[1])
    if subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()!=PIN:
        raise RuntimeError("suggestion anchor pin mismatch")
    for p,s in plan(root).items():
        if "--verify-only" in sys.argv:
            if p.read_text() != s: raise RuntimeError("suggestion overlay missing")
        else: p.write_text(s)
