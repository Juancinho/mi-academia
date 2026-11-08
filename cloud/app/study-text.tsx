import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import {safeStudyUrl} from '../lib/study-urls';
import 'katex/dist/katex.min.css';
import MermaidDiagram from './mermaid-diagram';
export default function StudyText({children}:{children:string}){
 return <div className="study-markdown"><Markdown skipHtml remarkPlugins={[remarkGfm,remarkMath]} rehypePlugins={[[rehypeKatex,{trust:false,maxExpand:1000,maxSize:20,throwOnError:false}]]} urlTransform={safeStudyUrl} components={{
  a:({href,children})=>href?<a href={href} target="_blank" rel="noreferrer">{children}</a>:<span>{children}</span>,
  img:({alt})=><span className="caption">[Imagen: {alt||'sin descripción'}]</span>,
  pre:({children})=><div className="study-code-block">{children}</div>,
  code:({className,children})=>className==='language-mermaid'?<MermaidDiagram code={String(children).trim()}/>:className||String(children).includes('\n')?<pre><code className={className}>{children}</code></pre>:<code>{children}</code>,
  h1:({children})=><h3>{children}</h3>,h2:({children})=><h3>{children}</h3>
 }}>{children}</Markdown></div>;
}
