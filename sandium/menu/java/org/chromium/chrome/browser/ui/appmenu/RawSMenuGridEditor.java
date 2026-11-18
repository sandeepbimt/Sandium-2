package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.widget.ImageView;
import android.widget.ScrollView;
import android.view.View;
import org.chromium.ui.modelutil.PropertyKey;
import org.chromium.ui.modelutil.PropertyModel;
import org.chromium.ui.modelutil.PropertyObservable.PropertyObserver;
import androidx.appcompat.app.AlertDialog;
import org.chromium.base.task.PostTask;
import org.chromium.base.task.TaskTraits;
import org.chromium.chrome.browser.ui.appmenu.internal.R;
import org.chromium.ui.modelutil.MVCListAdapter.ListItem;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Native dialog owner for frozen grid editing. Saves one complete durable layout, never per tap. */
final class RawSMenuGridEditor {
    static AlertDialog show(Context context,Map<String,ListItem> catalog,RawSMenuStore store) {
        RawSMenuModel<ListItem> state=new RawSMenuModel<>(store.read());state.bind(catalog);
        if(!state.writable())return null;
        List<String> order=new ArrayList<>();Map<String,Boolean> visible=new LinkedHashMap<>();
        for(String key:state.orderedKeys())if(catalog.containsKey(key)){order.add(key);visible.put(key,state.isVisible(key));}
        RawSMenuEditorView view=new RawSMenuEditorView(context,order,visible,new ArrayList<>(catalog.keySet()),
                new RawSMenuEditorView.Labels(){
                    public CharSequence title(String key){return catalog.get(key).model.get(AppMenuItemProperties.TITLE);}
                    public void icon(String key,ImageView icon){
                        icon.setId(R.id.menu_item_icon);
                        PropertyModel model=catalog.get(key).model;
                        PropertyObserver<PropertyKey> observer=(source,changed)->{
                            if(changed==AppMenuItemProperties.ICON || changed==AppMenuItemProperties.ICON_COLOR_RES
                                    || changed==AppMenuItemProperties.ICON_NO_TINT || changed==AppMenuItemProperties.ICON_SHOW_BADGE)
                                AppMenuItemViewBinder.bindStandardItem(model,icon,AppMenuItemProperties.ICON);
                        };
                        icon.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener(){
                            public void onViewAttachedToWindow(View v){model.addObserver(observer);AppMenuItemViewBinder.bindStandardItem(model,icon,AppMenuItemProperties.ICON);}
                            public void onViewDetachedFromWindow(View v){model.removeObserver(observer);}
                        });
                        AppMenuItemViewBinder.bindStandardItem(model,icon,AppMenuItemProperties.ICON_SUPPLIER);
                        AppMenuItemViewBinder.bindStandardItem(model,icon,AppMenuItemProperties.ICON);
                    }
                    public CharSequence quick(){return context.getString(R.string.raws_menu_drag);}
                    public CharSequence available(){return context.getString(R.string.raws_menu_available);}
                    public CharSequence previous(){return context.getString(R.string.raws_menu_previous);}
                    public CharSequence next(){return context.getString(R.string.raws_menu_next);}
                    public CharSequence earlier(){return context.getString(R.string.raws_menu_move_up);}
                    public CharSequence later(){return context.getString(R.string.raws_menu_move_down);}
                },R.id.raws_menu_move_up_action,R.id.raws_menu_move_down_action);
        // Native overflow safety only: when all six fixed rows fit there is no scroll range.
        // At extreme accessibility sizes/short windows, preserve every action rather than clip it.
        ScrollView overflow=new ScrollView(context);overflow.setVerticalScrollBarEnabled(false);
        overflow.setHorizontalScrollBarEnabled(false);overflow.addView(view);
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle(R.string.raws_customize_menu)
                .setView(overflow).setNegativeButton(android.R.string.cancel,(ignored,which)->{})
                .setNeutralButton(R.string.raws_menu_reset,null)
                .setPositiveButton(R.string.raws_menu_done,null).create();
        dialog.setOnShowListener(ignored->{
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->view.reset());
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
                if(!dialog.isShowing())return;
                RawSMenuModel<ListItem>.Editor draft=state.edit();
                if(view.resetRequested())draft.resetToDefaults();
                draft.reorderAvailable(view.order());for(String key:view.order())draft.setVisible(key,view.visible(key));
                dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);
                view.setEditingEnabled(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setEnabled(false);
                PostTask.postTask(TaskTraits.USER_VISIBLE_MAY_BLOCK,()->{
                    boolean saved=draft.save(store);
                    new Handler(Looper.getMainLooper()).post(()->{
                        if(!dialog.isShowing())return;
                        if(saved)dialog.dismiss();else{
                            dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);
                            view.setEditingEnabled(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
                            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setEnabled(true);
                            dialog.setTitle(R.string.raws_menu_save_failed);
                        }
                    });
                });
            });
        });
        dialog.show();return dialog;
    }
}
