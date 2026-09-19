import {citation, downloadText, type Artifact} from './Discovery';

const escapeHtml=(text:string)=>text.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));

// A standalone, script-free handout. Only public artifact fields are accepted;
// image bytes are embedded so the saved file remains useful offline.
export function lessonHtml(item:Artifact,imageData:string){
 if(!/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(imageData))throw new Error('Unsupported lesson image');
 const e=escapeHtml;
 return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>${e(item.title)} — AncientLens lesson</title><style>
 body{max-width:850px;margin:32px auto;padding:0 24px;color:#182c28;background:#fff;font:17px/1.6 system-ui,sans-serif}h1{line-height:1.15;font-size:32px}h2{font-size:22px;margin-top:28px}h3{font-size:18px}figure{margin:24px 0}img{display:block;max-width:100%;max-height:480px;margin:auto;object-fit:contain}figcaption,.citation,.note{font-size:14px}blockquote{margin:12px 0;padding-left:18px;border-left:3px solid #8b9e94;white-space:pre-wrap;overflow-wrap:anywhere}.caveat{padding:12px;background:#f1f3ee}.citation{overflow-wrap:anywhere}li{margin:10px 0}a{color:inherit}.print-help{padding:10px;border:1px solid #d7ded9}@media print{body{margin:0;max-width:none;padding:0;color:#000;font-size:11pt}h1{font-size:23pt}h2,h3{break-after:avoid}figure{break-inside:avoid}img{max-height:95mm}.print-help{display:none}a{text-decoration:none}.caveat{border:1px solid #aaa;background:none}}@page{margin:16mm}
 </style></head><body><p>AncientLens · Object-based lesson</p><h1>${e(item.title)}</h1><p>${e(item.date)} · ${e(item.collection)} collection</p><p class="print-help">This file includes its photograph and works offline. Use your browser’s Print command to print or save as PDF.</p><figure><img src="${imageData}" alt="${e(item.title)}"><figcaption>${e(item.institution)} · ${e(item.accession)} · CC0 photograph</figcaption></figure><p class="caveat">Museum source text · AncientLens scholarly review: unreviewed. Original spelling, typos and gaps are preserved. The photograph may not show every translated surface; passage alignment is unverified.${item.note?' '+e(item.note):''}</p><h2>Museum source passages</h2>${item.passages.map((p,i)=>`<section><h3>Inscription ${i+1}</h3><blockquote>${e(p.text)}</blockquote>${p.source_text?`<p class="note">Source transcription: ${e(p.source_text)}</p>`:''}${p.remark?`<p class="note">Museum note: ${e(p.remark)}</p>`:''}</section>`).join('')}<section><h2>Discussion prompts</h2><p class="note">AncientLens teaching aid, not museum source text.</p><ol><li>What does the published text say about this object?</li><li>Which details can you identify in the photograph?</li><li>What remains uncertain or outside the photographed surface?</li><li>Cite the museum source and separate your interpretation from its wording.</li></ol></section><section><h2>Source and reuse</h2><p class="citation">${e(citation(item))}</p><p class="note">Private research notes are not included.</p></section></body></html>`;
}

export async function downloadLesson(item:Artifact){
 const response=await fetch(item.image);
 if(!response.ok)throw new Error('Image unavailable');
 const blob=await response.blob();
 const imageData=await new Promise<string>((resolve,reject)=>{
  const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('Image unreadable'));reader.readAsDataURL(blob);
 });
 downloadText(item.id+'-lesson.html',lessonHtml(item,imageData),'text/html;charset=utf-8');
}
