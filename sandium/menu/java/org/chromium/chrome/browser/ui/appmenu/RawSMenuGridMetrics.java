package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.graphics.Paint;
import android.util.TypedValue;
import android.widget.TextView;

/** One font-aware sizing contract shared by native sizing provider and actual grid rows. */
final class RawSMenuGridMetrics {
    static void styleLabel(TextView label) {
        label.setTextAppearance(android.R.style.TextAppearance_DeviceDefault_Widget_Button);
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP,12);
    }
    static int rowHeight(Context context) {
        TextView sample=new TextView(context);styleLabel(sample);
        Paint.FontMetricsInt metrics=sample.getPaint().getFontMetricsInt();
        return rowHeight(Math.round(72*context.getResources().getDisplayMetrics().density),
                Math.round(32*context.getResources().getDisplayMetrics().density),metrics.bottom-metrics.top);
    }
    static int rowHeight(int minimum,int iconAndGap,int lineHeight) {
        if(minimum<0 || iconAndGap<0 || lineHeight<0)throw new IllegalArgumentException();
        return Math.max(minimum,iconAndGap+2*lineHeight);
    }
    static int footerHeight(Context context) {
        return Math.max(Math.round(48*context.getResources().getDisplayMetrics().density),
                rowHeight(context)-Math.round(24*context.getResources().getDisplayMetrics().density));
    }
    static int heightForLimit(Context context,RawSMenuPager<?> pager,int limit) {
        return pager.rowsForLimit(limit)*rowHeight(context)+(pager.pagesForLimit(limit)>1?footerHeight(context):0);
    }
    static int height(Context context,RawSMenuPager<?> pager) {
        return pager.rows()*rowHeight(context)+(pager.showPageIndicator()
                ? footerHeight(context):0);
    }
}
