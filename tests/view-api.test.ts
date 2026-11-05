import assert from "node:assert/strict";
import test from "node:test";
import { fetchView, type DaysView } from "../src/view-api.ts";
import { apiChart } from "../src/screens/api-chart.ts";

test("compact API retains zero and missing values without hourly observations",async()=>{
  const page={revision:"42",timezone:"UTC",start:"2026-10-01",values:[0,null,7],total:5000,more:true};
  const result=await fetchView<DaysView>("days?timezone=UTC","private",async(_url,options)=>{
    assert.equal((options?.headers as Record<string,string>).Authorization,"Bearer private");
    return new Response(JSON.stringify(page));
  });
  assert.deepEqual(result,page);
});

test("encoder selection changes only labels and the marker within a window",()=>{
  const values=Array.from({length:110},(_,i)=>i%20);
  const first=apiChart(values,"2026-07-14",74,100);
  const second=apiChart(values,"2026-07-14",74,99);
  assert.equal(first.find(e=>e.id==="view-bars")?.data,second.find(e=>e.id==="view-bars")?.data);
  assert.notEqual(first.find(e=>e.id==="view-selection")?.x,second.find(e=>e.id==="view-selection")?.x);
  const moved=apiChart(values,"2026-07-14",73,73);
  assert.equal(moved.find(e=>e.id==="view-selection")?.x,0);
});

test("hour screen fills the width with 24 three-pixel columns",()=>{
  const frame=apiChart(Array(24).fill(2),"2026-11-05",0,23,true,Array(24).fill("2026-11-05T23:00:00+00:00"));
  const selected=frame.find(e=>e.id==="view-selection");
  assert.equal(selected?.x,69);
  assert.match(selected?.data??"",/3 9 /);
});
