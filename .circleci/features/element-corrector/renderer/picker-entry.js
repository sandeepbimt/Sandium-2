// Appended inside the isolated-world bundle, after corrector core functions.
if (globalThis.__sandiumCancelPicker) globalThis.__sandiumCancelPicker();
const overlay = document.createElement('div');
overlay.style.cssText='position:fixed!important;inset:0!important;z-index:2147483647!important;background:transparent!important;pointer-events:auto!important;';
const shadow = overlay.attachShadow({mode:'closed'});
const panel = document.createElement('div');
panel.style.cssText='position:fixed;inset:0;pointer-events:auto;background:rgba(0,0,0,.08);';
shadow.appendChild(panel);
const cleanup=()=>{overlay.remove();if(globalThis.__sandiumCancelPicker===cleanup)delete globalThis.__sandiumCancelPicker;};
globalThis.__sandiumCancelPicker=cleanup;
panel.addEventListener('click',event=>{
  if(!event.isTrusted)return;
  event.preventDefault();event.stopImmediatePropagation();
  overlay.style.setProperty('display','none','important');
  const target=document.elementFromPoint(event.clientX,event.clientY);
  overlay.style.setProperty('display','block','important');
  if(!target)return;
  try {
    const path=captureTarget(target,document);
    let descriptor;
    try { descriptor=captureDescriptor(target,document); }
    catch { const own=path.at(-1); descriptor={tag:own.tag,id:'',role:own.role,
      ancestors:path.slice(0,-1).map(part=>({tag:part.tag,id:part.id}))}; }
    cf_worker.sandiumSelect(target,JSON.stringify(descriptor));
    cleanup();
  } catch { /* Unsupported target: keep picker active for another choice. */ }
},true);
document.documentElement.appendChild(overlay);
