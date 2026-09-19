import React, {useState, useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import type {Inscription, Glyph} from './models';
import './style.css';
import './modern.css';
import {Contributions} from './Contributions';

function App(){
 const [route,setRoute]=useState(window.location.hash);
 useEffect(()=>{const sync=()=>setRoute(window.location.hash);window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync);},[]);
 const [menu,setMenu]=useState(false),[signedIn,setSignedIn]=useState(false);
 useEffect(()=>{const sync=(e:Event)=>setSignedIn(Boolean((e as CustomEvent).detail));window.addEventListener('ancientlens:auth-state',sync);return()=>window.removeEventListener('ancientlens:auth-state',sync);},[]);
 function navigate(target:'contributions'|'images'){setTab(target);setMenu(false);if(target==='contributions')window.location.hash='explore';}
 function contribute(){navigate('contributions');requestAnimationFrame(()=>{const refs=document.getElementById('reference-browser') as HTMLDetailsElement|null;if(refs)refs.open=true;window.dispatchEvent(new Event('ancientlens:search'));});}
 function find(){navigate('contributions');requestAnimationFrame(()=>window.dispatchEvent(new Event('ancientlens:browse')));}
 function account(){setTab('contributions');setMenu(false);requestAnimationFrame(()=>{const panel=document.getElementById('account-access') as HTMLDetailsElement|null;if(panel){panel.open=true;panel.scrollIntoView({block:'start'});panel.querySelector<HTMLInputElement>('input')?.focus();}});}
 useEffect(()=>{window.addEventListener('ancientlens:account',account);return()=>window.removeEventListener('ancientlens:account',account);},[]);
 function library(){setTab('contributions');setMenu(false);window.location.hash='library';requestAnimationFrame(()=>window.dispatchEvent(new Event('ancientlens:browse')));}
 useEffect(()=>{function shortcut(e:KeyboardEvent){if(e.key==='/'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!(e.target as HTMLElement).isContentEditable&&!['INPUT','TEXTAREA','SELECT'].includes((e.target as HTMLElement).tagName)){e.preventDefault();find();}if(e.key==='Escape')setMenu(false);}document.addEventListener('keydown',shortcut);return()=>document.removeEventListener('keydown',shortcut);},[]);
 const [inspector,setInspector]=useState(false);
 useEffect(()=>{fetch('/api/features').then(r=>r.ok?r.json():Promise.reject()).then(data=>setInspector(data.image_inspector===true)).catch(()=>setInspector(false));},[]);
 const [tab,setTab]=useState<'contributions'|'images'>('contributions');
 const [result,setResult]=useState<Inscription|null>(null);
 const [selected,setSelected]=useState<Glyph|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [boxes,setBoxes]=useState(true);
 useEffect(()=>{
  const id=new URLSearchParams(window.location.search).get('inscription');
  if(!id||!inspector)return;
  setTab('images');
  let cancelled=false;
  setBusy(true);
  fetch('/api/inscriptions/'+encodeURIComponent(id)).then(async response=>{
   if(!response.ok)throw new Error('Saved inscription could not be loaded');
   return response.json() as Promise<Inscription>;
  }).then(data=>{if(!cancelled){setResult(data);setSelected(data.glyphs[0]??null);}})
   .catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:'Load failed');})
   .finally(()=>{if(!cancelled)setBusy(false);});
  return ()=>{cancelled=true;};
 },[inspector]);
 async function upload(file:File){
  setError(''); setResult(null); setSelected(null);
  if(file.size>10*1024*1024){setError('Choose an image smaller than 10 MiB.');return;}
  setBusy(true);
  try{const body=new FormData();body.append('file',file);
   const response=await fetch('/api/inscriptions',{method:'POST',body});
   if(!response.ok){const e=await response.json();throw new Error(typeof e.detail==='string'?e.detail:'Upload failed');}
   const data:Inscription=await response.json();setResult(data);setSelected(data.glyphs[0]??null);
  }catch(e){setError(e instanceof Error?e.message:'Upload failed');}finally{setBusy(false);}
 }
 return <><a className="skip-link" href="#main-content">Skip to collection</a><header className="global-header"><a className="brand" href="/" aria-label="AncientLens home">◈ AncientLens</a><button className="menu-toggle" aria-label="Toggle main menu" aria-expanded={menu} aria-controls="primary-nav" onClick={()=>setMenu(!menu)}>☰</button><nav id="primary-nav" className={menu?'primary-nav is-open':'primary-nav'} aria-label="Primary"><button aria-current={tab==='contributions'&&route!=='#map'&&route!=='#library'&&!route.startsWith('#contribute-')?'page':undefined} onClick={find}>Explore</button><button aria-current={route==='#map'?'page':undefined} onClick={()=>{setTab('contributions');setMenu(false);window.location.hash='map';}}>Map</button><button aria-current={route==='#library'?'page':undefined} onClick={library}>My Library</button><button onClick={contribute}>Contribute</button>{inspector&&<button aria-current={tab==='images'?'page':undefined} onClick={()=>navigate('images')}>Research Tools</button>}</nav><div className="header-actions"><button onClick={find} aria-label="Search collection (slash shortcut)">⌕ <span>Search</span></button><button onClick={account}>{signedIn?'Account':'Sign in'}</button></div></header>
 <main id="main-content">
 <div hidden={tab!=='contributions'}><Contributions/></div><div hidden={!inspector||tab!=='images'}>
 <div className="notice"><strong>Experimental region proposals</strong> · Boxes follow high-contrast image features, which may not be text. Individual glyph segmentation, recognition and translation are unavailable.</div>
 <section className="workspace"><div className="viewer"><div className="toolbar"><h2>Inscription canvas</h2><label><input type="checkbox" checked={boxes} onChange={e=>setBoxes(e.target.checked)}/> Boxes</label></div>
 <label className="upload">{busy?'Processing image…':'＋ Upload inscription'}<input aria-label="Upload inscription" type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f);e.target.value='';}}/></label><small>JPEG, PNG or WebP · 10 MiB · 20 megapixels maximum</small>
 {error&&<p role="alert" className="error">{error}</p>}
 {result?<div className="image-wrap"><img src={result.image_url} alt="Uploaded inscription"/>{boxes&&<svg viewBox={`0 0 ${result.width} ${result.height}`} aria-label="Heuristic region proposals">{result.glyphs.map(g=><rect key={g.id} x={g.bbox.x} y={g.bbox.y} width={g.bbox.width} height={g.bbox.height} className={selected?.id===g.id?'active':''} onClick={()=>setSelected(g)} />)}</svg>}<div className="overlay">{result.translation.text??'Translation unavailable · recognition model required'}</div></div>:<div className="empty"><span>𓂀</span><h3>Every inscription begins with a closer look.</h3><p>Upload a photograph to inspect the pipeline.</p></div>}
 </div><aside><p className="eyebrow">EVIDENCE INSPECTOR</p><h2>Region details</h2>{result?<>{result.regions.length===0&&<p role="status">No candidate regions found. This does not prove the image contains no inscription; faint or small features may be missed.</p>}<div className="glyph-list">{result.glyphs.map((g,i)=><button key={g.id} aria-pressed={selected?.id===g.id} onClick={()=>setSelected(g)}>Box {i+1}</button>)}</div>{selected&&<><img className="crop" src={selected.crop_url} alt="Crop from proposed region"/><dl><dt>Status</dt><dd>Unidentified · heuristic region</dd><dt>Gardiner candidates</dt><dd>{selected.candidates.length?selected.candidates.map(c=>c.sign.code).join(', '):'None — recognition unavailable'}</dd><dt>Confidence</dt><dd>Not evaluated</dd><dt>Orientation / reading order</dt><dd>Unknown / unresolved</dd></dl></>}<h3>Transliteration</h3><p>{result.transliteration.text??'Withheld — no identified signs.'}</p><h3>English translation</h3><p>{result.translation.text??'Withheld — insufficient evidence.'}</p></>:<p>Choose a box after uploading an image to inspect its crop and available evidence.</p>}<div className="legend"><span>● High confidence (future)</span><span>● Uncertain (future)</span><span>◌ Missing / reconstructed (future)</span><span>□ Unidentified</span></div></aside></section>
 {result&&<details><summary>Inspect complete API result</summary><pre>{JSON.stringify(result,null,2)}</pre></details>}</div><footer><div><strong>AncientLens</strong><p>A growing collection. Free to explore.</p></div><div><a href="/data.html">Open data &amp; source</a> · <a href="/privacy.html">Privacy</a> · <a href="/contributor-terms-2026-09-16.1.html">Contributor terms</a> · <a href="mailto:ancientlens.contact@gmail.com">Contact</a></div></footer></main></>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
