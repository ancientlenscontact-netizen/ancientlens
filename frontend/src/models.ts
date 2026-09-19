// Mirrors backend/app/models.py; JSON uses null for unavailable values.
export interface ConfidenceScore {value:number|null; calibrated:boolean; basis:string}
export interface SourceReference {title:string; uri:string; license:string|null}
export interface BoundingBox {x:number;y:number;width:number;height:number}
export interface GardinerSign {code:string;meanings:string[];sources:SourceReference[]}
export interface GlyphCandidate {sign:GardinerSign;confidence:ConfidenceScore}
export interface Glyph {id:string;bbox:BoundingBox;crop_url:string;candidates:GlyphCandidate[];orientation:string|null;reading_order_index:number|null;status:'high_confidence'|'uncertain'|'missing'|'unidentified';confidence:ConfidenceScore}
export interface TextRegion {id:string;bbox:BoundingBox;glyph_ids:string[];confidence:ConfidenceScore}
export interface Transliteration {text:string|null;confidence:ConfidenceScore;uncertain_segments:string[]}
export interface TranslationAlternative {text:string;confidence:ConfidenceScore;sources:SourceReference[]}
export interface Translation {text:string|null;confidence:ConfidenceScore;alternatives:TranslationAlternative[];uncertain_segments:string[];missing_segments:string[];reasoning_metadata:string[]}
export interface Inscription {id:string;schema_version:string;script:string;image_url:string;width:number;height:number;mode:'mock'|'heuristic';regions:TextRegion[];glyphs:Glyph[];transliteration:Transliteration;translation:Translation;warnings:string[]}
