import {useState} from 'react';
import {collection} from './collection';
// Rounded overview coordinates, not excavation coordinates. Evidence is pinned museum metadata.
export const discoveryPlaces=[
 {id:'giza',name:'Giza',lat:30,lon:31.1,artifacts:['cma-101380'],evidence:'Giza, western cemetery, excavations of Montague Ballard, 1901–2'},
 {id:'thebes',name:'Thebes / Luxor',lat:25.7,lon:32.6,artifacts:['cma-94136'],evidence:'Thebes, Egypt'},
 {id:'aswan',name:'Qubbet el-Hawa / Aswan',lat:24.1,lon:32.9,artifacts:['cma-102365'],evidence:'Aswan, Qubbet el-Hawa, excavations of Lady William Cecil, 1904'},
 {id:'nimrud',name:'Nimrud',lat:36.1,lon:43.3,artifacts:['cma-122979'],evidence:'palace of Ashur-nasirapal II in Calah (Nimrud)'},
];
// Regional overview anchor only: not a claimed findspot or surveyed object coordinate.
export const attributedRegions=[{id:'mesoamerica-region',name:'Mesoamerica · published excerpts',lat:20,lon:-88,artifacts:collection.filter(r=>r.id.startsWith('maya-')).map(r=>r.id),evidence:'Broad cultural region only. These research excerpts concern Maya objects and documents; individual discovery histories vary or are unknown. See each source. This overview anchor is not a findspot.'},{id:'usumacinta-region',name:'Guatemala / Mexico · broad region',lat:17,lon:-91,artifacts:['cma-138393'],evidence:'Museum attribution: Guatemala or Mexico, Usumacinta River region, Maya style. Exact findspot unknown; this marker represents a broad region, not an excavation site.'}];
const mappedCount=new Set(discoveryPlaces.flatMap(p=>p.artifacts)).size;
const unmappedCount=collection.length-mappedCount;
type Layer='findspots'|'regions'|'museum';
type View='locations'|'world'|'americas';
export function ArtifactMap({selected,onSelect}:{selected:string;onSelect:(id:string)=>void}){
 const [layer,setLayer]=useState<Layer>(selected==='cleveland'?'museum':attributedRegions.some(p=>p.id===selected)?'regions':'findspots'),[zoom,setZoom]=useState(1),[view,setView]=useState<View>('locations');
 const places=layer==='museum'?[{id:'cleveland',name:'Cleveland Museum of Art',lat:41.5,lon:-81.6,artifacts:collection.filter(r=>r.id.startsWith('cma-')).map(r=>r.id),evidence:'Holding collection; display availability is not confirmed.'}]:layer==='regions'?attributedRegions:discoveryPlaces;
 const bounds=view==='world'?[180,90,360,180]:view==='americas'?[100,85,150,160]:layer==='museum'?[112,53,150,75]:layer==='regions'?[89,73,45,30]:[215,60,40,20];
 const width=bounds[2]/zoom,height=bounds[3]/zoom,left=bounds[0]-width/2,top=bounds[1]-height/2;
 const visible=places.filter(p=>p.lon+180>=left&&p.lon+180<=left+width&&90-p.lat>=top&&90-p.lat<=top+height);
 const place=places.find(p=>p.id===selected);
 function changeLayer(next:Layer){setLayer(next);setZoom(1);setView('locations');onSelect('');}
 return <section className="discovery-map" aria-label="Find artifacts by location">
 <div className="map-toolbar"><div><h3>Explore by place</h3><p>Select a marker to see its artifacts. Counts are before search filters.</p></div><div className="filter-row"><button aria-pressed={layer==='findspots'} onClick={()=>changeLayer('findspots')}>Findspots</button><button aria-pressed={layer==='regions'} onClick={()=>changeLayer('regions')}>Attributed regions</button><button aria-pressed={layer==='museum'} onClick={()=>changeLayer('museum')}>Museums</button></div></div>
 <div className="map-options"><label>Map view <select value={view} onChange={e=>{setView(e.target.value as View);setZoom(1);}}><option value="locations">Fit this layer</option><option value="world">World</option><option value="americas">Americas</option></select></label><small>Map view changes the viewport, not the results.</small></div>
 <div className="map-canvas" style={{height:'auto',aspectRatio:`${width}/${height}`}}>
 <svg viewBox={`${left} ${top} ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true"><image href="/map-land.svg" width="360" height="180"/></svg>
 <span className="map-region">{view==='world'?'WORLD':view==='americas'?'AMERICAS':layer==='regions'?'MESOAMERICA':layer==='museum'?'NORTH AMERICA':'EGYPT · MESOPOTAMIA'}</span>
 {visible.map(p=><button className={'map-marker'+(selected===p.id?' selected':'')} key={p.id} style={{left:`${(p.lon+180-left)/width*100}%`,top:`${(90-p.lat-top)/height*100}%`,borderStyle:layer==='regions'?'dashed':undefined}} aria-label={`${p.name}: ${p.artifacts.length} artifacts`} aria-pressed={selected===p.id} onClick={()=>onSelect(p.id)}><span>{p.artifacts.length}</span><strong>{p.name}</strong></button>)}
 <div className="map-zoom"><button aria-label="Zoom in" disabled={zoom>=1.5} onClick={()=>setZoom(1.5)}>+</button><button aria-label="Zoom out" disabled={zoom===1} onClick={()=>setZoom(1)}>−</button></div></div>
 {!visible.length&&<p className="collection-caption">No locations in this viewport for the selected layer. Try Attributed regions for the Maya collection.</p>}
 <div className="map-options"><label>Location <select value={selected} onChange={e=>{onSelect(e.target.value);setView('locations');setZoom(1);}}><option value="">All artifacts</option>{places.map(p=><option key={p.id} value={p.id}>{p.name} ({p.artifacts.length})</option>)}{layer==='findspots'&&<option value="unmapped">Findspot not mapped ({unmappedCount})</option>}</select></label>{selected&&<button onClick={()=>onSelect('')}>Clear location</button>}</div>
 {place&&<p role="status"><strong>{place.name}</strong> · {place.evidence} {place.id==='cleveland'?<a href="https://www.clevelandart.org/plan-your-visit">Museum details ↗</a>:<a href={collection.find(r=>r.id===place.artifacts[0])?.source_snapshot}>Source evidence ↗</a>}</p>}
 <p className="collection-caption">{layer==='museum'?'Collection location, not a findspot.':layer==='regions'?'Dashed markers show broad source-attributed regions. They are not findspots.':`${mappedCount} artifacts have mapped findspots; ${unmappedCount} remain unmapped. Mint locations are not findspots.`} No South American records are included yet. <a href="https://www.naturalearthdata.com/about/terms-of-use/">Natural Earth</a> basemap · Public domain.</p>
 </section>;
}
export function atPlace(artifact:string,place:string){if(!place)return true;if(place==='cleveland')return artifact.startsWith('cma-');if(place==='unmapped')return !discoveryPlaces.some(p=>p.artifacts.includes(artifact));return [...discoveryPlaces,...attributedRegions].some(p=>p.id===place&&p.artifacts.includes(artifact));}
