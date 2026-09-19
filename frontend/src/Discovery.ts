import {collection} from './collection';
export type Artifact=typeof collection[number];
// Bounded editorial discovery labels, grounded in object titles; not scholarly readings.
export function topics(r:Artifact){const t=r.title.toLowerCase();return [
 /stele|canopic|shawabty/.test(t)?'Burial & remembrance':'',
 /drachm|stater|aureus|coin/.test(t)?'Coins & identity':'',
 /mirror/.test(t)?'Mirrors & daily life':'',
 /protective spirit|ramesses|nectanebo/.test(t)?'Rulers & protection':''
].filter(Boolean);}
export function objectType(r:Artifact){return /drachm|stater|aureus|coin/i.test(r.title)?'Coin':/mirror/i.test(r.title)?'Mirror':/stele|lintel|relief|spirit/i.test(r.title)?'Stone monument':'Other object';}
export function matches(r:Artifact,q:string){const aliases=q.toLowerCase().replace(/funerary|funeral|burial|afterlife|tomb/g,'burial').replace(/money|currency/g,'coins');const hay=[r.title,r.accession,r.date,r.description,r.source_language,...r.culture,...r.passages.map(p=>p.text),...topics(r),objectType(r)].join(' ').toLowerCase();return aliases.trim().split(/\s+/).every(word=>hay.includes(word));}
export function citation(r:Artifact,p?:Artifact['passages'][number]){return `${r.institution}. ${r.title}, accession ${r.accession}${p?`, museum field ${p.field}`:''}. ${r.source_url}. Source snapshot ${r.retrieved_at.slice(0,10)}. Via AncientLens: https://ancientlens.org/#artifact-${r.id}${p?`/inscription-${r.passages.findIndex(x=>x.id===p.id)+1}`:''}. CC0 source material. AncientLens scholarly review: unreviewed; individual translator not identified in imported fields.`;}
export function correctionLink(r:Artifact,p?:Artifact['passages'][number]){return 'mailto:ancientlens.contact@gmail.com?subject='+encodeURIComponent(`Source correction: ${r.accession}`)+'&body='+encodeURIComponent(citation(r,p)+'\n\nIssue noticed:\n\nSuggested correction and supporting source:\n\nPlease keep private notes and passwords out of this message.');}
export function downloadText(name:string,text:string,type='text/plain'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export function recordText(r:Artifact){return `${r.title} (${r.date})\n${citation(r)}\n\n${r.note||''}\nOriginal source typos and gaps preserved. Photograph-to-passage alignment unverified.\n\n${r.passages.map((p,i)=>`Inscription ${i+1} [${p.id}]\n${p.text}\n${p.source_text?'Source transcription: '+p.source_text:''}\n${p.remark?'Museum note: '+p.remark:''}`).join('\n\n')}`;}
