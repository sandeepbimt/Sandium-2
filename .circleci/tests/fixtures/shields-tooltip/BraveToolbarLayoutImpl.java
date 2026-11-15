    private void showTooltip(String tooltipPref, int tabId) {
        int gravity =
                BottomToolbarConfiguration.isToolbarBottomAnchored() ? Gravity.TOP : Gravity.BOTTOM;
        mShieldsPopupWindowTooltip =
                new PopupWindowTooltip.Builder(getContext())
                        .anchorView(mBraveShieldsButton)
                        .arrowColor(
                                ContextCompat.getColor(getContext(), R.color.primitive_primary_35))
                        .gravity(gravity)
                        .dismissOnOutsideTouch(true)
                        .dismissOnInsideTouch(false)
                        .backgroundDimDisabled(false)
                        .dimAmount(0.2f)
                        .padding(0f)
                        .parentPaddingHorizontal(dpToPx(getContext(), 10))
                        .modal(true)
                        .contentView(R.layout.brave_shields_tooltip_layout)
                        .build();

        int adsTrackersCount =
                mUnifiedPanelHandler.getTrackersBlockedCount(tabId)
                        + mUnifiedPanelHandler.getAdsBlockedCount(tabId);

        TextView tvBlocked = mShieldsPopupWindowTooltip.findViewById(R.id.tv_blocked);
        tvBlocked.setText(
                String.format(
                        getContext().getResources().getString(R.string.shield_tracker_blocked),
                        String.valueOf(adsTrackersCount)));

        if (mBraveShieldsButton != null && mBraveShieldsButton.isShown()) {
            mShieldsPopupWindowTooltip.show();
            BraveShieldsUtils.setShieldsTooltipShown(tooltipPref, true);
            BraveShieldsUtils.isTooltipShown = true;
        }
    }
