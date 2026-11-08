'use client';
import {useEffect,useId,useState} from 'react';
import DOMPurify from 'dompurify';
export default function MermaidDiagram({code}:{code:string}){
 const id=useId().replaceAll(':',''),[svg,setSvg]=useState(''),[error,setError]=useState('');
 useEffect(()=>{let active=true;setError('');setSvg('');
  if(code.length>20000||code.includes('%%{')||code.trimStart().startsWith('---')){setError('El diagrama supera el tamaño permitido o contiene configuración incrustada.');return;}
  import('mermaid').then(async({default:mermaid})=>{
   mermaid.initialize({startOnLoad:false,securityLevel:'strict',htmlLabels:false,flowchart:{htmlLabels:false},suppressErrorRendering:true,maxTextSize:20000,maxEdges:300,theme:'base',themeVariables:{primaryColor:'#edf4e8',primaryTextColor:'#284c36',primaryBorderColor:'#7a9d72',lineColor:'#7d936f'},secure:['secure','securityLevel','startOnLoad','maxTextSize','maxEdges','suppressErrorRendering','htmlLabels']});
   const result=await mermaid.render('diagram-'+id,code);if(active)setSvg(DOMPurify.sanitize(result.svg,{USE_PROFILES:{svg:true,svgFilters:true},FORBID_TAGS:['style','script','a','image','foreignObject'],FORBID_ATTR:['style','href','xlink:href']}));
  }).catch(()=>{if(active)setError('No se pudo dibujar este diagrama. Puedes consultar su código.');});return()=>{active=false;};
 },[code,id]);
 return <figure className="mermaid-figure">{svg?<div className="rendered-diagram" role="img" aria-label="Diagrama de estudio" dangerouslySetInnerHTML={{__html:svg}}/>:<p role="status">{error||'Preparando diagrama…'}</p>}<details><summary>Ver código del diagrama</summary><pre>{code}</pre></details></figure>;
}
