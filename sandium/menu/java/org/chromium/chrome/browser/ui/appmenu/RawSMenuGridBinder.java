package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.view.View;
import org.chromium.ui.modelutil.PropertyKey;
import org.chromium.ui.modelutil.PropertyModel;
import org.chromium.ui.modelutil.PropertyModel.WritableObjectPropertyKey;

/** Held custom native AppMenu binder. Registration and popup ownership stay with native host. */
final class RawSMenuGridBinder {
    static final WritableObjectPropertyKey<Binding<?>> DATA = new WritableObjectPropertyKey<>();
    static final class Binding<T> {
        final RawSMenuPager<T> pager;
        final RawSMenuGridView.Presentation<T> presentation;
        final RawSMenuModel.Dispatcher<T> dispatcher;
        final Runnable sizeChanged;
        Binding(RawSMenuPager<T> pager, RawSMenuGridView.Presentation<T> presentation,
                RawSMenuModel.Dispatcher<T> dispatcher, Runnable sizeChanged) {
            this.pager = pager; this.presentation = presentation;
            this.dispatcher = dispatcher; this.sizeChanged = sizeChanged;
        }
        @SuppressWarnings("unchecked")
        void bindTo(View view) {
            ((RawSMenuGridView<T>) view).bind(pager, presentation, dispatcher, sizeChanged);
        }
    }
    static View create(Context context) { return new RawSMenuGridView<>(context); }
    static void bind(PropertyModel model, View view, PropertyKey key) {
        if (key == DATA) model.get(DATA).bindTo(view);
    }
    static int pixelHeight(Context context, PropertyModel model) {
        RawSMenuPager<?> pager = model.get(DATA).pager;
        return RawSMenuGridMetrics.height(context,pager);
    }
}
