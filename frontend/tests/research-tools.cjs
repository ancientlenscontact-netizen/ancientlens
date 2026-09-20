// Run against CommonJS output of Discovery.ts and LessonSheet.ts in a temporary directory.
const assert = require('node:assert/strict');
const path = require('node:path');
const dir = process.argv[2];
const {collection} = require(path.join(dir, 'collection.js'));
const {matches} = require(path.join(dir, 'Discovery.js'));
const {lessonHtml} = require(path.join(dir, 'LessonSheet.js'));
const item = collection.find(r => r.id === 'cma-102365');
assert.equal(matches(item,'privateessaymarker'),false);
assert.equal(matches(item,'privateessaymarker','My PrivateEssayMarker'),true);
assert.equal(matches(item,'Shemai privateessaymarker','PrivateEssayMarker'),true);
assert.equal(matches(item,'funerary'),true);
assert.equal(matches(item,'afterlife note','afterlife note'),true);
const image='data:image/jpeg;base64,/9j/';
const escape=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
for(const object of collection){
 const html=lessonHtml(object,object.image?image:'');
 for(const passage of object.passages)assert.ok(html.includes(escape(passage.text)));
 assert.ok(html.includes('scholarly review: unreviewed'));
 if(object.image){assert.ok(html.includes(object.image_license+' image'));assert.ok(html.includes(image));}
 else {assert.ok(!html.includes('<img'));assert.ok(html.includes('CC BY 4.0'));assert.ok(html.includes(escape(object.institution)));}
 assert.ok(!html.includes('<script'));
}
const hostile={...item,title:'<script>alert("x")</script>',note:'<img src=x onerror=alert(1)>',notes:'privateessaymarker'};
const html=lessonHtml(hostile,image);
assert.ok(html.includes('&lt;script&gt;'));
assert.ok(!html.includes('<script>'));
assert.ok(!html.includes('privateessaymarker'));
assert.throws(()=>lessonHtml(item,'data:image/svg+xml;base64,AAAA'));
assert.throws(()=>lessonHtml(item,'https://example.com/image.jpg'));
console.log('PASS: private-note search boundary; all source passages and mixed-license text-only exports; embedded image, escaping and no private-note export');
