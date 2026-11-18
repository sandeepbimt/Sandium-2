package org.chromium.chrome.browser.ui.appmenu;

import android.content.ClipData;
import android.content.Context;
import android.view.DragEvent;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.os.Bundle;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Frozen two-quick/four-available-row editor inside the native dialog, never a new window.
 * Draft is local until the owner performs its durable Save transaction. No scrolling container.
 */
final class RawSMenuEditorView extends LinearLayout {
    interface Labels {
        CharSequence title(String key);
        void icon(String key,ImageView view);
        CharSequence quick();CharSequence available();CharSequence previous();CharSequence next();
        CharSequence earlier();CharSequence later();
    }
    private final RawSMenuEditorState state;
    private final Labels labels;
    private final int earlierId,laterId;
    private int quickPage,availablePage;
    private boolean editing=true;
    private final Object dragOwner=new Object();
    private static final class DragToken {final Object owner;final String key;DragToken(Object o,String k){owner=o;key=k;}}
    RawSMenuEditorView(Context c,List<String> order,Map<String,Boolean> visible,List<String> defaults,
            Labels labels,int earlierId,int laterId) {
        super(c);setOrientation(VERTICAL);state=new RawSMenuEditorState(order,visible,defaults);
        this.labels=labels;this.earlierId=earlierId;this.laterId=laterId;render();
    }
    List<String> order(){return state.order();}
    boolean visible(String key){return state.visible(key);}
    boolean resetRequested(){return state.resetRequested();}
    void setEditingEnabled(boolean enabled){editing=enabled;render();}
    void reset(){if(!editing)return;state.reset();quickPage=availablePage=0;render();}
    private int dp(int x){return Math.round(x*getResources().getDisplayMetrics().density);}
    private int columns(){return getResources().getConfiguration().fontScale>1.3f?2:4;}
    private List<String> selected(boolean quick){return state.selected(quick);}
    private void toggle(String key){if(editing&&state.toggle(key))render();}
    private boolean move(String key,int direction){if(!editing||!state.move(key,direction))return false;render();return true;}
    private void drop(String key,String target){if(editing&&state.drop(key,target))render();}
    private TextView text(CharSequence value){TextView v=new TextView(getContext());RawSMenuGridMetrics.styleLabel(v);v.setText(value);v.setGravity(Gravity.CENTER);v.setMaxLines(2);return v;}
    private void render(){removeAllViews();section(true,2,labels.quick());section(false,4,labels.available());}
    private void section(boolean quick,int rows,CharSequence title){
        TextView heading=text(title);heading.setMinHeight(dp(24));
        addView(heading,new LayoutParams(LayoutParams.MATCH_PARENT,LayoutParams.WRAP_CONTENT));
        List<String> section=selected(quick);int capacity=rows*columns(),pages=Math.max(1,(section.size()+capacity-1)/capacity);
        int page=Math.max(0,Math.min(quick?quickPage:availablePage,pages-1));if(quick)quickPage=page;else availablePage=page;
        for(int row=0;row<rows;row++){
            LinearLayout line=new LinearLayout(getContext());line.setOrientation(HORIZONTAL);
            addView(line,new LayoutParams(LayoutParams.MATCH_PARENT,RawSMenuGridMetrics.rowHeight(getContext())));
            for(int col=0;col<columns();col++){
                int index=page*capacity+row*columns()+col;
                if(index>=section.size()){line.addView(new View(getContext()),new LayoutParams(0,LayoutParams.MATCH_PARENT,1));continue;}
                String key=section.get(index);LinearLayout tile=new LinearLayout(getContext());tile.setOrientation(VERTICAL);tile.setGravity(Gravity.CENTER);
                tile.setContentDescription(labels.title(key));tile.setFocusable(true);tile.setEnabled(editing);
                tile.setAlpha(editing?1f:0.38f);
                ImageView icon=new ImageView(getContext());icon.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);labels.icon(key,icon);
                tile.addView(icon,new LayoutParams(dp(24),dp(24)));
                TextView caption=text(labels.title(key));caption.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
                tile.addView(caption,new LayoutParams(LayoutParams.MATCH_PARENT,LayoutParams.WRAP_CONTENT));
                tile.setOnClickListener(v->toggle(key));
                tile.setOnLongClickListener(v->editing&&v.startDragAndDrop(ClipData.newPlainText("menu",key),new View.DragShadowBuilder(v),new DragToken(dragOwner,key),0));
                tile.setOnDragListener((v,event)->{
                    Object local=event.getLocalState();if(!editing||!(local instanceof DragToken)||((DragToken)local).owner!=dragOwner)return false;
                    if(event.getAction()==DragEvent.ACTION_DROP)drop(((DragToken)local).key,key);
                    return true;
                });
                tile.setOnKeyListener((v,code,event)->event.getAction()==KeyEvent.ACTION_DOWN&&event.isCtrlPressed()
                    && ((code==KeyEvent.KEYCODE_DPAD_UP&&move(key,-1))||(code==KeyEvent.KEYCODE_DPAD_DOWN&&move(key,1))));
                tile.setAccessibilityDelegate(new View.AccessibilityDelegate(){
                    @Override public void onInitializeAccessibilityNodeInfo(View host,AccessibilityNodeInfo info){
                        super.onInitializeAccessibilityNodeInfo(host,info);info.setClassName("android.widget.Button");
                        if(editing){info.addAction(new AccessibilityNodeInfo.AccessibilityAction(earlierId,labels.earlier()));info.addAction(new AccessibilityNodeInfo.AccessibilityAction(laterId,labels.later()));}
                    }
                    @Override public boolean performAccessibilityAction(View host,int action,Bundle args){
                        if(action==earlierId)return move(key,-1);if(action==laterId)return move(key,1);
                        return super.performAccessibilityAction(host,action,args);
                    }
                });
                line.addView(tile,new LayoutParams(0,LayoutParams.MATCH_PARENT,1));
            }
        }
        if(pages>1){
            LinearLayout controls=new LinearLayout(getContext());controls.setOrientation(HORIZONTAL);
            for(int direction:new int[]{-1,1}){
                TextView button=text(direction<0?labels.previous():labels.next());button.setFocusable(true);
                button.setEnabled(editing&&(direction<0?page>0:page+1<pages));
                button.setOnClickListener(v->{if(quick)quickPage+=direction;else availablePage+=direction;render();});
                controls.addView(button,new LayoutParams(0,RawSMenuGridMetrics.footerHeight(getContext()),1));
            }
            addView(controls);
        }
    }
}
