import { addr, device } from "@shared/device";
import { render } from "@busy-app/busy-lib";
import manifest from "./appmeta/manifest.json";
import { fetchView, calendarDate, dateKey, type DaysView, type HoursView } from "./view-api.ts";
import { apiChart } from "./screens/api-chart.ts";
import { renderSalesScreen } from "./screens/sales.ts";
import { positionSalesDigits } from "./screens/sales-digits.ts";
import { dailySalesHeights } from "./screens/sales-chart.ts";
import { clearDisplay, changedElements, clearBeforeFrameChange, fetchWithTimeout, clampNegativeY } from "./display-api.ts";
import { createEncoderDrawScheduler } from "./encoder-draw.ts";
import { countdownIndicator } from "./countdown-indicator.ts";
import { salesNotification } from "./model/sales-notification.ts";
import { AccessKeyRequired } from "./sales-api.ts";

const APP=manifest.id, DRAW=(/^https?:/.test(addr)?addr:"http://"+addr).replace(/\/$/,"")+"/api/display/draw";
let screen:"home"|"days"|"hours"="home", key="", zone="", error="";
let stopped=false, loading=false, drawing=false, pending=false, access=false;
let recent:DaysView|undefined, hours:HoursView|undefined;
let days:(number|null)[]=[], start="", selected=0, windowStart=0, hour=0, generation=0, next=0;
let notification:number|undefined, notifyTimer:ReturnType<typeof setTimeout>|undefined;
let polling:ReturnType<typeof setInterval>|undefined, clock:ReturnType<typeof setInterval>|undefined;
let unbind:BusyUnbind|undefined, ids:string[]=[];
const drawn=new Map<string,string>();
const encoder=createEncoderDrawScheduler(()=>{void draw();});

/** Serialize device drawing while retaining unchanged elements during rotation. */
async function draw():Promise<void>{
  if(stopped)return;if(drawing){pending=true;return;}drawing=true;
  try{do{pending=false;
    let elements;
    if(screen==="home" || notification!==undefined){
      elements=positionSalesDigits(render(renderSalesScreen({screen:"home",now:new Date(),count:recent?.total,
        points:[],selectedDay:0,stale:!!error,accessRequired:access,notificationCount:notification,
        error:error||undefined,iconHeights:recent?dailySalesHeights(recent.values.slice(-8).map(v=>v??0),16):undefined})));
      if(recent && notification===undefined)elements.push(...countdownIndicator(next-Date.now()));
    }else if(!recent || (screen==="hours" && !hours)){
      elements=render(renderSalesScreen({screen:"days",now:new Date(),points:[],selectedDay:0,stale:false,historyState:error?"error":"loading"}));
    }else elements=screen==="days"?apiChart(days,start,windowStart,selected):apiChart(hours!.values,hours!.date,0,hour,true,hours!.starts);
    elements=clampNegativeY(elements);
    const nextIds=elements.flatMap(e=>e.id?[e.id]:[]);
    await clearBeforeFrameChange(ids,nextIds,async()=>{await clearDisplay(DRAW,APP);drawn.clear();ids=[];});
    if(stopped)return;
    const changed=changedElements(elements,drawn);
    if(changed.length){
      const response=await fetchWithTimeout(DRAW,{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({application_name:APP,priority:50,elements:changed})},8000);
      if(!response.ok){drawn.clear();throw new Error("Display "+response.status);}
      for(const e of changed)if(e.id)drawn.set(e.id,JSON.stringify(e));
    }ids=nextIds;
  }while(pending&&!stopped);}catch(e){console.warn("busy-profit: display",String(e));}finally{drawing=false;}
}

/** Preserve selected calendar dates when the older compact page is prepended. */
async function loadOlder(view:DaysView):Promise<void>{
  if(!view.more)return;
  try{
    const page=await fetchView<DaysView>("days?timezone="+encodeURIComponent(zone)+"&older=true&revision="+view.revision,key);
    if(stopped||recent?.revision!==view.revision)return;
    const chosen=calendarDate(start);chosen.setDate(chosen.getDate()+selected);
    const first=calendarDate(page.start);
    days=[...page.values,...view.values];start=page.start;
    selected=Math.max(0,Math.min(days.length-1,Math.round((chosen.getTime()-first.getTime())/86400000)));
    windowStart=Math.max(0,Math.min(selected,days.length-36));
    if(screen==="days")void draw();
  }catch(e){console.warn("busy-profit: older",String(e));}
}

/** Poll small recent views and report sales changes without retaining raw history. */
async function refresh():Promise<void>{
  if(loading||stopped||access)return;loading=true;next=Date.now()+60000;
  try{
    const view=await fetchView<DaysView>("days?timezone="+encodeURIComponent(zone),key);
    if(stopped)return;
    const previous=recent?.total;
    const oldDate=start?calendarDate(start):undefined;oldDate?.setDate(oldDate.getDate()+selected);
    recent=view;
    const keepHistory=screen!=="home" && days.length>36;
    if(keepHistory){
      const offset=Math.round((calendarDate(view.start).getTime()-calendarDate(start).getTime())/86400000);
      if(offset>=0)days.splice(offset,36,...view.values);
    }else{days=view.values;start=view.start;selected=days.length-1;windowStart=0;}
    error="";
    if(oldDate&&!keepHistory){
      const first=calendarDate(start);
      selected=Math.max(0,Math.min(days.length-1,Math.round((oldDate.getTime()-first.getTime())/86400000)));
    }
    const change=salesNotification(previous,view.total);
    if(change){
      notification=change.count;clearTimeout(notifyTimer);
      void device.AudioPlay({application_name:APP,path:change.sound==="applause"?"sounds/applause.snd":"sounds/cha-ching.snd"}).catch(()=>{});
      notifyTimer=setTimeout(()=>{notification=undefined;void draw();},10000);
    }
    if(!keepHistory)void loadOlder(view);
  }catch(e){access=e instanceof AccessKeyRequired;error=String(e);console.warn("busy-profit: API",error);}
  finally{loading=false;if(!stopped)void draw();}
}

/** Fetch only the selected day's hours and ignore late navigation completions. */
async function openHours():Promise<void>{
  if(screen!=="days"||!recent)return;
  const date=calendarDate(start);date.setDate(date.getDate()+selected);
  screen="hours";hours=undefined;error="";const request=++generation;void draw();
  try{
    const value=await fetchView<HoursView>("hours?timezone="+encodeURIComponent(zone)+"&date="+dateKey(date),key);
    if(stopped||request!==generation||screen!=="hours")return;
    hours=value;hour=0;
  }catch(e){if(request===generation)error=String(e);}
  if(!stopped&&request===generation)void draw();
}

/** Initialize device context before starting lightweight minute refreshes. */
export default function run():void{
  clock=setInterval(()=>{if(loading)console.info("busy-profit: waiting for API");if(screen==="home")void draw();},1000);
  unbind=listen("input",event=>{
    if(event.key==="back"&&event.action==="short"){
      if(screen==="hours"){generation++;screen="days";void draw();return;}
      stopped=true;generation++;clearInterval(polling);clearInterval(clock);clearTimeout(notifyTimer);encoder.stop();setTimeout(()=>unbind?.(),10);return;
    }
    if(event.key==="start"&&event.action==="short"){generation++;screen=screen==="home"?"days":screen==="hours"?"days":"home";void draw();return;}
    if(event.key==="ok"&&event.action==="short"){void openHours();return;}
    if(event.key!=="encoder")return;
    if(screen==="days"&&days.length){
      selected=Math.max(0,Math.min(days.length-1,selected+event.delta));
      if(selected<windowStart)windowStart=selected;
      if(selected>=windowStart+36)windowStart=selected-35;
      encoder.request();
    }else if(screen==="hours"&&hours){hour=Math.max(0,Math.min(hours.values.length-1,hour+event.delta));encoder.request();}
  });
  void(async()=>{
    try{
      const settings=await device.AppsSettingsGet({app_id:APP});
      key=typeof settings.values?.access_key==="string"?settings.values.access_key.trim():"";access=!key;
      const info=await device.TimeTimezoneGet();
      const aliases:Record<string,string>={Moscow:"Europe/Moscow",Istanbul:"Europe/Istanbul"};
      zone=aliases[info.name]??info.name;
      await clearDisplay(DRAW,APP);if(stopped)return;
      void draw();await refresh();if(stopped)return;
      polling=setInterval(()=>{void refresh();},60000);
    }catch(e){error=String(e);console.error("busy-profit: initialization",error);void draw();}
  })();
}
