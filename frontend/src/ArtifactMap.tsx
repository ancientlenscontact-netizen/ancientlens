import {useState} from 'react';
import {collection} from './collection';
// Rounded overview coordinates, not excavation coordinates. Evidence is in pinned museum metadata.
export const discoveryPlaces=[
 {id:'giza',name:'Giza',lat:30,lon:31.1,artifacts:['cma-101380'],field:'culture',evidence:'Giza, western cemetery, excavations of Montague Ballard, 1901–2'},
 {id:'thebes',name:'Thebes / Luxor',lat:25.7,lon:32.6,artifacts:['cma-94136'],field:'find_spot',evidence:'Thebes, Egypt'},
 {id:'aswan',name:'Qubbet el-Hawa / Aswan',lat:24.1,lon:32.9,artifacts:['cma-102365'],field:'culture',evidence:'Aswan, Qubbet el-Hawa, excavations of Lady William Cecil, 1904'},
 {id:'nimrud',name:'Nimrud',lat:36.1,lon:43.3,artifacts:['cma-122979'],field:'find_spot',evidence:'palace of Ashur-nasirapal II in Calah (Nimrud)'},
];
const mappedCount=new Set(discoveryPlaces.flatMap(p=>p.artifacts)).size;
const unmappedCount=collection.length-mappedCount;
export function ArtifactMap({selected,onSelect}:{selected:string;onSelect:(id:string)=>void}){
 const [museum,setMuseum]=useState(selected==='cleveland'),[zoom,setZoom]=useState(1);
 const places=museum?[{id:'cleveland',name:'Cleveland Museum of Art',lat:41.5,lon:-81.6,artifacts:collection.map(r=>r.id),field:'institution',evidence:'Holding collection; display availability is not confirmed.'}]:discoveryPlaces;
 const width=(museum?150:40)/zoom,height=width/2,center=museum?[112,53]:[215,60];
 const left=center[0]-width/2,top=center[1]-height/2;
 const place=places.find(p=>p.id===selected);
 return <section className="discovery-map" aria-label="Find artifacts by location">
 <div className="map-toolbar"><div><h3>Explore by place</h3><p>Select a marker to see its artifacts.</p></div><div className="filter-row"><button aria-pressed={!museum} onClick={()=>{setMuseum(false);setZoom(1);onSelect('');}}>Found near</button><button aria-pressed={museum} onClick={()=>{setMuseum(true);setZoom(1);onSelect('');}}>Museum</button></div></div>
 <div className="map-canvas">
 <svg viewBox={`${left} ${top} ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true"><image href="/map-land.svg" width="360" height="180"/></svg>
 <span className="map-region">{museum?'NORTH AMERICA':'EGYPT · MESOPOTAMIA'}</span>
 {places.map(p=><button className={'map-marker'+(selected===p.id?' selected':'')} key={p.id} style={{left:`${(p.lon+180-left)/width*100}%`,top:`${(90-p.lat-top)/height*100}%`}} aria-label={`${p.name}: ${p.artifacts.length} artifacts`} aria-pressed={selected===p.id} onClick={()=>onSelect(p.id)}><span>{p.artifacts.length}</span><strong>{p.name}</strong></button>)}
 <div className="map-zoom"><button aria-label="Zoom in" disabled={zoom>=1.5} onClick={()=>setZoom(1.5)}>+</button><button aria-label="Zoom out" disabled={zoom===1} onClick={()=>setZoom(1)}>−</button></div></div>
 <div className="map-options"><label>Location <select value={selected} onChange={e=>onSelect(e.target.value)}><option value="">All artifacts</option>{places.map(p=><option key={p.id} value={p.id}>{p.name} ({p.artifacts.length})</option>)}{!museum&&<option value="unmapped">Findspot not mapped ({unmappedCount})</option>}</select></label>{selected&&<button onClick={()=>onSelect('')}>Clear location</button>}</div>
 {place&&<p role="status"><strong>{place.name}</strong> · {place.evidence} {place.id==='cleveland'?<a href="https://www.clevelandart.org/plan-your-visit">Museum details ↗</a>:<a href={collection.find(r=>r.id===place.artifacts[0])?.source_snapshot}>Museum evidence ↗</a>}</p>}
 <p className="collection-caption">{museum?'Collection location, not a findspot.':`${mappedCount} artifacts have mapped findspots; ${unmappedCount} remain unmapped. Mint locations are not findspots.`} Pins show approximate areas, not exact excavation coordinates. <a href="https://www.naturalearthdata.com/about/terms-of-use/">Natural Earth</a> basemap · Public domain.</p>
 </section>;
}
export function atPlace(artifact:string,place:string){if(!place||place==='cleveland')return true;const mapped=discoveryPlaces.find(p=>p.artifacts.includes(artifact));return place==='unmapped'?!mapped:mapped?.id===place;}
