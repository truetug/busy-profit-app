import { generateXpm2, type render } from "@busy-app/busy-lib";
import { historicalSalesIcon } from "./sales-chart.ts";
import { calendarDate } from "../view-api.ts";
let cachedKey="",cachedBitmap="";

/** Draw compact API values directly, retaining a stable bitmap during rotation. */
export function apiChart(values: (number | null)[], start: string, windowStart: number, selected: number, hours = false, starts: string[] = []): ReturnType<typeof render> {
  const slots = hours ? values.length : 36;
  const visible = values.slice(windowStart, windowStart+slots);
  const numbers = visible.map((v) => v ?? 0);
  const key=numbers.join(",");
  if(key!==cachedKey){cachedKey=key;cachedBitmap=historicalSalesIcon(numbers,72,9);}
  const index = selected-windowStart;
  const value = values[selected];
  const date = calendarDate(start);
  date.setDate(date.getDate()+selected);
  const label = hours ? (starts[selected]?.slice(11,16) ?? "") : String(date.getDate()).padStart(2,"0")+"."+String(date.getMonth()+1).padStart(2,"0");
  const ordinal = Math.round((Date.UTC(date.getFullYear(),date.getMonth(),date.getDate())-Date.UTC(2026,6,14))/86400000)+1;
  const barHeight = Math.max(1, Math.round((value ?? 0)/Math.max(1,...numbers)*9));
  const x0 = Math.floor(index*72/slots);
  const x1 = Math.floor((index+1)*72/slots);
  const elements: ReturnType<typeof render> = [
    {type:"text",id:"view-label",x:0,y:0,text:label+"  "+(value ?? "-"),font:"small",color:"#FFFFFFFF"},
    {type:"text",id:"view-ordinal",x:71,y:0,align:"top_right",text:hours?"H":String(ordinal),font:"small",color:"#A0A0A0FF"},
    {type:"xpmbitmap",id:"view-bars",x:0,y:7,data:cachedBitmap,opacity:100,z_index:0},
    {type:"xpmbitmap",id:"view-selection",x:x0,y:16-barHeight,
      data:generateXpm2({palette:{w:"#FFFFFF"},grid:Array(barHeight).fill("w".repeat(x1-x0))}),opacity:100,z_index:100},
  ];
  if (!hours) {
    const row = visible.map((_,i) => {
      const day = calendarDate(start); day.setDate(day.getDate()+windowStart+i);
      return day.getDay()===0 || day.getDay()===6 ? "ww":"..";
    }).join("");
    elements.push({type:"xpmbitmap",id:"view-weekends",x:0,y:15,data:generateXpm2({palette:{".":"None",w:"#808080"},grid:[row]}),opacity:100,z_index:6});
  }
  return elements;
}
