export function layoutGraph(nodes:any[],edges:any[]):Record<string,{x:number;y:number}>{
 const positions=new Map(nodes.map((n,i)=>[n.id,{x:500+Math.cos(i*2.39996)*Math.sqrt(i+1)*42,y:340+Math.sin(i*2.39996)*Math.sqrt(i+1)*35}]));
 for(let step=0;step<100;step++){
  const delta=new Map(nodes.map(n=>[n.id,{x:0,y:0}]));
  for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
   const a=positions.get(nodes[i].id)!,b=positions.get(nodes[j].id)!,dx=a.x-b.x,dy=a.y-b.y,d=Math.max(20,Math.hypot(dx,dy)),force=1500/(d*d);
   delta.get(nodes[i].id)!.x+=dx/d*force;delta.get(nodes[i].id)!.y+=dy/d*force;delta.get(nodes[j].id)!.x-=dx/d*force;delta.get(nodes[j].id)!.y-=dy/d*force;
  }
  for(const e of edges){const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b)continue;const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),f=(d-130)*.015;delta.get(e.source)!.x+=dx/d*f;delta.get(e.source)!.y+=dy/d*f;delta.get(e.target)!.x-=dx/d*f;delta.get(e.target)!.y-=dy/d*f;}
  for(const n of nodes){const pos=positions.get(n.id)!,d=delta.get(n.id)!;pos.x+=Math.max(-8,Math.min(8,d.x))+(500-pos.x)*.002;pos.y+=Math.max(-8,Math.min(8,d.y))+(340-pos.y)*.002;}
 }
 if(nodes.length){
  const values=[...positions.values()],minX=Math.min(...values.map(p=>p.x)),maxX=Math.max(...values.map(p=>p.x)),minY=Math.min(...values.map(p=>p.y)),maxY=Math.max(...values.map(p=>p.y)),scale=Math.min(3,780/Math.max(120,maxX-minX),460/Math.max(120,maxY-minY));
  for(const pos of values){pos.x=500+(pos.x-(minX+maxX)/2)*scale;pos.y=340+(pos.y-(minY+maxY)/2)*scale;}
 }
 return Object.fromEntries(positions);
}
export function graphNeighbors(id:string,edges:any[],depth:number){
 const ids=new Set([id]);for(let n=0;n<depth;n++){const current=new Set(ids);for(const e of edges){if(current.has(e.source))ids.add(e.target);if(current.has(e.target))ids.add(e.source);}}return ids;
}
