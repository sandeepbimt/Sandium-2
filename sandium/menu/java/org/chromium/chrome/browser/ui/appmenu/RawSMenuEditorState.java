package org.chromium.chrome.browser.ui.appmenu;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Original editor transaction draft; no storage writes until explicit owner Save. */
final class RawSMenuEditorState {
    private final List<String> keys=new ArrayList<>(),defaults=new ArrayList<>();
    private final Map<String,Boolean> visible=new LinkedHashMap<>();
    private boolean reset;
    RawSMenuEditorState(List<String> order,Map<String,Boolean> visibility,List<String> defaults) {
        if(order.size()!=new java.util.HashSet<>(order).size() || !new java.util.HashSet<>(order).equals(visibility.keySet())
                || !new java.util.HashSet<>(order).equals(new java.util.HashSet<>(defaults)))throw new IllegalArgumentException();
        keys.addAll(order);visible.putAll(visibility);this.defaults.addAll(defaults);
    }
    List<String> order(){return new ArrayList<>(keys);}
    boolean visible(String key){return Boolean.TRUE.equals(visible.get(key));}
    boolean resetRequested(){return reset;}
    void reset(){keys.clear();keys.addAll(defaults);for(String k:keys)visible.put(k,true);reset=true;}
    List<String> selected(boolean quick){List<String> result=new ArrayList<>();for(String k:keys)if(visible(k)==quick)result.add(k);return result;}
    boolean toggle(String key){if(!visible.containsKey(key))return false;boolean next=!visible(key);visible.put(key,next);if(next){keys.remove(key);keys.add(key);}return true;}
    boolean move(String key,int direction){
        if(direction!=-1&&direction!=1)return false;List<String> selected=selected(visible(key));int index=selected.indexOf(key),next=index+direction;
        if(index<0||next<0||next>=selected.size())return false;
        int destination=keys.indexOf(selected.get(next));keys.remove(key);keys.add(destination,key);return true;
    }
    boolean drop(String key,String target){if(key.equals(target)||!keys.contains(key)||!keys.contains(target))return false;visible.put(key,visible(target));keys.remove(key);keys.add(keys.indexOf(target),key);return true;}
}
